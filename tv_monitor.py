# ============================================================
# DIL-Salud — Monitor de Cartelería Digital para Smart TV v2
# ============================================================
# Interfaz diseñada para proyectarse de forma estática en Smart TV o Chromecast.
# Cero interacción, autorefresco de 5 minutos, diseño de aeropuerto.
# ============================================================

import os
import re
import json
import base64
from datetime import datetime, date, timezone, timedelta
from calendar import monthrange

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
from streamlit_autorefresh import st_autorefresh

# ============================================================
# 1. CONFIGURACIÓN DE PÁGINA (Sin barra lateral)
# ============================================================
st.set_page_config(
    page_title="FAUJIDA | Monitor TV",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}

# ============================================================
# 2. ESTILOS CSS — Cartelería Digital Sin Interacción (Cero Menús)
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0f172a; /* Fondo ultra oscuro para alto contraste */
        color: #f8fafc;
    }

    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    
    /* Quitar padding de Streamlit */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* Cabecera del Monitor */
    .monitor-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #1e293b;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .monitor-title {
        font-size: 30px;
        font-weight: 800;
        color: #38bdf8; /* Celeste moderno */
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0;
    }
    .monitor-timeinfo {
        text-align: right;
    }
    .timeinfo-date {
        font-size: 18px;
        font-weight: 700;
        color: #f1f5f9;
        margin: 0;
    }
    .timeinfo-refresh {
        font-size: 13px;
        color: #64748b;
        margin: 1px 0 0 0;
        font-weight: 600;
    }

    /* Columnas Estilo Aeropuerto */
    .tv-col-header {
        text-align: center;
        font-size: 22px;
        font-weight: 800;
        padding: 8px;
        border-radius: 8px;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
    }
    .tv-col-header.green {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 2px solid rgba(16, 185, 129, 0.3);
    }
    .tv-col-header.red {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 2px solid rgba(239, 68, 68, 0.3);
    }
    .tv-col-header.grey {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 2px solid rgba(245, 158, 11, 0.3);
    }

    /* Subcabecera de Turno (Pills) */
    .turno-sub-header {
        font-size: 13px;
        font-weight: 800;
        color: #94a3b8;
        background-color: #1e293b;
        padding: 4px 12px;
        border-radius: 20px;
        margin-top: 10px;
        margin-bottom: 8px;
        border: 1px solid #334155;
        display: inline-block;
        letter-spacing: 0.5px;
    }

    /* Tarjetas de Pacientes (Diseño Compacto para evitar scroll) */
    .tv-card {
        background-color: #1e293b;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 5px solid #64748b;
    }
    .tv-card.green {
        border-left-color: #10b981;
    }
    .tv-card.red {
        border-left-color: #ef4444;
    }
    .tv-card.grey {
        border-left-color: #f59e0b; /* Amarillo/Naranja en espera */
    }
    
    .tv-patient-name {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        line-height: 1.2;
    }
    .tv-patient-details {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 4px;
        font-weight: 600;
        display: flex;
        justify-content: space-between;
    }

    /* Footer Fijo en Pantalla */
    .tv-footer {
        position: fixed;
        bottom: 12px;
        right: 24px;
        font-size: 13px;
        color: #64748b;
        font-weight: 700;
        z-index: 999;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. REFRESH AUTOMÁTICO INTELIGENTE
# ============================================================
# Horario de Argentina (UTC-3)
tz_arg = timezone(timedelta(hours=-3))
ahora_arg = datetime.now(tz_arg)
hoy_arg = ahora_arg.date()

# De lunes a sábado (weekday <= 5), de 05:00 hs a 18:00 hs
es_operativo = (ahora_arg.weekday() <= 5) and (5 <= ahora_arg.hour < 18)

if es_operativo:
    # 5 minutos (300,000 ms) en horario de clínica
    st_autorefresh(interval=300000, key="tv_autorefresh")
else:
    # 30 minutos (1,800,000 ms) fuera de horario operativo
    st_autorefresh(interval=1800000, key="tv_autorefresh_slow")

# ============================================================
# 4. CONEXIÓN A GOOGLE SHEETS (OAuth2)
# ============================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
_AUTH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit")
_AUTHORIZED_USER = os.path.join(_AUTH_DIR, "authorized_user.json")

def _cargar_credenciales_oauth():
    try:
        auth_info = dict(st.secrets["oauth_credentials"])
        return OAuthCredentials(
            token=auth_info.get("token"),
            refresh_token=auth_info.get("refresh_token"),
            token_uri=auth_info.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=auth_info.get("client_id"),
            client_secret=auth_info.get("client_secret"),
            scopes=SCOPES,
        )
    except (KeyError, FileNotFoundError):
        pass

    if not os.path.exists(_AUTHORIZED_USER):
        st.error("❌ Credenciales OAuth no encontradas.")
        st.stop()

    with open(_AUTHORIZED_USER, "r") as f:
        auth_info = json.load(f)

    return OAuthCredentials(
        token=auth_info.get("token"),
        refresh_token=auth_info.get("refresh_token"),
        token_uri=auth_info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=auth_info.get("client_id"),
        client_secret=auth_info.get("client_secret"),
        scopes=SCOPES,
    )

def cargar_datos_tv_limpios():
    creds = _cargar_credenciales_oauth()
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(st.secrets["google_sheets"]["spreadsheet_url"])

    nombres = ["ASISTENCIA_DIARIA", "PACIENTE", "CRONOGRAMA", "EXCEPCIONES"]
    hojas = {}
    for nombre in nombres:
        try:
            hojas[nombre] = pd.DataFrame(spreadsheet.worksheet(nombre).get_all_records())
        except gspread.exceptions.WorksheetNotFound:
            hojas[nombre] = pd.DataFrame()
            st.error(f"⚠️ Hoja {nombre} no encontrada.")
            st.stop()
    return hojas

try:
    hojas = cargar_datos_tv_limpios()
except Exception as e:
    st.error(f"❌ Error al conectar con Google Sheets: {e}")
    st.stop()

df_cron = hojas["CRONOGRAMA"]
df_exc = hojas["EXCEPCIONES"]
df_pac = hojas["PACIENTE"]
df_asis = hojas["ASISTENCIA_DIARIA"]

# ============================================================
# 5. MOTOR DE CÁLCULO DIARIO
# ============================================================
def calcular_universo_diario(fecha_sel, df_cron, df_exc, df_pac, df_asis):
    dia_semana = DIAS_SEMANA[fecha_sel.weekday()]
    fecha_str = fecha_sel.strftime("%d/%m/%Y")

    if df_cron.empty:
        fijos = pd.DataFrame()
    else:
        c = df_cron.copy()
        c["_d"] = c["Día_Semana"].astype(str).str.strip().str.lower()
        fijos = c[c["_d"] == dia_semana.lower()].drop(columns=["_d"])

    cancel_ids, agregados = set(), pd.DataFrame()
    if not df_exc.empty:
        ex = df_exc.copy()
        ex["_f"] = ex["Fecha_Exacta"].astype(str).str.strip()
        ex["_t"] = ex["Tipo_Modificacion"].astype(str).str.strip()
        cancel_ids = set(
            ex.loc[(ex["_f"] == fecha_str) & (ex["_t"] == "CANCELA VIAJE FIJO"), "ID_Paciente"]
            .astype(str).str.strip()
        )
        agregados = ex[(ex["_f"] == fecha_str) & (ex["_t"] == "AGREGA VIAJE")]

    if not fijos.empty and cancel_ids:
        fijos = fijos[~fijos["ID_Paciente"].astype(str).str.strip().isin(cancel_ids)]

    registros = []
    for _, r in fijos.iterrows():
        registros.append({
            "ID_Paciente": str(r.get("ID_Paciente", "")).strip(),
            "Turno": str(r.get("Turno", "")).strip(),
            "Móvil": str(r.get("Móvil_Asignado", "")).strip(),
            "Origen": "Fijo",
        })
    for _, r in agregados.iterrows():
        registros.append({
            "ID_Paciente": str(r.get("ID_Paciente", "")).strip(),
            "Turno": str(r.get("Turno", "")).strip(),
            "Móvil": str(r.get("Móvil_Asignado", "")).strip(),
            "Origen": "Extra",
        })

    cols = ["Móvil", "Turno", "ID_Paciente", "Nombre", "Destino",
            "Asistencia", "Observaciones", "Hora", "Origen"]

    if not registros:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(registros)

    if not df_pac.empty:
        p = df_pac.copy()
        p["_id"] = p["ID_Paciente"].astype(str).str.strip()
        p = p.rename(columns={"Nombre_Paciente": "Nombre", "Centro_Hemoterapia": "Destino"})
        df = df.merge(p[["_id", "Nombre", "Destino"]], left_on="ID_Paciente",
                      right_on="_id", how="left").drop(columns=["_id"])

    df["Nombre"] = df.get("Nombre", pd.Series(dtype=str)).fillna("Desconocido")
    df["Destino"] = df.get("Destino", pd.Series(dtype=str)).fillna("Sin destino")
    df["Asistencia"] = "Pendiente"
    df["Observaciones"] = ""
    df["Hora"] = ""

    if not df_asis.empty:
        a = df_asis.copy()
        a["_f"] = a["Fecha_Servicio"].astype(str).str.strip()
        a["_id"] = a["ID_Paciente"].astype(str).str.strip()
        a["_t"] = a["Turno"].astype(str).str.strip()
        ah = a[a["_f"] == fecha_str]

        for idx, row in df.iterrows():
            reg = ah[(ah["_id"] == row["ID_Paciente"]) & (ah["_t"] == row["Turno"])]
            if reg.empty:
                continue
            r = reg.iloc[0]
            estado = str(r.get("Estado", "")).strip().upper()
            df.at[idx, "Asistencia"] = "Presente" if estado in ("TRUE", "VERDADERO", "1", "SI", "SÍ") else "Ausente"
            df.at[idx, "Observaciones"] = str(r.get("Observaciones", "")).strip()
            m = re.search(r"(\d{1,2}):(\d{2})", str(r.get("Marca_Temporal", "")))
            if m:
                df.at[idx, "Hora"] = f"{m.group(1).zfill(2)}:{m.group(2)}"

    return df[cols].sort_values(["Móvil", "Turno", "Nombre"]).reset_index(drop=True)

# Calcular el universo operativo de hoy
df_hoy = calcular_universo_diario(hoy_arg, df_cron, df_exc, df_pac, df_asis)

# ============================================================
# 6. HEADER DEL MONITOR (FAUJIDA)
# ============================================================
fecha_label = f"{hoy_arg.strftime('%d/%m/%Y')} — {DIAS_SEMANA[hoy_arg.weekday()]}"
actualizado_label = ahora_arg.strftime("%H:%M:%S")

st.markdown(
    f"""
    <div class="monitor-header">
        <div class="monitor-title">
            <span>🏥</span> FAUJIDA — Monitor de Recepción
        </div>
        <div class="monitor-timeinfo">
            <div class="timeinfo-date">{fecha_label}</div>
            <div class="timeinfo-refresh">Actualizado: {actualizado_label}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# 7. MAQUETADO DE GRILLA DE AEROPUERTO (Vista Unificada)
# ============================================================
if df_hoy.empty:
    st.info("No hay traslados programados para el día de hoy.")
else:
    col_presente, col_ausente, col_pendiente = st.columns(3)
    
    # 1. EN CAMINO (Presente)
    with col_presente:
        st.markdown('<div class="tv-col-header green">🟢 EN CAMINO</div>', unsafe_allow_html=True)
        for turno_name in ["Turno 1", "Turno 2", "Turno 3"]:
            df_t = df_hoy[(df_hoy["Turno"] == turno_name) & (df_hoy["Asistencia"] == "Presente")]
            if not df_t.empty:
                st.markdown(f'<div class="turno-sub-header">{turno_name.upper()}</div>', unsafe_allow_html=True)
                for _, r in df_t.iterrows():
                    nombre = r["Nombre"]
                    movil = r["Móvil"]
                    hora = f" ({r['Hora']})" if r["Hora"] else ""
                    st.markdown(
                        f"""
                        <div class="tv-card green">
                            <p class="tv-patient-name">{nombre}</p>
                            <div class="tv-patient-details">
                                <span>Vehículo: {movil}</span>
                                <span>Hora: {hora if hora else 'En camino'}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
    # 2. NO ASISTE (Ausente)
    with col_ausente:
        st.markdown('<div class="tv-col-header red">🔴 NO ASISTE</div>', unsafe_allow_html=True)
        for turno_name in ["Turno 1", "Turno 2", "Turno 3"]:
            df_t = df_hoy[(df_hoy["Turno"] == turno_name) & (df_hoy["Asistencia"] == "Ausente")]
            if not df_t.empty:
                st.markdown(f'<div class="turno-sub-header">{turno_name.upper()}</div>', unsafe_allow_html=True)
                for _, r in df_t.iterrows():
                    nombre = r["Nombre"]
                    movil = r["Móvil"]
                    obs = f" — {r['Observaciones']}" if r["Observaciones"] else ""
                    st.markdown(
                        f"""
                        <div class="tv-card red">
                            <p class="tv-patient-name">{nombre}</p>
                            <div class="tv-patient-details">
                                <span>Vehículo: {movil}</span>
                                <span>{obs if obs else 'Cancelado'}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
    # 3. EN ESPERA (Pendiente)
    with col_pendiente:
        st.markdown('<div class="tv-col-header grey">🟡 EN ESPERA</div>', unsafe_allow_html=True)
        for turno_name in ["Turno 1", "Turno 2", "Turno 3"]:
            df_t = df_hoy[(df_hoy["Turno"] == turno_name) & (df_hoy["Asistencia"] == "Pendiente")]
            if not df_t.empty:
                st.markdown(f'<div class="turno-sub-header">{turno_name.upper()}</div>', unsafe_allow_html=True)
                for _, r in df_t.iterrows():
                    nombre = r["Nombre"]
                    movil = r["Móvil"]
                    destino = r["Destino"]
                    st.markdown(
                        f"""
                        <div class="tv-card grey">
                            <p class="tv-patient-name">{nombre}</p>
                            <div class="tv-patient-details">
                                <span>Vehículo: {movil}</span>
                                <span>Destino: {destino}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

# ============================================================
# 8. FOOTER FIJO EN PANTALLA
# ============================================================
st.markdown(
    """
    <div class="tv-footer">
        Desarrollado por <b>DIL Digital</b>
    </div>
    """,
    unsafe_allow_html=True
)
