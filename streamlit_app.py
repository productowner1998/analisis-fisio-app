import streamlit as st
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Análisis de Evolución de Pacientes",
    page_icon="📊",
    layout="wide"
)

# --- CONEXIÓN A GOOGLE SHEETS (Usa los secretos de Streamlit para más seguridad) ---
try:
    credentials_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)

    # Reemplaza con el nombre exacto de tu hoja de cálculo
    SPREADSHEET_NAME = "extraccion_fisioterapia_datos" 
    sheet = client.open(SPREADSHEET_NAME).sheet1

    # Cargar datos en un DataFrame de pandas
    @st.cache_data(ttl=600) # Cache por 10 minutos
    def load_data():
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        # Convertir columnas numéricas, manejando N/A y otros no números
        for col in df.columns[4:]: # Asume que las columnas de datos empiezan en la 5ta posición
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna('N/A')
        return df

    df = load_data()
    data_loaded_successfully = True
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.error("Asegúrate de haber configurado los 'Secrets' en Streamlit Cloud y compartido la hoja de cálculo con el email del servicio.")
    data_loaded_successfully = False

# --- INTERFAZ DE USUARIO (UI) ---

st.title("📊 Herramienta de Análisis de Evolución")
st.write("Esta aplicación te permite comparar dos valoraciones de un paciente para analizar su progreso.")

if data_loaded_successfully:
    # --- 1. BÚSQUEDA DE PACIENTE ---
    st.header("1. Buscar Paciente")
    search_id = st.text_input("Ingresa el número de identificación del paciente:")

    if search_id:
        # Filtrar el DataFrame para encontrar al paciente
        patient_records = df[df['Identificación'].astype(str) == str(search_id)]

        if not patient_records.empty:
            patient_name_formula = patient_records['Nombre Paciente'].iloc[0]

            # Extraer nombre visible del hipervínculo
            def extract_name_from_hyperlink(formula):
                match = re.search(r'";"([^"]+)"\)', formula)
                return match.group(1) if match else "Nombre no encontrado"

            patient_name = extract_name_from_hyperlink(patient_name_formula)
            st.success(f"Paciente encontrado: **{patient_name}**")

            # --- 2. SELECCIÓN DE FECHAS ---
            st.header("2. Seleccionar Periodos de Comparación")

            # Obtener los periodos disponibles para este paciente
            available_periods = patient_records['Periodo'].unique().tolist()

            col1, col2 = st.columns(2)
            with col1:
                fecha_comparativa = st.selectbox("Fecha Comparativa (punto de partida)", options=available_periods, index=None, placeholder="Elige una fecha")
            with col2:
                fecha_evolutiva = st.selectbox("Fecha Evolutiva (reciente)", options=available_periods, index=None, placeholder="Elige una fecha")

            # --- 3. ANÁLISIS ---
            if fecha_comparativa and fecha_evolutiva:
                st.header("3. Ejecutar Análisis")
                if st.button("Analizar Progreso"):
                    if fecha_comparativa == fecha_evolutiva:
                        st.warning("Por favor, selecciona dos fechas diferentes para la comparación.")
                    else:
                        # Obtener los registros completos para cada fecha
                        record_comp = patient_records[patient_records['Periodo'] == fecha_comparativa].iloc[0]
                        record_evol = patient_records[patient_records['Periodo'] == fecha_evolutiva].iloc[0]

                        st.subheader("Resultados del Análisis")

                        # Extraer el hipervínculo para mostrarlo
                        def extract_url_from_hyperlink(formula):
                            match = re.search(r'HYPERLINK\("([^"]+)"', formula)
                            return match.group(1) if match else "#"

                        url_comp = extract_url_from_hyperlink(record_comp['Nombre Paciente'])
                        url_evol = extract_url_from_hyperlink(record_evol['Nombre Paciente'])

                        st.write(f"Comparando la valoración de **{fecha_comparativa}** ([ver PDF]({url_comp})) con la de **{fecha_evolutiva}** ([ver PDF]({url_evol})).")

                        # Crear tabla de resultados
                        resultados = []
                        columnas_analisis = df.columns[4:] # Asume que estas son las columnas de etiquetas

                        for col in columnas_analisis:
                            val_comp = record_comp[col]
                            val_evol = record_evol[col]

                            diferencia = "N/A"
                            if val_comp != "N/A" and val_evol != "N/A":
                                try:
                                    diferencia = float(val_evol) - float(val_comp)
                                except (ValueError, TypeError):
                                    diferencia = "Error"

                            resultados.append({
                                "Etiqueta": col,
                                f"Valor ({fecha_comparativa})": val_comp,
                                f"Valor ({fecha_evolutiva})": val_evol,
                                "Diferencia (Evolutiva - Comparativa)": diferencia
                            })

                        df_resultados = pd.DataFrame(resultados)
                        st.dataframe(df_resultados)
        else:
            st.warning("No se encontraron registros para la identificación ingresada. Por favor, verifica el número.")
else:
    st.info("La aplicación no puede cargar los datos. Por favor, contacta al administrador.")
