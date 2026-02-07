import cv2
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import threading
import os
import time
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image
import numpy as np  # <-- Agrégalo junto con tus otros imports
import textwrap

# Variables globales
grabando = False
video_writer = None
frame_count = 0       # contador de frames grabados
fps = 20.0            # mismo valor que usas en VideoWriter
nombre_archivo_base = ""
anotaciones = []
texto_actual = ""
texto_timestamp = 0
ancho = 0
alto = 0
tiempo_inicio_grabacion = None
ultima_imagen = None
carpeta_destino = ""
carpeta_grabacion = ""
tramo_nombre = ""
cap = None
cerrar_camara = False  # <-- NUEVA VARIABLE PARA CERRAR CÁMARA MANUALMENTE

def crear_carpeta_guardado():
    global carpeta_destino
    hoy = datetime.now().strftime("%Y-%m-%d")
    carpeta_destino = os.path.join("grabaciones", hoy)
    os.makedirs(carpeta_destino, exist_ok=True)

def iniciar_captura():
    def capturar():
        global grabando, video_writer, nombre_archivo_base, anotaciones
        global texto_actual, texto_timestamp, ancho, alto
        global tiempo_inicio_grabacion, ultima_imagen, cap, cerrar_camara
        global boton_iniciar  # <- para poder modificar el estado del botón

        cap = None  # Se declara aquí porque se va a asignar en este mismo bloque

        for index in range(1, 10):  # Escanea hasta 10 cámaras posibles
            temp_cap = cv2.VideoCapture(index)

            # Forzar resolución HD (1280x720)
            temp_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            temp_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

            if temp_cap is not None and temp_cap.isOpened():
                cap = temp_cap
                print(f"Cámara USB encontrada en índice {index}")
                break
            else:
                temp_cap.release()


        if cap is None or not cap.isOpened():
            print("No se pudo encontrar una cámara USB disponible.")
            if boton_iniciar:
                root.after(0, lambda: boton_iniciar.config(state=tk.NORMAL))
            return

        cerrar_camara = False
        ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cv2.namedWindow("Captura CCTV", cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)

        # 🟩 Posicionar y redimensionar ventana de cámara a la derecha
        cv2.resizeWindow("Captura CCTV", ancho_cv, pantalla_alto)
        cv2.moveWindow("Captura CCTV", ancho_tk, 0)

        # Solo se llama una vez antes del bucle
        while cap.isOpened() and not cerrar_camara:
            ret, frame = cap.read()
            if not ret:
                break

            ahora = time.time()
            if texto_actual and ahora - texto_timestamp < 5:
                # 🔹 Ajustar texto largo al ancho del video
                max_chars_por_linea = max(30, min(60, ancho // 20))
                texto_envuelto = textwrap.fill(texto_actual, width=max_chars_por_linea)

                # 🔹 Configuración del texto
                lineas = texto_envuelto.split('\n')
                font_scale = 0.8
                thickness = 2
                y_offset = alto - 10

                # 🟢 Dibujar línea por línea (de abajo hacia arriba)
                for i, linea in enumerate(reversed(lineas)):
                    cv2.putText(frame, linea, (10, y_offset - i * 30),
                                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)


            if grabando and ret:
                global frame_count
                frame_count += 1  # aumentar contador de frames grabados
                tiempo_transcurrido = frame_count / fps  # tiempo real según los frames
                tiempo_str = time.strftime('%H:%M:%S', time.gmtime(int(tiempo_transcurrido)))
                # 🕒 Mostrar solo el tiempo en pantalla (sin texto "GRABANDO")
                cv2.putText(frame, tiempo_str, (10, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                video_writer.write(frame)

            ultima_imagen = frame.copy()

            # 🔁 NUEVO BLOQUE PARA REDIMENSIONAR SIN DEFORMAR
            window_rect = cv2.getWindowImageRect("Captura CCTV")
            target_w, target_h = window_rect[2], window_rect[3]
            frame_h, frame_w = frame.shape[:2]

            # Relación de aspecto
            aspect_ratio_frame = frame_w / frame_h
            aspect_ratio_win = target_w / target_h

            if aspect_ratio_win > aspect_ratio_frame:
                # La ventana es más ancha, escalamos según la altura
                new_h = target_h
                new_w = int(aspect_ratio_frame * new_h)
            else:
                # La ventana es más alta, escalamos según el ancho
                new_w = target_w
                new_h = int(new_w / aspect_ratio_frame)

            frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Crear fondo negro y centrar
            lienzo = cv2.UMat(np.zeros((target_h, target_w, 3), dtype=np.uint8)).get()
            offset_x = (target_w - new_w) // 2
            offset_y = (target_h - new_h) // 2
            lienzo[offset_y:offset_y + new_h, offset_x:offset_x + new_w] = frame_resized

            cv2.imshow("Captura CCTV", lienzo)


            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        if cap:
            cap.release()
        if video_writer:
            video_writer.release()
        cv2.destroyAllWindows()

        # ✅ Reactivar el botón después de cerrar cámara
        if boton_iniciar:
            root.after(0, lambda: boton_iniciar.config(state=tk.NORMAL))

    crear_carpeta_guardado()
    if boton_iniciar:
        boton_iniciar.config(state=tk.DISABLED)  # 🔒 Desactiva el botón
    threading.Thread(target=capturar).start()

def guardar_video():
    global grabando, video_writer, nombre_archivo_base, anotaciones
    global ancho, alto, tiempo_inicio_grabacion, carpeta_grabacion, tramo_nombre

    if not grabando:
        now = datetime.now()
        # 🕒 Nombre base solo con la hora, sin el texto "video"
        nombre_archivo_base = now.strftime("%H-%M-%S")

        # 🟩 Crear carpeta dentro del día con el formato TRAMO_HH-MM-SS
        carpeta_grabacion = os.path.join(carpeta_destino, f"{tramo_nombre}_{nombre_archivo_base}")
        os.makedirs(carpeta_grabacion, exist_ok=True)

        # 🎥 Nombre del archivo de video con el mismo formato
        video_filename = os.path.join(carpeta_grabacion, f"{tramo_nombre}_{nombre_archivo_base}.avi")

        if ancho > 0 and alto > 0:
            video_writer = cv2.VideoWriter(
                video_filename,
                cv2.VideoWriter_fourcc(*'XVID'),
                20.0,
                (1280, 720)  # 👈 fuerza resolución HD
            )
            grabando = True
            anotaciones = []
            tiempo_inicio_grabacion = time.time()


def detener_video():
    global grabando, video_writer, nombre_archivo_base, anotaciones, carpeta_grabacion

    if grabando:
        grabando = False
        if video_writer:
            video_writer.release()
            video_writer = None
        global frame_count
        frame_count = 0  # reiniciar contador para la próxima grabación

        txt_filename = os.path.join(carpeta_grabacion, f"{tramo_nombre}_{nombre_archivo_base}.txt")
        with open(txt_filename, "w", encoding="utf-8") as f:
            for entrada in anotaciones:
                f.write(entrada + "\n")
        messagebox.showinfo("Grabación finalizada", f"Video y anotaciones guardadas en:\n{carpeta_grabacion}")

def insertar_texto():
    global texto_actual, texto_timestamp, anotaciones, ultima_imagen, tramo_nombre
    texto = entrada_texto.get("1.0", tk.END).strip()

    if texto:
        texto_actual = texto
        texto_timestamp = time.time()

        # ⏱️ Usar tiempo relativo desde que empezó la grabación
        if grabando:
            elapsed = frame_count / fps  # tiempo según frames grabados
            marca_tiempo = time.strftime("%H:%M:%S", time.gmtime(int(elapsed)))
        else:
            marca_tiempo = "00:00:00"

        # 🧾 Registrar la anotación en la lista
        anotaciones.append(f"[{marca_tiempo}] {texto}")
        entrada_texto.delete("1.0", tk.END)

        # 📸 Guardar imagen con texto sobrepuesto
        if ultima_imagen is not None:
            frame_con_texto = ultima_imagen.copy()
            alto_local = frame_con_texto.shape[0]
            ancho_local = frame_con_texto.shape[1]

            # 🧾 Ajustar texto largo al ancho del video
            import textwrap
            max_chars_por_linea = max(30, min(60, ancho_local // 20))
            texto_envuelto = textwrap.fill(texto, width=max_chars_por_linea)

            # 🟩 Configuración del texto
            lineas = texto_envuelto.split('\n')
            y_offset = alto_local - 10
            font_scale = 0.8   # 🔹 tamaño reducido de fuente
            thickness = 2

            # 🟢 Dibujar línea por línea (de abajo hacia arriba)
            for i, linea in enumerate(reversed(lineas)):
                cv2.putText(frame_con_texto, linea, (10, y_offset - i * 30),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)

            # 🕒 Guardar imagen usando el tiempo transcurrido, no la hora del PC
            timestamp = time.strftime("%H-%M-%S", time.gmtime(int(elapsed)))

            # ✨ Limpiar el texto para evitar caracteres inválidos en nombres de archivo
            texto_limpio = (texto.replace(" ", "_")
                                   .replace(":", "-")
                                   .replace("/", "-")
                                   .replace("\\", "-"))

            # 📄 Crear nombre con formato: TRAMO_HH-MM-SS_Anotacion.jpg
            nombre_imagen = f"{tramo_nombre}_{timestamp}_{texto_limpio}.jpg"
            ruta = os.path.join(carpeta_grabacion, nombre_imagen)
            cv2.imwrite(ruta, frame_con_texto)

def capturar_imagen():
    global ultima_imagen, carpeta_grabacion
    if ultima_imagen is not None:
        timestamp = datetime.now().strftime("%H-%M-%S")
        ruta = os.path.join(carpeta_grabacion, f"imagen_{timestamp}.jpg")
        cv2.imwrite(ruta, ultima_imagen)
        messagebox.showinfo("Imagen guardada", f"Se guardó en:\n{ruta}")
    else:
        messagebox.showwarning("Aviso", "No hay imagen disponible.")

def generar_informe_pdf():
    global tramo_nombre, carpeta_grabacion, anotaciones

    if not tramo_nombre:
        messagebox.showwarning("Falta tramo", "Por favor ingresa el ID del tramo antes de generar el informe.")
        return

    pdf_path = os.path.join(carpeta_grabacion, f"{tramo_nombre}_{nombre_archivo_base}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    y = height - 40

    # Título
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, f"Informe de Inspección - Tramo: {tramo_nombre}")
    y -= 30

    c.setFont("Helvetica", 12)
    c.drawString(40, y, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 40

    # Recorrer imágenes en orden
    for archivo in sorted(os.listdir(carpeta_grabacion)):
        if archivo.lower().endswith(".jpg") and archivo.startswith(tramo_nombre):
            # 🧩 Separar nombre: TRAMO_HH-MM-SS_Anotacion.jpg
            base = archivo.replace(".jpg", "")
            partes = base.split("_", 2)  # ['TR009', '00-00-08', 'Inicio_de_Inspección']

            if len(partes) >= 3:
                ts_text = partes[1].replace("-", ":")
                texto_anotacion = partes[2].replace("_", " ")
            else:
                ts_text = ""
                texto_anotacion = "(sin descripción)"

            img_path = os.path.join(carpeta_grabacion, archivo)

            try:
                # 🖼️ Cargar y escalar imagen
                img = Image.open(img_path)
                iw, ih = img.size
                max_width, max_height = 450, 280
                ratio = min(max_width / iw, max_height / ih)
                new_width, new_height = int(iw * ratio), int(ih * ratio)

                # 📄 Calcular espacio requerido
                espacio_necesario = new_height + 60  # 40 margen + 20 texto
                if y - espacio_necesario < 100:
                    c.showPage()
                    y = height - 40

                # 🟩 Dibujar anotación (solo una vez)
                c.setFont("Helvetica-Bold", 12)
                c.drawString(40, y, f"[{ts_text}] {texto_anotacion}")
                y -= 25

                # 🖼️ Dibujar imagen
                c.drawImage(ImageReader(img_path), 50, y - new_height,
                            width=new_width, height=new_height, preserveAspectRatio=True, mask='auto')

                y -= (new_height + 40)  # espacio después de la imagen

            except Exception as e:
                print(f"Error cargando imagen {archivo}: {e}")

    c.save()
    messagebox.showinfo("Informe generado", f"Informe PDF guardado en:\n{pdf_path}")

def cerrar_ventana():
    global cap, cerrar_camara
    cerrar_camara = True
    time.sleep(0.5)
    if cap:
        cap.release()
        cap = None
    cv2.destroyAllWindows()
    root.destroy()

def cerrar_camara_manual():
    global cerrar_camara, cap
    cerrar_camara = True
    time.sleep(0.5)  # Pequeña pausa para salir del loop
    if cap:
        cap.release()
        cap = None
    cv2.destroyAllWindows()

# Interfaz gráfica
root = tk.Tk()
root.title("Capturador CCTV GSA")

# 🔹 Distribución de ventanas
root.update_idletasks()
pantalla_ancho = root.winfo_screenwidth()
pantalla_alto = root.winfo_screenheight()

ancho_tk = pantalla_ancho // 3         # 1/3 de pantalla para Tkinter
ancho_cv = pantalla_ancho - ancho_tk   # 2/3 para OpenCV

# Fijar posición de ventana Tkinter a la izquierda
root.geometry(f"{ancho_tk}x{pantalla_alto}+0+0")

root.resizable(True, True)  # ✅ Permite redimensionar la ventana
root.protocol("WM_DELETE_WINDOW", cerrar_ventana)

tk.Label(root, text="Id Tramo:").pack()
entrada_cliente = tk.Entry(root, width=50)
entrada_cliente.pack(pady=5)

def actualizar_cliente():
    global tramo_nombre
    tramo_nombre = entrada_cliente.get().strip()
    if tramo_nombre:
        messagebox.showinfo("Tramo asignado", f"Tramo: {tramo_nombre}")
    else:
        messagebox.showwarning("Tramo", "Ingresa un ID de tramo válido.")

tk.Button(root, text="Asignar Tramo", command=actualizar_cliente).pack(pady=5)


entrada_texto = tk.Text(root, height=4, width=50)
entrada_texto.pack(pady=5)

tk.Button(root, text="Insertar Texto", command=insertar_texto).pack(pady=5)
tk.Button(root, text="Grabar Video", command=guardar_video).pack(pady=5)
tk.Button(root, text="Detener Grabación", command=detener_video).pack(pady=5)
tk.Button(root, text="Capturar Imagen", command=capturar_imagen).pack(pady=5)
tk.Button(root, text="Cerrar Cámara", command=cerrar_camara_manual).pack(pady=5)  # <-- NUEVO BOTÓN
tk.Button(root, text="Generar Informe PDF", command=generar_informe_pdf).pack(pady=5)

boton_iniciar = tk.Button(root, text="Iniciar Cámara", command=iniciar_captura)
boton_iniciar.pack(pady=5)

root.mainloop()
