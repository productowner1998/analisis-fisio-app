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
    Aplica color a los valores de diferencia.
    Verde para positivo, Rojo para negativo. 0 y N/A se ignoran.
    """
    color = 'inherit' # Color por defecto
    try:
        val_float = float(val)
        if val_float > 0:
            color = 'green'
        elif val_float < 0:
            color = 'red'
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
        return '' # Devuelve vacío si no se puede convertir

# --- FUNCIÓN PARA OBTENER EL ANÁLISIS CLÍNICO ---
def get_analysis_description(difference):
    """
    Asigna una descripción clínica basada en la diferencia numérica.
    """
    if difference == "N/A" or difference == "Error":
        return "No aplica. El paciente no fue evaluado por razones clínicas o porque ese ítem no está siendo trabajado."

    try:
        diff_val = float(difference)
    except (ValueError, TypeError):
        return "No se pudo interpretar la diferencia."

    if diff_val < 0:
        return "No presenta aumento. No se ha observado progreso en ese aspecto evaluado."
    if diff_val == 0:
        return "No presenta aumento. No se ha observado progreso en ese aspecto evaluado."

    if 0.5 <= diff_val <= 5.9: return "Leve mejoría, apenas perceptible."
    if 6 <= diff_val <= 10.9: return "Mejora ligera, posiblemente inicial o marginal."
    if 11 <= diff_val <= 15.9: return "Mejora leve pero ya observable."
    if 16 <= diff_val <= 20.9: return "Progreso clínicamente moderado."
    if 21 <= diff_val <= 25.9: return "Mejora establecida, aunque todavía moderada."
    if 26 <= diff_val <= 30.9: return "Progreso consistente y significativo."
    if 31 <= diff_val <= 35.9: return "Mejora marcada, buen avance terapéutico."
    if 36 <= diff_val <= 40.9: return "Progreso importante."
    if 41 <= diff_val <= 45.9: return "Avance clínicamente sólido."
    if 46 <= diff_val <= 50.9: return "Mejora significativa, cercana a la mitad del máximo esperado."
    if 51 <= diff_val <= 55.9: return "Ya se supera la mitad del potencial de mejora."
    if 56 <= diff_val <= 60.9: return "Mejora clara y continua."
    if 61 <= diff_val <= 65.9: return "Alto nivel de progreso."
    if 66 <= diff_val <= 70.9: return "Progreso muy destacado."
    if 71 <= diff_val <= 75.9: return "El paciente se acerca al máximo de mejora posible."
    if 76 <= diff_val <= 80.9: return "Gran mejora, resultado clínicamente excelente."
    if 81 <= diff_val <= 85.9: return "Alta recuperación o efectividad del tratamiento."
    if 86 <= diff_val <= 90.9: return "Nivel casi óptimo."
    if 91 <= diff_val <= 95.9: return "Progreso casi completo."
    if 96 <= diff_val <= 100: return "Mejora máxima alcanzada según los ítems evaluados."
    
    return "Progreso positivo no categorizado."

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
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df['Identificación'] = df['Identificación'].astype(str).str.strip()
        columnas_datos = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo', 'URL_PDF']]
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
        match = re.search(r'\((\d+)\)', selected_patient_label)
        if match:
            selected_id_str = match.group(1)
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
                    
                    url_comp = record_comp.get('URL_PDF', '#')
                    url_evol = record_evol.get('URL_PDF', '#')
                    
                    st.write(f"Comparando la valoración de **{fecha_comparativa}** ([ver PDF]({url_comp})) con la de **{fecha_evolutiva}** ([ver PDF]({url_evol})).")
                    
                    resultados = []
                    columnas_analisis = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo', 'URL_PDF']]

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
                        
                        analisis = get_analysis_description(diferencia)

                        resultados.append({
                            "Etiqueta": col,
                            f"Valor ({fecha_comparativa})": display_comp,
                            f"Valor ({fecha_evolutiva})": display_evol,
                            "Diferencia": diferencia,
                            "Análisis": analisis
                        })
                    
                    df_resultados = pd.DataFrame(resultados).set_index("Etiqueta")
                    
                    # *** CAMBIO: Se usa st.dataframe con configuración de columnas para un mejor layout ***
                    st.dataframe(
                        df_resultados.style.format(formatter={"Diferencia": format_difference}).apply(lambda x: x.map(style_difference), subset=['Diferencia']),
                        column_config={
                            f"Valor ({fecha_comparativa})": st.column_config.TextColumn(width="small"),
                            f"Valor ({fecha_evolutiva})": st.column_config.TextColumn(width="small"),
                            "Diferencia": st.column_config.TextColumn(width="small"),
                            "Análisis": st.column_config.TextColumn(width="large"),
                        },
                        use_container_width=True
                    )
    else:
        pass
else:
    st.info("La aplicación no puede cargar los datos. Por favor, contacta al administrador.")
