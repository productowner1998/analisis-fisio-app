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

# --- FUNCIÓN PARA APLICAR ESTILO DE COLOR ---
def style_difference(val):
    """
    Aplica un color sutil a los valores de diferencia.
    Verde para positivo, Rojo para negativo. 0 y N/A se ignoran.
    """
    color = 'inherit' # Color por defecto
    try:
        val_float = float(val)
        if val_float > 0:
            color = '#28a745'  # Verde sutil
        elif val_float < 0:
            color = '#dc3545'  # Rojo sutil
    except (ValueError, TypeError):
        pass # Se mantiene el color por defecto para 'N/A' o 'Error'
    return f'color: {color}'

# --- FUNCIÓN PARA FORMATEAR LA DIFERENCIA ---
def format_difference(val):
    """
    Formatea la diferencia para mostrarla como un entero, manejando N/A.
    """
    if val == "N/A" or val == "Error":
        return val
    try:
        # Formatea como entero sin decimales
        return f"{int(val):d}"
    except (ValueError, TypeError):
        return '' # Devuelve vacío si no se puede convertir (no debería pasar)

# --- CONEXIÓN A GOOGLE SHEETS Y CARGA DE DATOS ---
try:
    credentials_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    
    SPREADSHEET_NAME = "Resultados Informes Fisioterapia" 
    sheet = client.open(SPREADSHEET_NAME).sheet1
    
    @st.cache_data(ttl=600)
    def load_data():
        # Obtenemos los valores como texto visible, no como fórmulas
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # Asegurar que la columna de Identificación sea de tipo string y sin espacios extra
        df['Identificación'] = df['Identificación'].astype(str).str.strip()

        # Convertir columnas de datos a tipo numérico y luego a entero (manejando N/A)
        columnas_datos = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo']]
        for col in columnas_datos:
             numeric_col = pd.to_numeric(df[col], errors='coerce')
             df[col] = numeric_col.astype('Int64')
        return df

    df = load_data()
    data_loaded_successfully = not df.empty
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.error("Asegúrate de haber configurado los 'Secrets' en Streamlit Cloud y compartido la hoja de cálculo con el email del servicio.")
    data_loaded_successfully = False

# --- INTERFAZ DE USUARIO (UI) ---

st.title("📊 Herramienta de Análisis de Evolución")
st.write("Esta aplicación te permite comparar dos valoraciones de un paciente para analizar su progreso.")

if data_loaded_successfully:
    
    # Crear una lista de pacientes únicos para el dropdown
    unique_patients_df = df[['Nombre Paciente', 'Identificación']].dropna().drop_duplicates()
    unique_patients_df['display_label'] = unique_patients_df['Nombre Paciente'] + " (" + unique_patients_df['Identificación'].astype(str) + ")"
    patient_options = sorted(unique_patients_df['display_label'].tolist())
    
    st.header("1. Seleccionar Paciente")
    selected_patient_label = st.selectbox(
        "Escribe un nombre o identificación para buscar y seleccionar un paciente:",
        options=patient_options,
        index=None,
        placeholder="Elige un paciente..."
    )

    if selected_patient_label:
        # Extraer el ID de la etiqueta del dropdown
        match = re.search(r'\((\d+)\)', selected_patient_label)
        if match:
            selected_id_str = match.group(1)
            
            # Filtrar el DataFrame principal usando el ID extraído
            patient_records = df[df['Identificación'] == selected_id_str]
            patient_name = unique_patients_df[unique_patients_df['display_label'] == selected_patient_label]['Nombre Paciente'].iloc[0]
            
            st.success(f"Paciente seleccionado: **{patient_name}**")

            st.header("2. Seleccionar Periodos de Comparación")
            available_periods = patient_records['Periodo'].unique().tolist()

            col1, col2 = st.columns(2)
            with col1:
                fecha_comparativa = st.selectbox("Fecha Comparativa (punto de partida)", options=available_periods, index=None, placeholder="Elige una fecha")
            with col2:
                fecha_evolutiva = st.selectbox("Fecha Evolutiva (reciente)", options=available_periods, index=None, placeholder="Elige una fecha")
            
            st.header("3. Ejecutar Análisis")
            if st.button("Analizar Progreso", disabled=not (fecha_comparativa and fecha_evolutiva)):
                if fecha_comparativa == fecha_evolutiva:
                    st.warning("Por favor, selecciona dos fechas diferentes para la comparación.")
                else:
                    record_comp = patient_records[patient_records['Periodo'] == fecha_comparativa].iloc[0]
                    record_evol = patient_records[patient_records['Periodo'] == fecha_evolutiva].iloc[0]

                    st.subheader("Resultados del Análisis")
                    
                    st.write(f"Comparando la valoración de **{fecha_comparativa}** con la de **{fecha_evolutiva}**.")
                    
                    resultados = []
                    columnas_analisis = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo']]

                    for col in columnas_analisis:
                        val_comp = record_comp[col]
                        val_evol = record_evol[col]
                        
                        display_comp = "N/A" if pd.isna(val_comp) else int(val_comp)
                        display_evol = "N/A" if pd.isna(val_evol) else int(val_evol)

                        diferencia = "N/A"
                        if pd.notna(val_comp) and pd.notna(val_evol):
                            try:
                                diferencia = int(val_evol) - int(val_comp)
                            except (ValueError, TypeError):
                                diferencia = "Error"
                        
                        resultados.append({
                            "Etiqueta": col,
                            f"Valor ({fecha_comparativa})": display_comp,
                            f"Valor ({fecha_evolutiva})": display_evol,
                            "Diferencia (Evolutiva - Comparativa)": diferencia
                        })
                    
                    df_resultados = pd.DataFrame(resultados).set_index("Etiqueta")
                    
                    # *** LÍNEA CORREGIDA ***
                    # Se usa un formateador personalizado para asegurar que el 0 se muestre.
                    st.dataframe(df_resultados.style.format(
                        formatter={"Diferencia (Evolutiva - Comparativa)": format_difference}
                    ).apply(
                        lambda x: x.map(style_difference), subset=['Diferencia (Evolutiva - Comparativa)']
                    ))
    else:
        pass
else:
    st.info("La aplicación no puede cargar los datos. Por favor, contacta al administrador.")
