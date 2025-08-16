# app.py
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import pandas as pd
import os
import time
import base64
from supabase import create_client, Client
import openai  # Para DALL-E 3
import requests  # Para descargar las imágenes de DALL-E
import math  # Para la paginación del lector

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(layout="wide", page_title="Fábrica de Libros IA")

# --- INYECCIÓN DE CSS (La nueva interfaz moderna) ---
def load_css():
    st.markdown("""
        <style>
            /* Importar una fuente de Google Fonts */
            @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

            /* Paleta de colores principal */
            :root {
                --primary-color: #9b59b6; /* Un violeta vibrante */
                --background-color: #121212; /* Un negro suave */
                --secondary-background: #1E1E1E;
                --text-color: #E0E0E0;
                --subtle-text-color: #A0A0A0;
                --border-color: #333333;
            }

            /* Estilo general del cuerpo */
            body {
                font-family: 'Poppins', sans-serif;
                color: var(--text-color);
            }
            
            /* Contenedor principal de Streamlit */
            .main .block-container {
                padding-top: 2rem;
                padding-bottom: 2rem;
            }

            /* --- Animación de entrada para los elementos --- */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* Estilo para los contenedores de los libros en la biblioteca */
            .book-container {
                background-color: var(--secondary-background);
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 15px;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                animation: fadeIn 0.5s ease-out;
            }
            .book-container:hover {
                transform: scale(1.05) rotate(1deg);
                box-shadow: 0 10px 40px rgba(155, 89, 182, 0.2);
                border: 1px solid var(--primary-color);
            }
            .book-container h5 {
                color: var(--text-color);
                height: 40px; /* Altura fija para alinear títulos */
                overflow: hidden;
            }

            /* Estilo para los botones */
            .stButton>button {
                border-radius: 8px;
                border: 1px solid var(--primary-color);
                background-color: transparent;
                color: var(--primary-color);
                padding: 10px 24px;
                transition: all 0.3s ease;
            }
            .stButton>button:hover {
                background-color: var(--primary-color);
                color: white;
                border-color: var(--primary-color);
                box-shadow: 0 0 15px rgba(155, 89, 182, 0.5);
            }
            .stButton>button[kind="primary"] {
                background-color: var(--primary-color);
                color: white;
            }
             .stButton>button[kind="primary"]:hover {
                background-color: #8e44ad;
            }

            /* Estilo para el panel lateral (sidebar) */
            [data-testid="stSidebar"] {
                background-color: var(--secondary-background);
                border-right: 1px solid var(--border-color);
            }

            /* Spinner de carga */
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(155, 89, 182, 0.7); }
                70% { box-shadow: 0 0 0 20px rgba(155, 89, 182, 0); }
                100% { box-shadow: 0 0 0 0 rgba(155, 89, 182, 0); }
            }
            .pulse-icon {
                font-size: 50px;
                animation: pulse 2s infinite;
                border-radius: 50%;
                display: inline-block;
                padding: 10px;
                color: var(--primary-color);
            }
        </style>
    """, unsafe_allow_html=True)

load_css()

# --- INICIALIZACIÓN DE CLIENTES (GEMINI, SUPABASE Y OPENAI) ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    openai_client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"Asegúrate de configurar tus API keys (GOOGLE_API_KEY y OPENAI_API_KEY) en los Secrets. Error: {e}")
    st.stop()

@st.cache_resource
def init_supabase_client():
    try:
        url = st.secrets["supabase_url"]
        key = st.secrets["supabase_key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase. Revisa tus secrets 'supabase_url' y 'supabase_key'. Error: {e}")
        st.stop()

supabase = init_supabase_client()

# --- CONSTANTES Y GESTIÓN DE ARCHIVOS ---
IMAGE_DIR = "portadas"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# --- ESTADO DE LA SESIÓN ---
if 'view' not in st.session_state: st.session_state.view = 'library'
if 'selected_book_id' not in st.session_state: st.session_state.selected_book_id = None
if 'current_page' not in st.session_state: st.session_state.current_page = 0 # Para el lector avanzado

# --- FUNCIONES CORE ---
def cargar_libros():
    try:
        response = supabase.table('libros').select("*").order('created_at', desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return pd.DataFrame()

def anadir_libro_db(libro_data):
    try:
        response = supabase.table('libros').insert(libro_data).execute()
        return response.data[0]
    except Exception as e:
        st.error(f"Error al guardar el libro: {e}")
        return None

def borrar_libro(id_libro):
    try:
        # Borrar la portada local
        response = supabase.table('libros').select('ruta_portada').eq('id', id_libro).single().execute()
        if response.data and response.data.get('ruta_portada'):
            ruta_portada = response.data['ruta_portada']
            if os.path.exists(ruta_portada):
                os.remove(ruta_portada)
        # Borrar el registro en la base de datos
        supabase.table('libros').delete().eq('id', id_libro).execute()
    except Exception as e:
        st.error(f"Error al borrar el libro: {e}")

def actualizar_ruta_portada(id_libro, nueva_ruta):
    try:
        supabase.table('libros').update({'ruta_portada': nueva_ruta}).eq('id', id_libro).execute()
    except Exception as e:
        st.error(f"Error al actualizar la portada: {e}")

def generar_libro(prompt_usuario):
    model_texto = genai.GenerativeModel('gemini-1.5-pro-latest')
    mega_prompt = f"""
    Actúa como un maestro escritor. Tu tarea es expandir la siguiente idea en un libro corto.
    **Idea del Usuario:** "{prompt_usuario}"
    **Instrucciones:**
    1. **Título:** Crea un título atractivo.
    2. **Portada (Prompt):** Describe en una sola frase una escena visualmente impactante para la portada, estilo arte digital épico.
    3. **Contenido:** Escribe el libro con 3 a 5 capítulos, usando Markdown para los títulos de capítulo (ej. `### Capítulo 1: El Despertar`).
    4. **Formato de Salida:** Devuelve el resultado EXACTAMENTE en este formato: [TITULO]...[/TITULO][PORTADA_PROMPT]...[/PORTADA_PROMPT][CONTENIDO]...[/CONTENIDO]
    """
    try:
        response = model_texto.generate_content(mega_prompt)
        return response.text
    except Exception as e:
        st.error(f"Error al generar el texto con Gemini: {e}")
        return None

def generar_y_guardar_portada(prompt_portada, id_libro, titulo_libro):
    """Genera una imagen con DALL-E 3, la descarga y la guarda localmente."""
    try:
        enhanced_prompt = f"Book cover for a story titled '{titulo_libro}'. The scene is: '{prompt_portada}'. Epic digital art, cinematic lighting, high detail, illustration style, no text on the cover."
        
        st.info(f"🎨 Enviando a DALL-E 3: *'{enhanced_prompt}'*")
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            size="1024x1792",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url

        image_response = requests.get(image_url)
        image_response.raise_for_status()

        ruta_archivo = os.path.join(IMAGE_DIR, f"{id_libro}.png")
        with open(ruta_archivo, "wb") as f:
            f.write(image_response.content)
        return ruta_archivo
    except Exception as e:
        st.error(f"Ocurrió un error al generar la portada con DALL-E 3: {e}")
        return None

# --- FUNCIONES DE LA INTERFAZ ---

def mostrar_biblioteca():
    st.title("📚 Mi Biblioteca")
    st.markdown("---")
    
    libros_df = cargar_libros()
    if libros_df.empty:
        st.info("Tu estantería está vacía. ¡Crea tu primer libro en el panel de la izquierda!")
        return

    num_columnas = st.slider("Libros por fila:", 2, 6, 4)
    cols = st.columns(num_columnas)
    
    for i, libro in libros_df.iterrows():
        col = cols[i % num_columnas]
        with col.container():
            if libro['ruta_portada'] and os.path.exists(libro['ruta_portada']):
                st.image(libro['ruta_portada'], caption=libro['titulo'], use_column_width=True)
            else:
                st.markdown(f"<div class='book-container' style='height: 350px; display: flex; align-items: center; justify-content: center; text-align: center;'>Portada no encontrada para<br><b>{libro['titulo']}</b></div>", unsafe_allow_html=True)

            if st.button("📖 Abrir Libro", key=f"read_{libro['id']}", use_container_width=True):
                st.session_state.view = 'reader'
                st.session_state.selected_book_id = libro['id']
                st.session_state.current_page = 0 # Siempre empezar por la primera página
                st.rerun()

def mostrar_lector():
    book_id = st.session_state.selected_book_id
    libros_df = cargar_libros()
    libro = libros_df[libros_df['id'] == book_id].iloc[0]

    if st.button("◀️ Volver a la Biblioteca"):
        st.session_state.view = 'library'
        st.session_state.selected_book_id = None
        st.session_state.current_page = 0
        st.rerun()

    st.title(libro['titulo'])
    st.markdown("---")
    
    col1, col2 = st.columns([0.4, 0.6])
    with col1:
        st.image(libro['ruta_portada'])
        with st.expander("Opciones del Libro"):
            st.info(f"**Prompt de portada:** *{libro['prompt_portada']}*")
            if st.button("🎨 Regenerar Portada", use_container_width=True):
                with st.spinner("Creando una nueva visión con DALL-E 3..."):
                    nueva_ruta = generar_y_guardar_portada(libro['prompt_portada'], libro['id'], libro['titulo'])
                    if nueva_ruta:
                        actualizar_ruta_portada(libro['id'], nueva_ruta)
                        st.success("¡Portada actualizada!")
                        st.rerun()
            
            if st.button("🗑️ Borrar Libro", type="primary", use_container_width=True):
                borrar_libro(libro['id'])
                st.success(f"'{libro['titulo']}' ha sido borrado.")
                st.session_state.view = 'library'
                st.session_state.selected_book_id = None
                time.sleep(1)
                st.rerun()
        
        st.subheader("Preferencias de Lectura")
        theme = st.radio("Tema:", ("Día ☀️", "Sepia 📜", "Noche 🌙"), horizontal=True, key="theme")
        font_family = st.radio("Fuente:", ("Serifa", "Sans-Serif"), horizontal=True, key="font")
    
    with col2:
        contenido_limpio = libro['contenido'].replace('<br>', ' ')
        palabras = contenido_limpio.split()
        PALABRAS_POR_PAGINA = 250
        total_paginas = math.ceil(len(palabras) / PALABRAS_POR_PAGINA)

        if st.session_state.current_page >= total_paginas: st.session_state.current_page = total_paginas - 1
        if st.session_state.current_page < 0: st.session_state.current_page = 0

        start_word = st.session_state.current_page * PALABRAS_POR_PAGINA
        end_word = start_word + PALABRAS_POR_PAGINA
        pagina_actual_texto = " ".join(palabras[start_word:end_word]).replace('\n', '<br>')

        font_css = "font-family: 'Georgia', serif;" if font_family == "Serifa" else "font-family: 'Poppins', sans-serif;"
        
        if theme == "Noche 🌙":
            theme_css = "background-color: #1E1E1E; color: #E0E0E0; border-color: #444;"
        elif theme == "Sepia 📜":
            theme_css = "background-color: #FBF0D9; color: #5B4636; border-color: #E9DDC7;"
        else: # Día
            theme_css = "background-color: #FFFFFF; color: #333333; border-color: #EAEAEA;"

        st.markdown(f"""
            <style>
            .book-content {{
                {theme_css}
                {font_css}
                padding: 30px; border-radius: 10px; border: 1px solid; height: 500px;
                overflow-y: auto; font-size: 1.1em; line-height: 1.6;
            }}
            </style>
            <div class="book-content">
                {pagina_actual_texto}
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        nav_cols = st.columns([1, 2, 1])
        with nav_cols[0]:
            if st.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.current_page == 0)):
                st.session_state.current_page -= 1
                st.rerun()
        with nav_cols[1]:
            st.markdown(f"<p style='text-align: center; font-weight: bold;'>Página {st.session_state.current_page + 1} de {total_paginas}</p>", unsafe_allow_html=True)
        with nav_cols[2]:
            if st.button("Siguiente ➡️", use_container_width=True, disabled=(st.session_state.current_page >= total_paginas - 1)):
                st.session_state.current_page += 1
                st.rerun()

def mostrar_creador():
    st.header("Crear un Nuevo Libro")
    
    modo_creacion = st.radio(
        "Modo de creación:", ('A partir de una idea', 'Por género y personaje'), horizontal=True)
    
    prompt_final = ""
    if modo_creacion == 'A partir de una idea':
        idea_usuario = st.text_area("Escribe la sinopsis de tu historia:", height=150, placeholder="Ej: Un detective en un Madrid ciberpunk investiga la desaparición de un androide con recuerdos humanos...")
        prompt_final = idea_usuario
    else: 
        col1, col2 = st.columns(2)
        with col1:
            genero = st.selectbox("Elige un género:", ["Fantasía Épica", "Ciencia Ficción", "Misterio Noir", "Aventura Juvenil", "Terror Cósmico"])
        with col2:
            personaje = st.text_input("Nombre del protagonista:", "Elara")
        descripcion_extra = st.text_area("Añade algún detalle extra (opcional):", placeholder="Ej: ...que tiene el poder de hablar con las estrellas.")
        prompt_final = f"Crea una historia de '{genero}' con un protagonista llamado {personaje}. Detalle adicional: {descripcion_extra}."

    if st.button("✨ ¡Forjar mi Libro!", type="primary", use_container_width=True):
        if prompt_final and prompt_final.strip():
            spinner_placeholder = st.empty()
            with spinner_placeholder.container():
                st.markdown("<p style='text-align: center;'>Forjando tu narrativa... ✍️</p>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center;'><span class='pulse-icon'>📖</span></p>", unsafe_allow_html=True)
            
            libro_texto = generar_libro(prompt_final)
            spinner_placeholder.empty()

            if libro_texto:
                try:
                    titulo = libro_texto.split("[TITULO]")[1].split("[/TITULO]")[0].strip()
                    prompt_portada = libro_texto.split("[PORTADA_PROMPT]")[1].split("[/PORTADA_PROMPT]")[0].strip()
                    contenido = libro_texto.split("[CONTENIDO]")[1].split("[/CONTENIDO]")[0].strip().replace('\n', '<br>')
                    
                    with st.spinner("Guardando tu historia en la base de datos..."):
                        libro_parcial = {'titulo': titulo, 'prompt_portada': prompt_portada, 'contenido': contenido}
                        nuevo_libro_data = anadir_libro_db(libro_parcial)
                    
                    if nuevo_libro_data:
                        id_libro = nuevo_libro_data['id']
                        with st.spinner("Dando vida a tu portada con DALL-E 3..."):
                            ruta_portada = generar_y_guardar_portada(prompt_portada, id_libro, titulo)
                        
                        if ruta_portada:
                            actualizar_ruta_portada(id_libro, ruta_portada)
                            st.success("¡Tu libro ha sido forjado y guardado!")
                            st.session_state.view = 'reader'
                            st.session_state.selected_book_id = id_libro
                            st.rerun()
                except IndexError:
                    st.error("La IA no devolvió el formato esperado. Inténtalo de nuevo con más detalle.")
        else:
            st.warning("Por favor, introduce una idea para poder crear tu libro.")

# --- LÓGICA PRINCIPAL DE LA APLICACIÓN ---
with st.sidebar:
    st.title("🚀 Fábrica de Libros")
    st.markdown("---")
    mostrar_creador()
    st.markdown("---")
    st.info("Créditos de Generación: 10/10")
    st.button("🖼️ Galería Comunitaria (Próximamente)", disabled=True, use_container_width=True)

# Router principal
if st.session_state.view == 'library':
    mostrar_biblioteca()
elif st.session_state.view == 'reader':
    mostrar_lector()
    
