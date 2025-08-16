# app.py
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import pandas as pd
import os
import time
from PIL import Image
import random
import base64 # Necesario para la animación de hover

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(layout="wide", page_title="Fábrica de Libros 3D")

# --- INYECCIÓN DE CSS PARA ANIMACIONES Y ESTILOS ---
def load_css():
    st.markdown("""
        <style>
            /* Animación de hover para los libros en la biblioteca */
            .book-container {
                transition: transform 0.3s ease-in-out;
                border-radius: 10px;
                padding: 15px;
                border: 1px solid #eee;
            }
            .book-container:hover {
                transform: scale(1.05);
                box-shadow: 0 8px 30px rgba(0,0,0,0.12);
                border: 1px solid #ddd;
            }
            
            /* Animación para el spinner personalizado */
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(74, 144, 226, 0.7); }
                70% { box-shadow: 0 0 0 20px rgba(74, 144, 226, 0); }
                100% { box-shadow: 0 0 0 0 rgba(74, 144, 226, 0); }
            }
            .pulse-icon {
                font-size: 50px;
                animation: pulse 2s infinite;
                border-radius: 50%;
                display: inline-block;
                padding: 10px;
            }
        </style>
    """, unsafe_allow_html=True)

load_css()

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
    return pd.DataFrame(columns=['id', 'titulo', 'prompt_portada', 'contenido', 'ruta_portada'])

def guardar_libro(df):
    df.to_csv(CSV_FILE, index=False)
    
def borrar_libro(id_libro):
    df = cargar_libros()
    libro_a_borrar = df[df.id == id_libro]
    if not libro_a_borrar.empty:
        ruta_portada = libro_a_borrar.iloc[0]['ruta_portada']
        if os.path.exists(ruta_portada):
            os.remove(ruta_portada) # Borra el archivo de la imagen
    df = df[df.id != id_libro] # Elimina la fila del dataframe
    guardar_libro(df)

def generar_libro(prompt_usuario):
    model_texto = genai.GenerativeModel('gemini-1.5-pro-latest')
    mega_prompt = f"""
    Actúa como un maestro escritor de novelas. Tu tarea es tomar la siguiente idea y expandirla en un libro corto y completo.
    **Idea del Usuario:** "{prompt_usuario}"
    **Instrucciones:**
    1. **Título:** Crea un título atractivo y relevante.
    2. **Portada (Prompt):** Describe en una sola frase una escena visualmente impactante para la portada.
    3. **Contenido:** Escribe el libro dividido en 3 a 5 capítulos con sus títulos. Usa Markdown para formatear los títulos de los capítulos (ej. `### Capítulo 1: El Despertar`).
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
        # Placeholder que genera una imagen aleatoria. Aquí iría la llamada a DALL-E, Midjourney, etc.
        img = Image.new('RGB', (600, 800), color=(random.randint(0, 150), random.randint(0, 150), random.randint(0, 150)))
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
        col = cols[i % num_columnas]
        # MEJORA FASE 2: Contenedor para la animación de hover
        with col.container():
            # Convertir imagen a base64 para evitar recargas y mejorar rendimiento
            with open(libro.ruta_portada, "rb") as img_file:
                b64_string = base64.b64encode(img_file.read()).decode()
            
            # Usamos HTML para poder aplicar la clase CSS
            st.markdown(
                f"""
                <div class="book-container">
                    <h5 style="text-align: center;">{libro.titulo}</h5>
                    <img src="data:image/png;base64,{b64_string}" style="width: 100%;">
                </div>
                """,
                unsafe_allow_html=True
            )
            
            if st.button("📖 Abrir y Leer", key=f"read_{libro.id}", use_container_width=True):
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
    
    # MEJORA FASE 2: Diseño del lector más limpio
    col1, col2 = st.columns([0.4, 0.6])
    with col1:
        st.image(libro.ruta_portada)
        with st.expander("Opciones del Libro"):
            st.info(f"**Prompt de portada:** *{libro.prompt_portada}*")
            if st.button("🎨 Regenerar Portada", use_container_width=True):
                with st.spinner("Creando una nueva visión..."):
                    df = cargar_libros()
                    nueva_ruta = generar_y_guardar_portada(libro.prompt_portada, libro.id)
                    if nueva_ruta:
                        df.loc[df.id == libro.id, 'ruta_portada'] = nueva_ruta
                        guardar_libro(df)
                        st.success("¡Portada actualizada!")
                        st.rerun()
            
            # MEJORA FASE 1: Botón para borrar el libro
            if st.button("🗑️ Borrar Libro Permanentemente", type="primary", use_container_width=True):
                borrar_libro(libro.id)
                st.success(f"'{libro.titulo}' ha sido borrado.")
                st.session_state.view = 'library'
                st.session_state.selected_book_id = None
                time.sleep(1) # Pequeña pausa para leer el mensaje
                st.rerun()

    with col2:
        st.markdown(libro.contenido, unsafe_allow_html=True)

# MEJORA FASE 2: MODIFICACIÓN COMPLETA APLICADA
def mostrar_creador():
    st.header("Crear un Nuevo Libro")
    
    modo_creacion = st.radio(
        "¿Cómo quieres empezar tu historia?",
        ('A partir de una idea', 'Por género y personaje'),
        horizontal=True,
        label_visibility="collapsed"
    )
    prompt_final = ""

    if modo_creacion == 'A partir de una idea':
        idea_usuario = st.text_area("Escribe aquí tu idea:", height=150, key="idea_input", placeholder="Ej: Un faro en el fin del mundo que guía naves entre dimensiones...")
        prompt_final = idea_usuario
    else: # Modo 'Por género y personaje'
        col1, col2 = st.columns(2)
        with col1:
            genero = st.selectbox("Elige un género:", ["Fantasía Épica", "Ciencia Ficción", "Misterio Noir", "Aventura Juvenil", "Terror Cósmico", "Romance Histórico"])
        with col2:
            personaje = st.text_input("Nombre del protagonista:", "Kael")
        
        descripcion_extra = st.text_area("Añade algún detalle extra (opcional):", placeholder="Ej: un detective con miedo a la oscuridad, un mago que no sabe hacer magia...")
        
        prompt_final = f"Crea una historia del género '{genero}'. El protagonista se llama {personaje}. Considera este detalle adicional: {descripcion_extra}. Genera una sinopsis y luego el libro."

    if st.button("✨ ¡Crear mi libro!", type="primary", use_container_width=True):
        if prompt_final and prompt_final.strip():
            # MEJORA FASE 2: Spinner personalizado
            spinner_placeholder = st.empty()
            with spinner_placeholder.container():
                st.markdown("<p style='text-align: center;'>Forjando tu narrativa... ✍️</p>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center;'><span class='pulse-icon'>📖</span></p>", unsafe_allow_html=True)

            libro_texto = generar_libro(prompt_final)
            spinner_placeholder.empty() # Limpia la animación

            if libro_texto:
                try:
                    titulo = libro_texto.split("[TITULO]")[1].split("[/TITULO]")[0].strip()
                    prompt_portada = libro_texto.split("[PORTADA_PROMPT]")[1].split("[/PORTADA_PROMPT]")[0].strip()
                    contenido = libro_texto.split("[CONTENIDO]")[1].split("[/CONTENIDO]")[0].strip().replace('\n', '<br>')
                    id_libro = int(time.time())
                    
                    df = cargar_libros()
                    ruta_portada = generar_y_guardar_portada(prompt_portada, id_libro)
                    
                    if ruta_portada:
                        nuevo_libro = pd.DataFrame([{'id': id_libro, 'titulo': titulo, 'prompt_portada': prompt_portada, 'contenido': contenido, 'ruta_portada': ruta_portada}])
                        df = pd.concat([df, nuevo_libro], ignore_index=True)
                        guardar_libro(df)
                        st.success("¡Tu libro ha sido forjado!")
                        st.session_state.view = 'reader'
                        st.session_state.selected_book_id = id_libro
                        st.rerun()
                except IndexError:
                    st.error("La IA no devolvió el formato esperado. Inténtalo de nuevo con más detalle.")
        else:
            st.warning("Necesitas rellenar los campos para crear una historia.")

# --- LÓGICA PRINCIPAL DE LA APLICACIÓN ---
with st.sidebar:
    st.title("🚀 Panel de Creación")
    mostrar_creador()
    st.markdown("---")
    # MEJORA FASE 3: Visión de Producto más clara
    st.header("Producto")
    st.info("Créditos de Generación: 10/10")
    st.button("🖼️ Galería Comunitaria (Próximamente)", disabled=True, use_container_width=True)
    st.caption("Imagina un lugar donde compartir y descubrir historias creadas por otros usuarios.")

# Router principal
if st.session_state.view == 'library':
    mostrar_biblioteca()
elif st.session_state.view == 'reader':
    mostrar_lector()

