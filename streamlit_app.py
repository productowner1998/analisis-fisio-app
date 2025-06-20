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
    Verde para positivo, Rojo para negativo.
    """
    color = 'black' # Color por defecto
    try:
        val_float = float(val)
        if val_float > 0:
            color = '#28a745'  # Verde sutil
        elif val_float < 0:
            color = '#dc3545'  # Rojo sutil
    except (ValueError, TypeError):
        pass # Se mantiene el color por defecto para 'N/A' o 'Error'
    return f'color: {color}'

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
        # Obtenemos los valores con las FÓRMULAS para poder extraer los hipervínculos
        all_values = sheet.get_all_values(value_render_option='FORMULA')
        headers = all_values[0]
        data = all_values[1:]
        df = pd.DataFrame(data, columns=headers)
        
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
                    if isinstance(formula, str):
                        match = re.search(r'HYPERLINK\("([^"]+)"', formula)
                        return match.group(1) if match else "#"
                    return "#"
                
                url_comp = extract_url_from_hyperlink(record_comp['Nombre Paciente'])
                url_evol = extract_url_from_hyperlink(record_evol['Nombre Paciente'])

                st.write(f"Comparando la valoración de **{fecha_comparativa}** ([ver PDF]({url_comp})) con la de **{fecha_evolutiva}** ([ver PDF]({url_evol})).")
                
                resultados = []
                columnas_analisis = [col for col in df.columns if col not in ['Nombre Archivo', 'Nombre Paciente', 'Identificación', 'Periodo', 'Nombre Limpio']]

                for col in columnas_analisis:
                    val_comp = record_comp[col]
                    val_evol = record_evol[col]
                    
                    diferencia = "N/A"
                    if val_comp != "N/A" and val_evol != "N/A":
                        try:
                            diferencia = round(float(val_evol) - float(val_comp), 2)
                        except (ValueError, TypeError):
                            diferencia = "Error"
                    
                    resultados.append({
                        "Etiqueta": col,
                        f"Valor ({fecha_comparativa})": val_comp,
                        f"Valor ({fecha_evolutiva})": val_evol,
                        "Diferencia (Evolutiva - Comparativa)": diferencia
                    })
                
                df_resultados = pd.DataFrame(resultados).set_index("Etiqueta")
                
                # Aplicar el estilo de color y mostrar la tabla compacta
                st.dataframe(df_resultados.style.applymap(style_difference, subset=['Diferencia (Evolutiva - Comparativa)']))

else:
    st.info("La aplicación no puede cargar los datos. Por favor, contacta al administrador.")
