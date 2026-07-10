# ============================================================
# DIL-Salud — Dashboard Analítico de Logística Médica v2
# ============================================================
# Stack:       Streamlit + Pandas + Plotly + gspread
# Mejoras v2:  Responsive mobile, Excepciones, Acumulado mensual
# ============================================================

import faulthandler
faulthandler.enable()

import os
import re
import json
import base64
from datetime import datetime, date
from calendar import monthrange

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials
import plotly.express as px
import plotly.graph_objects as go


# ============================================================
# 1. CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="DIL-Salud | Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",  # Colapsada por defecto en mobile
)

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ============================================================
# 2. ESTILOS CSS — Responsive Desktop + Mobile (Premium Clinic Theme)
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Make Streamlit top bar transparent to keep the sidebar toggle button visible */
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }

    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* Compact sidebar spacing */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.6rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        padding-bottom: 0.3rem !important;
    }

    /* ── KPI Cards ── */
    .kpi-card {
        border-radius: 16px; 
        padding: 22px 16px; 
        background: var(--secondary-background-color, #ffffff);
        color: var(--text-color, #1e293b);
        border: 1px solid rgba(128, 128, 128, 0.15);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
        transition: all 0.2s ease-in-out;
        margin-bottom: 15px;
        position: relative;
        overflow: hidden;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.04);
    }
    .kpi-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 5px;
        height: 100%;
    }
    .kpi-card.purple::before { background: #6366f1; }
    .kpi-card.green::before  { background: #10b981; }
    .kpi-card.red::before    { background: #f43f5e; }
    .kpi-card.yellow::before { background: #eab308; }
    .kpi-card.blue::before   { background: #06b6d4; }
    
    .kpi-value { 
        font-size: 34px; 
        font-weight: 800; 
        margin: 0; 
        line-height: 1.1; 
        color: var(--text-color, #0f172a);
    }
    .kpi-label { 
        font-size: 11px; 
        color: var(--text-color, #64748b); 
        opacity: 0.8;
        margin-top: 5px;
        font-weight: 700;
        text-transform: uppercase; 
        letter-spacing: 1.2px; 
    }

    /* ── Header Container ── */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 24px;
        background: var(--secondary-background-color, #ffffff);
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
        margin-top: 0rem !important;
        margin-bottom: 25px;
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-left: 5px solid #1e3b8b;
    }
    .header-logo-title {
        display: flex;
        align-items: center;
        gap: 20px;
    }
    .client-logo {
        height: 75px;
        object-fit: contain;
    }
    .header-text {
        display: flex;
        flex-direction: column;
    }
    .header-subtitle {
        margin: 0;
        font-size: 14px;
        color: var(--text-color, #64748b);
        font-weight: 600;
        opacity: 0.9;
    }
    .sync-badge {
        background: rgba(21, 128, 61, 0.1);
        color: #15803d;
        border: 1px solid rgba(21, 128, 61, 0.2);
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    /* ── Watermark Container ── */
    .footer-container {
        margin-top: 50px;
        padding: 25px 0;
        text-align: center;
    }
    .footer-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(128, 128, 128, 0.2), transparent);
        margin-bottom: 15px;
    }
    .footer-content {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 8px;
        font-size: 10px;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .dil-logo {
        height: 24px;
        object-fit: contain;
        vertical-align: middle;
        transition: transform 0.2s;
    }
    .dil-logo:hover {
        transform: scale(1.08);
    }
    .dil-link {
        display: flex;
        align-items: center;
        gap: 6px;
        text-decoration: none;
        color: #64748b;
        font-weight: 700;
    }
    .dil-link:hover {
        color: #1e3b8b;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] { 
        background-color: var(--background-color, #ffffff) !important;
        border-right: 1px solid rgba(128, 128, 128, 0.15) !important;
    }

    /* ── Tab styles override ── */
    button[data-baseweb="tab"] {
        font-weight: 600;
        color: #64748b;
        font-size: 14px;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #1e3b8b !important;
        border-bottom-color: #1e3b8b !important;
    }

    /* Pulsing sync dot */
    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(22, 163, 74, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
    }

    /* ── MOBILE: pantallas < 768px ── */
    @media (max-width: 768px) {
        .header-container {
            flex-direction: column;
            align-items: flex-start;
            gap: 15px;
            padding: 16px;
        }
        .header-logo-title {
            gap: 12px;
        }
        .client-logo {
            height: 55px;
        }
        .header-subtitle {
            font-size: 12px;
        }
        .kpi-value { font-size: 26px; }
        .kpi-label { font-size: 9px; }
        .kpi-card { padding: 14px 10px; }
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 3. CONEXIÓN A GOOGLE SHEETS (OAuth2 dual: Cloud + Local)
# ============================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
_AUTH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit")
_AUTHORIZED_USER = os.path.join(_AUTH_DIR, "authorized_user.json")


def _cargar_credenciales_oauth():
    """Carga OAuth2 desde st.secrets (Cloud) o archivo local."""
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
        st.error("❌ Ejecutá primero: **`python setup_auth.py`**")
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


@st.cache_resource(show_spinner=False)
def _get_client():
    return gspread.authorize(_cargar_credenciales_oauth())


# ============================================================
# 3c. LOGO BASE64 ENCODER HELPER
# ============================================================
@st.cache_data
def get_base64_logo(filename):
    """Carga y convierte una imagen local en base64 para embeber en HTML."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""


# ============================================================
# 4. CONTROL DE ACCESO
# ============================================================
def verificar_acceso():
    try:
        password_correcta = st.secrets["app_auth"]["password"]
    except (KeyError, FileNotFoundError):
        return

    if st.session_state.get("autenticado"):
        return

    logo_client_b64 = get_base64_logo("logo.png")
    logo_dil_b64 = get_base64_logo("logoDIL1transp.png")

    client_logo_html = f'<img src="data:image/png;base64,{logo_client_b64}" style="height: 130px; object-fit: contain; margin-bottom: 25px;">' if logo_client_b64 else '🏥'

    st.markdown(f"""
    <div style="text-align: center; margin-top: 50px;">
        {client_logo_html}
        <p style="color: var(--text-color); opacity: 0.8; font-size: 14px; margin-top: 5px; margin-bottom: 30px; font-weight: 600;">Control y Logística de Pacientes Hematológicos</p>
    </div>
    """, unsafe_allow_html=True)

    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        with st.container(border=True):
            pwd = st.text_input("Contraseña de Acceso", type="password", key="lp")
            if st.button("Ingresar al Sistema", use_container_width=True, type="primary"):
                if pwd == password_correcta:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")

    dil_logo_html = f'<img src="data:image/png;base64,{logo_dil_b64}" class="dil-logo">' if logo_dil_b64 else '<span>DIL Digital</span>'
    st.markdown(f"""
    <div class="footer-container" style="margin-top: 60px;">
        <div class="footer-divider"></div>
        <div class="footer-content">
            <span>Desarrollado por</span>
            <a href="https://www.dildigital.com.ar" target="_blank" class="dil-link">
                {dil_logo_html}
                <span>DIL Digital</span>
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


verificar_acceso()


# ============================================================
# 5. CARGA DE DATOS
# ============================================================
@st.cache_data(ttl=300, show_spinner="Sincronizando con Google Sheets…")
def cargar_datos():
    client = _get_client()
    spreadsheet = client.open_by_url(st.secrets["google_sheets"]["spreadsheet_url"])

    nombres = ["ASISTENCIA_DIARIA", "PACIENTE", "CRONOGRAMA", "EXCEPCIONES", "USUARIOS"]
    hojas = {}
    for nombre in nombres:
        try:
            hojas[nombre] = pd.DataFrame(spreadsheet.worksheet(nombre).get_all_records())
        except gspread.exceptions.WorksheetNotFound:
            hojas[nombre] = pd.DataFrame()
            st.warning(f"⚠️ Hoja **{nombre}** no encontrada.")
    return hojas


try:
    hojas = cargar_datos()
except Exception as e:
    st.error(f"❌ Error de conexión: `{e}`")
    st.stop()

df_cronograma = hojas["CRONOGRAMA"]
df_excepciones = hojas["EXCEPCIONES"]
df_pacientes = hojas["PACIENTE"]
df_asistencia = hojas["ASISTENCIA_DIARIA"]
df_usuarios = hojas["USUARIOS"]


# ============================================================
# 6. MOTOR DE CÁLCULO DIARIO
# ============================================================
def calcular_universo_diario(fecha_sel, df_cron, df_exc, df_pac, df_asis):
    """Réplica de obtenerPacientesDia del backend GAS."""
    dia_semana = DIAS_SEMANA[fecha_sel.weekday()]
    fecha_str = fecha_sel.strftime("%d/%m/%Y")

    # Viajes fijos del día
    if df_cron.empty:
        fijos = pd.DataFrame()
    else:
        c = df_cron.copy()
        c["_d"] = c["Día_Semana"].astype(str).str.strip().str.lower()
        fijos = c[c["_d"] == dia_semana.lower()].drop(columns=["_d"])

    # Excepciones del día
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

    # Unificar
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

    # Enriquecer con datos del paciente
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

    # Cruzar con asistencia
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


# ============================================================
# 7. MOTOR DE CÁLCULO MENSUAL
# ============================================================
@st.cache_data(ttl=300, show_spinner="Calculando métricas mensuales…")
def calcular_metricas_mensuales(_mes, _anio, _df_cron, _df_exc, _df_pac, _df_asis):
    """Itera día por día del mes y acumula las métricas diarias."""
    ultimo_dia = monthrange(_anio, _mes)[1]
    hoy = date.today()

    datos_diarios = []
    for dia in range(1, ultimo_dia + 1):
        fecha = date(_anio, _mes, dia)
        if fecha > hoy:
            break

        df_dia = calcular_universo_diario(fecha, _df_cron, _df_exc, _df_pac, _df_asis)
        esp = len(df_dia)
        if esp == 0:
            continue

        pre = len(df_dia[df_dia["Asistencia"] == "Presente"])
        aus = len(df_dia[df_dia["Asistencia"] == "Ausente"])
        pen = len(df_dia[df_dia["Asistencia"] == "Pendiente"])

        datos_diarios.append({
            "Fecha": fecha,
            "Día": DIAS_SEMANA[fecha.weekday()][:3],
            "Esperados": esp,
            "Presentes": pre,
            "Ausentes": aus,
            "Pendientes": pen,
        })

    if not datos_diarios:
        return None

    df = pd.DataFrame(datos_diarios)
    return {
        "total_esperados": int(df["Esperados"].sum()),
        "total_presentes": int(df["Presentes"].sum()),
        "total_ausentes": int(df["Ausentes"].sum()),
        "total_pendientes": int(df["Pendientes"].sum()),
        "tasa": round(df["Presentes"].sum() / df["Esperados"].sum() * 100, 1) if df["Esperados"].sum() > 0 else 0,
        "dias_operativos": len(df),
        "diario": df,
    }


# ============================================================
# 8. MOTOR DE EXCEPCIONES
# ============================================================
def obtener_excepciones_mes(mes, anio, df_exc, df_pac):
    """Filtra excepciones del mes y enriquece con nombre de paciente."""
    if df_exc.empty:
        return pd.DataFrame(), 0, 0

    ex = df_exc.copy()
    ex["_fecha_str"] = ex["Fecha_Exacta"].astype(str).str.strip()

    # Parsear fecha dd/MM/yyyy y filtrar por mes/año
    fechas_validas = []
    for i, f_str in ex["_fecha_str"].items():
        try:
            partes = f_str.split("/")
            if len(partes) == 3:
                d, m, y = int(partes[0]), int(partes[1]), int(partes[2])
                if m == mes and y == anio:
                    fechas_validas.append(i)
        except (ValueError, IndexError):
            pass

    if not fechas_validas:
        return pd.DataFrame(), 0, 0

    df = ex.loc[fechas_validas].copy()

    # Enriquecer con nombre
    if not df_pac.empty:
        p = df_pac.copy()
        p["_id"] = p["ID_Paciente"].astype(str).str.strip()
        df["_pid"] = df["ID_Paciente"].astype(str).str.strip()
        df = df.merge(
            p[["_id", "Nombre_Paciente"]],
            left_on="_pid", right_on="_id", how="left"
        ).drop(columns=["_id", "_pid"])
    else:
        df["Nombre_Paciente"] = "Desconocido"

    df["Nombre_Paciente"] = df["Nombre_Paciente"].fillna("Desconocido")
    tipo = df["Tipo_Modificacion"].astype(str).str.strip()
    cancelaciones = int((tipo == "CANCELA VIAJE FIJO").sum())
    agregados = int((tipo == "AGREGA VIAJE").sum())

    # Columnas finales
    resultado = pd.DataFrame({
        "Fecha": df["Fecha_Exacta"],
        "Paciente": df["Nombre_Paciente"],
        "Tipo": df["Tipo_Modificacion"],
        "Turno": df.get("Turno", ""),
        "Móvil": df.get("Móvil_Asignado", ""),
    })

    return resultado.reset_index(drop=True), cancelaciones, agregados


# ============================================================
# 9. SIDEBAR
# ============================================================
if not df_cronograma.empty:
    turnos_disp = sorted(df_cronograma["Turno"].astype(str).str.strip().unique().tolist())
    moviles_disp = sorted(df_cronograma["Móvil_Asignado"].astype(str).str.strip().unique().tolist())
else:
    turnos_disp = ["Turno 1", "Turno 2", "Turno 3"]
    moviles_disp = []

with st.sidebar:
    logo_client_b64 = get_base64_logo("logo.png")
    if logo_client_b64:
        st.markdown(f'<div style="text-align: center; margin-bottom: 5px;"><img src="data:image/png;base64,{logo_client_b64}" style="width: 140px; object-fit: contain;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center; font-size: 11px; font-weight: 600; color: var(--text-color); opacity: 0.7; margin-bottom: 8px;">Control de Traslados</div>', unsafe_allow_html=True)
    
    st.markdown('<div style="margin: 4px 0; border-top: 1px solid rgba(128,128,128,0.15)"></div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size: 12px; font-weight: 700; color: var(--text-color); margin-bottom: 4px;">📅 Fecha (Monitor Diario)</div>', unsafe_allow_html=True)
    fecha_sel = st.date_input("Fecha", value=date.today(), format="DD/MM/YYYY",
                              label_visibility="collapsed")

    st.markdown('<div style="margin: 4px 0; border-top: 1px solid rgba(128,128,128,0.15)"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 12px; font-weight: 700; color: var(--text-color); margin-bottom: 4px;">🎯 Filtros</div>', unsafe_allow_html=True)
    turnos_filtro = st.multiselect("Turnos", turnos_disp, default=turnos_disp,
                                   placeholder="Todos", label_visibility="collapsed")
    moviles_filtro = st.multiselect("Móviles", moviles_disp, default=moviles_disp,
                                    placeholder="Todos", label_visibility="collapsed")

    st.markdown('<div style="margin: 4px 0; border-top: 1px solid rgba(128,128,128,0.15)"></div>', unsafe_allow_html=True)
    if st.button("🔄  Sincronizar Datos", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<div style="margin: 4px 0; border-top: 1px solid rgba(128,128,128,0.15)"></div>', unsafe_allow_html=True)
    logo_dil_b64 = get_base64_logo("logoDIL1transp.png")
    dil_logo_html = f'<img src="data:image/png;base64,{logo_dil_b64}" class="dil-logo" style="height: 18px;">' if logo_dil_b64 else '<span>DIL Digital</span>'
    st.markdown(f"""
    <div style="text-align: center; font-size: 9px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; display: flex; align-items: center; justify-content: center; gap: 6px;">
        <span>Desarrollado por</span>
        <a href="https://www.dildigital.com.ar" target="_blank" class="dil-link" style="font-size: 9px; font-weight: 700; color: #64748b; display: inline-flex; align-items: center; gap: 4px; text-decoration: none;">
            {dil_logo_html}
        </a>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# 10. HEADER
# ============================================================
hora_sync = datetime.now().strftime("%H:%M:%S")
logo_client_b64 = get_base64_logo("logo.png")
logo_client_html = f'<img src="data:image/png;base64,{logo_client_b64}" class="client-logo">' if logo_client_b64 else '🏥'

st.markdown(f"""
<div class="header-container">
    <div class="header-logo-title">
        {logo_client_html}
        <div class="header-text">
            <p class="header-subtitle">Control y Logística de Pacientes Hematológicos</p>
        </div>
    </div>
    <div class="header-sync-status">
        <span class="sync-badge">
            <span style="display:inline-block; width:8px; height:8px; background-color:#16a34a; border-radius:50%; animation: pulse 2s infinite;"></span>
            Sincronizado: {hora_sync}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# 11. PESTAÑAS PRINCIPALES
# ============================================================
tab_diario, tab_mensual, tab_excepciones = st.tabs([
    "📋 Monitor Diario", "📊 Acumulado Mensual", "📝 Excepciones"
])


# ── TAB 1: MONITOR DIARIO ──────────────────────────────────
with tab_diario:
    dia_nombre = DIAS_SEMANA[fecha_sel.weekday()]
    fecha_display = fecha_sel.strftime("%d/%m/%Y")
    st.markdown(f"**📅 {dia_nombre} {fecha_display}**")

    df_monitor = calcular_universo_diario(
        fecha_sel, df_cronograma, df_excepciones, df_pacientes, df_asistencia
    )
    if turnos_filtro:
        df_monitor = df_monitor[df_monitor["Turno"].isin(turnos_filtro)]
    if moviles_filtro:
        df_monitor = df_monitor[df_monitor["Móvil"].isin(moviles_filtro)]

    t_esp = len(df_monitor)
    t_pre = len(df_monitor[df_monitor["Asistencia"] == "Presente"])
    t_aus = len(df_monitor[df_monitor["Asistencia"] == "Ausente"])
    t_pen = len(df_monitor[df_monitor["Asistencia"] == "Pendiente"])

    # KPIs (2 filas × 2 columnas para mobile-friendly)
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)

    with r1c1:
        st.markdown(f'<div class="kpi-card purple"><p class="kpi-value">{t_esp}</p>'
                    f'<p class="kpi-label">Esperados</p></div>', unsafe_allow_html=True)
    with r1c2:
        st.markdown(f'<div class="kpi-card green"><p class="kpi-value">{t_pre}</p>'
                    f'<p class="kpi-label">Presentes</p></div>', unsafe_allow_html=True)
    with r2c1:
        st.markdown(f'<div class="kpi-card red"><p class="kpi-value">{t_aus}</p>'
                    f'<p class="kpi-label">Ausentes</p></div>', unsafe_allow_html=True)
    with r2c2:
        st.markdown(f'<div class="kpi-card yellow"><p class="kpi-value">{t_pen}</p>'
                    f'<p class="kpi-label">Pendientes</p></div>', unsafe_allow_html=True)

    st.markdown("")

    # Gráficos
    if t_esp > 0:
        col_pie, col_bar = st.columns(2)

        with col_pie:
            st.markdown("**Distribución de Asistencia**")
            fig = px.pie(
                names=["Presentes", "Ausentes", "Pendientes"],
                values=[t_pre, t_aus, t_pen],
                color_discrete_sequence=["#38ef7d", "#f45c43", "#ffd200"],
                hole=0.5,
            )
            fig.update_traces(textinfo="value+percent", textfont_size=13)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300,
                              legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
            st.plotly_chart(fig, use_container_width=True)

        with col_bar:
            st.markdown("**Volumen por Móvil**")
            df_b = df_monitor.groupby(["Móvil", "Asistencia"]).size().reset_index(name="Cant")
            fig2 = px.bar(df_b, x="Móvil", y="Cant", color="Asistencia",
                          color_discrete_map={"Presente": "#38ef7d", "Ausente": "#f45c43",
                                              "Pendiente": "#ffd200"},
                          barmode="stack", text="Cant")
            fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300,
                               xaxis_title="", yaxis_title="Pacientes",
                               legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center",
                                           title=""))
            fig2.update_traces(textposition="inside")
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")

    # Tabla de monitoreo
    st.markdown("**Detalle de Pacientes**")
    if df_monitor.empty:
        st.info("No hay viajes programados con los filtros seleccionados.")
    else:
        df_tabla = df_monitor[["Móvil", "Turno", "Nombre", "Destino",
                               "Asistencia", "Observaciones", "Hora"]].copy()

        def _color(row):
            estilos = {
                "Presente":  "background-color:#d1fae5;color:#065f46",
                "Ausente":   "background-color:#fee2e2;color:#991b1b",
                "Pendiente": "background-color:#fef9c3;color:#854d0e",
            }
            e = estilos.get(row["Asistencia"], "")
            return [e] * len(row)

        st.dataframe(
            df_tabla.style.apply(_color, axis=1),
            use_container_width=True,
            height=min(500, 45 + len(df_tabla) * 36),
            hide_index=True,
        )

        if t_pen > 0:
            with st.expander(f"⚠️ {t_pen} paciente(s) pendientes", expanded=True):
                for _, r in df_monitor[df_monitor["Asistencia"] == "Pendiente"].iterrows():
                    st.markdown(f"- **{r['Nombre']}** → {r['Móvil']} / {r['Turno']}")


# ── TAB 2: ACUMULADO MENSUAL ───────────────────────────────
with tab_mensual:
    hoy = date.today()
    mes_ant = hoy.month - 1 if hoy.month > 1 else 12
    anio_ant = hoy.year if hoy.month > 1 else hoy.year - 1

    opciones_mes = {
        f"{MESES_ES[hoy.month]} {hoy.year}": (hoy.month, hoy.year),
        f"{MESES_ES[mes_ant]} {anio_ant}": (mes_ant, anio_ant),
    }

    mes_label = st.selectbox("Seleccionar período", list(opciones_mes.keys()))
    mes_sel, anio_sel = opciones_mes[mes_label]

    metricas = calcular_metricas_mensuales(
        mes_sel, anio_sel, df_cronograma, df_excepciones, df_pacientes, df_asistencia
    )

    if metricas is None:
        st.info(f"No hay datos operativos para {mes_label}.")
    else:
        # KPIs mensuales (2×3 grid)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f'<div class="kpi-card purple"><p class="kpi-value">'
                        f'{metricas["total_esperados"]}</p>'
                        f'<p class="kpi-label">Traslados Esperados</p></div>',
                        unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="kpi-card green"><p class="kpi-value">'
                        f'{metricas["total_presentes"]}</p>'
                        f'<p class="kpi-label">Presentes</p></div>',
                        unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="kpi-card red"><p class="kpi-value">'
                        f'{metricas["total_ausentes"]}</p>'
                        f'<p class="kpi-label">Ausentes</p></div>',
                        unsafe_allow_html=True)

        m4, m5, m6 = st.columns(3)
        with m4:
            st.markdown(f'<div class="kpi-card yellow"><p class="kpi-value">'
                        f'{metricas["total_pendientes"]}</p>'
                        f'<p class="kpi-label">Pendientes</p></div>',
                        unsafe_allow_html=True)
        with m5:
            st.markdown(f'<div class="kpi-card blue"><p class="kpi-value">'
                        f'{metricas["tasa"]}%</p>'
                        f'<p class="kpi-label">Tasa Asistencia</p></div>',
                        unsafe_allow_html=True)
        with m6:
            st.markdown(f'<div class="kpi-card purple"><p class="kpi-value">'
                        f'{metricas["dias_operativos"]}</p>'
                        f'<p class="kpi-label">Días Operativos</p></div>',
                        unsafe_allow_html=True)

        st.markdown("")

        # Gráfico de tendencia diaria
        st.markdown("**📈 Tendencia Diaria**")
        df_d = metricas["diario"].copy()
        df_d["Fecha_str"] = df_d["Fecha"].apply(lambda x: x.strftime("%d/%m"))

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=df_d["Fecha_str"], y=df_d["Presentes"],
            name="Presentes", marker_color="#38ef7d",
        ))
        fig_trend.add_trace(go.Bar(
            x=df_d["Fecha_str"], y=df_d["Ausentes"],
            name="Ausentes", marker_color="#f45c43",
        ))
        fig_trend.add_trace(go.Bar(
            x=df_d["Fecha_str"], y=df_d["Pendientes"],
            name="Pendientes", marker_color="#ffd200",
        ))
        fig_trend.update_layout(
            barmode="stack",
            margin=dict(t=10, b=10, l=10, r=10),
            height=350,
            xaxis_title="", yaxis_title="Pacientes",
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", title=""),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # Tabla resumen diario
        with st.expander("📋 Ver detalle día por día"):
            df_show = df_d[["Fecha_str", "Día", "Esperados", "Presentes",
                            "Ausentes", "Pendientes"]].copy()
            df_show = df_show.rename(columns={"Fecha_str": "Fecha"})
            st.dataframe(df_show, use_container_width=True, hide_index=True)


# ── TAB 3: EXCEPCIONES ─────────────────────────────────────
with tab_excepciones:
    hoy = date.today()
    mes_ant = hoy.month - 1 if hoy.month > 1 else 12
    anio_ant = hoy.year if hoy.month > 1 else hoy.year - 1

    opciones_exc = {
        f"{MESES_ES[hoy.month]} {hoy.year}": (hoy.month, hoy.year),
        f"{MESES_ES[mes_ant]} {anio_ant}": (mes_ant, anio_ant),
    }

    mes_exc_label = st.selectbox("Período de excepciones", list(opciones_exc.keys()),
                                  key="exc_mes")
    mes_exc, anio_exc = opciones_exc[mes_exc_label]

    df_exc_mes, n_cancel, n_agreg = obtener_excepciones_mes(
        mes_exc, anio_exc, df_excepciones, df_pacientes
    )

    total_exc = n_cancel + n_agreg

    # KPIs de excepciones
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown(f'<div class="kpi-card purple"><p class="kpi-value">{total_exc}</p>'
                    f'<p class="kpi-label">Total Excepciones</p></div>',
                    unsafe_allow_html=True)
    with e2:
        st.markdown(f'<div class="kpi-card red"><p class="kpi-value">{n_cancel}</p>'
                    f'<p class="kpi-label">Viajes Cancelados</p></div>',
                    unsafe_allow_html=True)
    with e3:
        st.markdown(f'<div class="kpi-card green"><p class="kpi-value">{n_agreg}</p>'
                    f'<p class="kpi-label">Viajes Agregados</p></div>',
                    unsafe_allow_html=True)

    st.markdown("")

    if df_exc_mes.empty:
        st.info(f"No se registraron excepciones en {mes_exc_label}.")
    else:
        # Gráfico: distribución de excepciones por tipo
        st.markdown("**Distribución de Excepciones**")
        fig_exc = px.pie(
            names=["Cancelaciones", "Viajes Extra"],
            values=[n_cancel, n_agreg],
            color_discrete_sequence=["#f45c43", "#38ef7d"],
            hole=0.5,
        )
        fig_exc.update_traces(textinfo="value+percent", textfont_size=14)
        fig_exc.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280,
                              legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
        st.plotly_chart(fig_exc, use_container_width=True)

        st.markdown("---")

        # Tabla detallada
        st.markdown("**Listado de Excepciones**")

        def _color_exc(row):
            tipo = str(row.get("Tipo", "")).strip()
            if "CANCELA" in tipo:
                return ["background-color:#fee2e2;color:#991b1b"] * len(row)
            elif "AGREGA" in tipo:
                return ["background-color:#d1fae5;color:#065f46"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_exc_mes.style.apply(_color_exc, axis=1),
            use_container_width=True,
            height=min(400, 45 + len(df_exc_mes) * 36),
            hide_index=True,
        )


# ============================================================
# 12. FOOTER
# ============================================================
logo_dil_b64 = get_base64_logo("logoDIL1transp.png")
dil_logo_html = f'<img src="data:image/png;base64,{logo_dil_b64}" class="dil-logo">' if logo_dil_b64 else '<span>DIL Digital</span>'

st.markdown(f"""
<div class="footer-container">
    <div class="footer-divider"></div>
    <div class="footer-content">
        <span>Desarrollado y Administrado por</span>
        <a href="https://www.dildigital.com.ar" target="_blank" class="dil-link">
            {dil_logo_html}
            <span>DIL Digital</span>
        </a>
    </div>
</div>
""", unsafe_allow_html=True)
