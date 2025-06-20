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

# --- FUNCIÓN DE INTERPRETACIÓN CLÍNICA ---
def get_progress_description(difference):
    """
    Asigna una descripción clínica e icono basado en la diferencia numérica.
    Retorna una tupla (icono, texto_descripcion).
    """
    if difference == "N/A" or difference == "Error":
        return " ", "No aplica. El paciente no fue evaluado por razones clínicas o porque ese ítem no está siendo trabajado."

    try:
        diff_val = float(difference)
    except (ValueError, TypeError):
        return " ", "No se pudo interpretar la diferencia."

    if diff_val < 0:
        return "🔻", "Regresión. Se ha observado un retroceso en este ítem."
    if diff_val == 0:
        return " ", "No presenta aumento. No se ha observado progreso en ese aspecto evaluado."

    # Si es positivo, el icono es verde y elegante.
    icon = "✅"
    
    # Mapeo de rangos de diferencia a descripciones
    if 1 <= diff_val <= 5.9:
        return icon, "Leve mejoría, apenas perceptible."
    elif 6 <= diff_val <= 10.9:
        return icon, "Mejora ligera, posiblemente inicial o marginal."
    elif 11 <= diff_val <= 15.9:
        return icon, "Mejora leve pero ya observable."
    elif 16 <= diff_val <= 20.9:
        return icon, "Progreso clínicamente moderado."
    elif 21 <= diff_val <= 25.9:
        return icon, "Mejora establecida, aunque todavía moderada."
    elif 26 <= diff_val <= 30.9:
        return icon, "Progreso consistente y significativo."
    elif 31 <= diff_val <= 35.9:
        return icon, "Mejora marcada, buen avance terapéutico."
    elif 36 <= diff_val <= 40.9:
        return icon, "Progreso importante."
    elif 41 <= diff_val <= 45.9:
        return icon, "Avance clínicamente sólido."
    elif 46 <= diff_val <= 50.9:
        return icon, "Mejora significativa, cercana a la mitad del máximo esperado."
    elif 51 <= diff_val <= 55.9:
        return icon, "Ya se supera la mitad del potencial de mejora."
    elif 56 <= diff_val <= 60.9:
        return icon, "Mejora clara y continua."
    elif 61 <= diff_val <= 65.9:
        return icon, "Alto nivel de progreso."
    elif 66 <= diff_val <= 70.9:
        return icon, "Progreso muy destacado."
    elif 71 <= diff_val <= 75.9:
        return icon, "El paciente se acerca al máximo de mejora posible."
    elif 76 <= diff_val <= 80.9:
        return icon, "Gran mejora, resultado clínicamente excelente."
    elif 81 <= diff_val <= 85.9:
        return icon, "Alta recuperación o efectividad del tratamiento."
    elif 86 <= diff_val <= 90.9:
        return icon, "Nivel casi óptimo."
    elif 91 <= diff_val <= 95.9:
        return icon, "Progreso casi completo."
    elif 96 <= diff_val <= 100:
        return icon, "Mejora máxima alcanzada según los ítems evaluados."
    else:
        return icon, "Progreso positivo no categorizado."


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
        df = pd.DataFrame(data)
        
        def extract_name_from_hyperlink(formula):
            if isinstance(formula, str):
                match = re.search(r'";"([^"]+)"\)', formula)
                return match.group(1) if match else formula
            return formula

        df['Nombre Limpio'] = df['Nombre Paciente'].apply(extract_name_from_hyperlink)
        
        columnas_datos = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo', 'Nombre Limpio']]
        for col in columnas_datos:
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
    
    unique_patients_df = df[['Nombre Limpio', 'Identificación']].drop_duplicates()
    unique_patients_df['display_label'] = unique_patients_df['Nombre Limpio'] + " (" + unique_patients_df['Identificación'].astype(str) + ")"
    patient_options = unique_patients_df['display_label'].tolist()
    
    st.header("1. Seleccionar Paciente")
    selected_patient_label = st.selectbox(
        "Escribe un nombre o identificación para buscar y seleccionar un paciente:",
        options=patient_options,
        index=None,
        placeholder="Elige un paciente..."
    )

    if selected_patient_label:
        selected_id = unique_patients_df[unique_patients_df['display_label'] == selected_patient_label]['Identificación'].iloc[0]
        patient_records = df[df['Identificación'] == selected_id]
        patient_name = unique_patients_df[unique_patients_df['display_label'] == selected_patient_label]['Nombre Limpio'].iloc[0]
        
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
                
                def extract_url_from_hyperlink(formula):
                    match = re.search(r'HYPERLINK\("([^"]+)"', formula)
                    return match.group(1) if match else "#"
                
                url_comp = extract_url_from_hyperlink(record_comp['Nombre Paciente'])
                url_evol = extract_url_from_hyperlink(record_evol['Nombre Paciente'])

                st.write(f"Comparando la valoración de **{fecha_comparativa}** ([ver PDF]({url_comp})) con la de **{fecha_evolutiva}** ([ver PDF]({url_evol})).")
                st.markdown("---")

                columnas_analisis = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo', 'Nombre Limpio']]

                for col in columnas_analisis:
                    val_comp = record_comp[col]
                    val_evol = record_evol[col]
                    
                    diferencia = "N/A"
                    if val_comp != "N/A" and val_evol != "N/A":
                        try:
                            # Calcular la diferencia con decimales
                            diferencia = round(float(val_evol) - float(val_comp), 2)
                        except (ValueError, TypeError):
                            diferencia = "Error"
                    
                    # Mostrar el título de la etiqueta de forma destacada
                    st.markdown(f"#### {col}")

                    # Mostrar los valores y la diferencia en columnas
                    v_col1, v_col2, v_col3 = st.columns(3)
                    with v_col1:
                        st.metric(label=f"Valor ({fecha_comparativa})", value=val_comp)
                    with v_col2:
                        st.metric(label=f"Valor ({fecha_evolutiva})", value=val_evol)
                    with v_col3:
                        st.metric(label="Diferencia", value=diferencia)

                    # Obtener y mostrar la descripción con el ícono
                    icon, desc_text = get_progress_description(diferencia)
                    
                    if icon == "✅":
                        st.markdown(f"> :green[{icon} {desc_text}]")
                    elif icon == "🔻":
                        st.markdown(f"> :red[{icon} {desc_text}]")
                    else:
                        st.markdown(f"> {desc_text}")
                    
                    st.markdown("---") # Separador para el siguiente ítem

else:
    st.info("La aplicación no puede cargar los datos. Por favor, contacta al administrador.")
