# app.py
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import pandas as pd
import os
import time
from PIL import Image
import random

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(layout="wide", page_title="Fábrica de Libros 3D")

# Carga segura de la API Key desde los secrets de Streamlit
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Por favor, configura tu GOOGLE_API_KEY en los Secrets de Streamlit.")
    st.stop()

# --- CONSTANTES Y GESTIÓN DE ARCHIVOS ---
CSV_FILE = "books.csv"
IMAGE_DIR = "portadas"
STATIC_DIR = "static"
MODEL_PATH = os.path.join(STATIC_DIR, "book.glb")

for directory in [IMAGE_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# --- ESTADO DE LA SESIÓN ---
if 'view' not in st.session_state:
    st.session_state.view = 'library'
if 'selected_book_id' not in st.session_state:
    st.session_state.selected_book_id = None

# --- FUNCIONES CORE ---
def cargar_libros():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        return pd.DataFrame(columns=['id', 'titulo', 'prompt_portada', 'contenido', 'ruta_portada'])

def guardar_libro(id_libro, titulo, prompt_portada, contenido, ruta_portada):
    df = cargar_libros()
    df = df[df.id != id_libro] # Evita duplicados si se regenera
    nuevo_libro = pd.DataFrame([{'id': id_libro, 'titulo': titulo, 'prompt_portada': prompt_portada, 'contenido': contenido, 'ruta_portada': ruta_portada}])
    df = pd.concat([df, nuevo_libro], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)

def generar_libro(prompt_usuario):
    model_texto = genai.GenerativeModel('gemini-1.5-pro-latest')
    mega_prompt = f"""
    Actúa como un maestro escritor de novelas. Tu tarea es tomar la siguiente idea y expandirla en un libro corto y completo.
    **Idea del Usuario:** "{prompt_usuario}"
    **Instrucciones:**
    1. **Título:** Crea un título atractivo y relevante.
    2. **Portada (Prompt):** Describe en una sola frase una escena visualmente impactante para la portada.
    3. **Contenido:** Escribe el libro dividido en 3 a 5 capítulos con sus títulos.
    4. **Formato de Salida:** Devuelve el resultado EXACTAMENTE en el siguiente formato: [TITULO]...[/TITULO][PORTADA_PROMPT]...[/PORTADA_PROMPT][CONTENIDO]...[/CONTENIDO]
    """
    try:
        response = model_texto.generate_content(mega_prompt)
        return response.text
    except Exception as e:
        st.error(f"Error al generar el texto: {e}")
        return None

def generar_y_guardar_portada(prompt_portada, id_libro):
    try:
        # Usamos el código placeholder.
        img = Image.new('RGB', (600, 800), color = (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150)))
        ruta_archivo = os.path.join(IMAGE_DIR, f"{id_libro}.png")
        img.save(ruta_archivo)
        return ruta_archivo
    except Exception as e:
        st.error(f"No se pudo generar la portada: {e}")
        return None

# --- FUNCIONES DE LA INTERFAZ ---
def mostrar_biblioteca():
    st.title("📚 Mi Biblioteca 3D")
    st.markdown("---")
    
    libros_df = cargar_libros()
    if libros_df.empty:
        st.info("Tu estantería está vacía. ¡Crea tu primer libro en el menú de la izquierda!")
        return

    num_columnas = st.number_input("Libros por fila:", 2, 6, 4)
    cols = st.columns(num_columnas)
    libros_a_mostrar = libros_df.sort_values(by='id', ascending=False)

    for i, libro in enumerate(libros_a_mostrar.itertuples()):
        with cols[i % num_columnas]:
            st.subheader(libro.titulo)
            
            if os.path.exists(libro.ruta_portada) and os.path.exists(MODEL_PATH):
                with open("viewer.html", "r", encoding="utf-8") as f:
                    html_template = f.read()
                
                html_final = html_template.replace("static/book.glb", MODEL_PATH).replace("portadas/default.png", libro.ruta_portada)
                components.html(html_final, height=400, scrolling=False)
            
            if st.button("📖 Abrir y Leer", key=f"read_{libro.id}"):
                st.session_state.view = 'reader'
                st.session_state.selected_book_id = libro.id
                st.rerun()

def mostrar_lector():
    book_id = st.session_state.selected_book_id
    libros_df = cargar_libros()
    libro = libros_df[libros_df.id == book_id].iloc[0]

    if st.button("◀️ Volver a la Biblioteca"):
        st.session_state.view = 'library'
        st.session_state.selected_book_id = None
        st.rerun()

    st.title(libro.titulo)
    st.markdown("---")
    
    col1, col2 = st.columns([0.4, 0.6])
    with col1:
        st.image(libro.ruta_portada)
        st.info(f"**Prompt de la portada:** *{libro.prompt_portada}*")
        if st.button("🎨 Regenerar Portada"):
            with st.spinner("Creando una nueva visión..."):
                nueva_ruta = generar_y_guardar_portada(libro.prompt_portada, libro.id)
                if nueva_ruta:
                    guardar_libro(libro.id, libro.titulo, libro.prompt_portada, libro.contenido, nueva_ruta)
                    st.success("¡Portada actualizada!")
                    st.rerun()

    with col2:
        st.markdown(libro.contenido)

def mostrar_creador():
    st.header("Crear un Nuevo Libro")
    idea_usuario = st.text_area("Escribe aquí tu idea:", height=150, key="idea_input")

    if st.button("✨ ¡Crear mi libro!", type="primary"):
        if idea_usuario:
            with st.spinner("Forjando tu narrativa... ✍️"):
                libro_texto = generar_libro(idea_usuario)
            if libro_texto:
                try:
                    titulo = libro_texto.split("[TITULO]")[1].split("[/TITULO]")[0].strip()
                    prompt_portada = libro_texto.split("[PORTADA_PROMPT]")[1].split("[/PORTADA_PROMPT]")[0].strip()
                    contenido = libro_texto.split("[CONTENIDO]")[1].split("[/CONTENIDO]")[0].strip()
                    id_libro = int(time.time())
                    ruta_portada = generar_y_guardar_portada(prompt_portada, id_libro)

                    if ruta_portada:
                        guardar_libro(id_libro, titulo, prompt_portada, contenido, ruta_portada)
                        st.success("¡Tu libro ha sido forjado!")
                        st.session_state.view = 'reader'
                        st.session_state.selected_book_id = id_libro
                        st.rerun()
                except IndexError:
                    st.error("La IA no devolvió el formato esperado. Inténtalo de nuevo.")
        else:
            st.warning("Una idea es la semilla de una historia. ¡Planta una!")

# --- LÓGICA PRINCIPAL DE LA APLICACIÓN ---
with st.sidebar:
    st.title("🚀 Panel de Creación")
    mostrar_creador()

if st.session_state.view == 'library':
    mostrar_biblioteca()
elif st.session_state.view == 'reader':
    mostrar_lector()
  
