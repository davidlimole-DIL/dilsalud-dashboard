# ============================================================
# DIL-Salud — Monitor de Cartelería Digital para Smart TV v9
# ============================================================
# Interfaz diseñada para proyectarse de forma estática en Smart TV o Chromecast.
# Cero interacción, autorefresco de 5 minutos. Layout inteligente y adaptativo.
# Color de borde de tarjeta según el Turno (Celeste, Púrpura, Rosa).
# ============================================================

import os
import re
import json
import base64
import math
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
    page_title="NEFRA Valle de Uco | Monitor TV",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}

# ============================================================
# 2. CONEXIÓN A GOOGLE SHEETS Y CARGA DE DATOS (Sin caché)
# ============================================================
# Horario de Argentina (UTC-3)
tz_arg = timezone(timedelta(hours=-3))
ahora_arg = datetime.now(tz_arg)
hoy_arg = ahora_arg.date()

# De lunes a sábado (weekday <= 5), de 05:00 hs a 18:00 hs
es_operativo = (ahora_arg.weekday() <= 5) and (5 <= ahora_arg.hour < 18)

if es_operativo:
    st_autorefresh(interval=300000, key="tv_autorefresh")
else:
    st_autorefresh(interval=1800000, key="tv_autorefresh_slow")

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
# 3. MOTOR DE CÁLCULO DIARIO
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
            role_est = str(r.get("Estado", "")).strip().upper()
            df.at[idx, "Asistencia"] = "Presente" if role_est in ("TRUE", "VERDADERO", "1", "SI", "SÍ") else "Ausente"
            df.at[idx, "Observaciones"] = str(r.get("Observaciones", "")).strip()
            m = re.search(r"(\d{1,2}):(\d{2})", str(r.get("Marca_Temporal", "")))
            if m:
                df.at[idx, "Hora"] = f"{m.group(1).zfill(2)}:{m.group(2)}"

    return df[cols].sort_values(["Móvil", "Turno", "Nombre"]).reset_index(drop=True)

# Calcular el universo operativo de hoy
df_hoy = calcular_universo_diario(hoy_arg, df_cron, df_exc, df_pac, df_asis)

# ============================================================
# 4. AGRUPACIÓN ADAPTATIVA DE ELEMENTOS POR ESTADO
# ============================================================
items_p = []
for turno in ["Turno 1", "Turno 2", "Turno 3"]:
    pacs = df_hoy[(df_hoy["Turno"] == turno) & (df_hoy["Asistencia"] == "Presente")] if not df_hoy.empty else pd.DataFrame()
    if not pacs.empty:
        items_p.append({"type": "header", "text": turno.upper()})
        t_cls = "turno-" + turno.split(" ")[1]
        for _, r in pacs.iterrows():
            items_p.append({"type": "patient", "name": r["Nombre"], "turno_class": t_cls})

items_a = []
for turno in ["Turno 1", "Turno 2", "Turno 3"]:
    pacs = df_hoy[(df_hoy["Turno"] == turno) & (df_hoy["Asistencia"] == "Ausente")] if not df_hoy.empty else pd.DataFrame()
    if not pacs.empty:
        items_a.append({"type": "header", "text": turno.upper()})
        t_cls = "turno-" + turno.split(" ")[1]
        for _, r in pacs.iterrows():
            items_a.append({"type": "patient", "name": r["Nombre"], "turno_class": t_cls})

items_e = []
for turno in ["Turno 1", "Turno 2", "Turno 3"]:
    pacs = df_hoy[(df_hoy["Turno"] == turno) & (df_hoy["Asistencia"] == "Pendiente")] if not df_hoy.empty else pd.DataFrame()
    if not pacs.empty:
        items_e.append({"type": "header", "text": turno.upper()})
        t_cls = "turno-" + turno.split(" ")[1]
        for _, r in pacs.iterrows():
            items_e.append({"type": "patient", "name": r["Nombre"], "turno_class": t_cls})

# Determinar cantidad óptima de subcolumnas (C_p, C_a, C_e) dinámicamente
C_p = max(1, math.ceil(len(items_p) / 8)) if items_p else 1
C_a = max(1, math.ceil(len(items_a) / 8)) if items_a else 1
C_e = max(1, math.ceil(len(items_e) / 8)) if items_e else 1

# Determinar el máximo de elementos en cualquier columna del monitor
E_max = max(
    math.ceil(len(items_p) / C_p) if items_p else 0,
    math.ceil(len(items_a) / C_a) if items_a else 0,
    math.ceil(len(items_e) / C_e) if items_e else 0
)
C_total = C_p + C_a + C_e

# ============================================================
# 5. CÁLCULO MATEMÁTICO ADAPTATIVO DE ALTURA Y FUENTE
# ============================================================
target_height = 610
safe_emax = max(1, E_max)

# Altura proporcional teórica para cada elemento
item_height = target_height / safe_emax
item_height = min(75.0, max(22.0, item_height))

# Proporciones adaptativas basadas en la altura calculada
F = max(11, int(item_height * 0.44))  # Tamaño de fuente (mínimo 11px)
P = max(2, int(item_height * 0.16))   # Relleno vertical (mínimo 2px)
M = max(2, int(item_height * 0.14))   # Separación inferior (mínimo 2px)

# Ajuste por ancho horizontal (si hay muchas subcolumnas, reducimos un poco la fuente)
if C_total >= 7 and F > 13:
    F = max(13, F - 2)
    P = max(2, P - 1)
    M = max(2, M - 1)
elif C_total >= 9 and F > 11:
    F = max(11, F - 4)
    P = max(2, P - 2)
    M = max(2, M - 2)

# Capping de fuentes para cabeceras y turnos
col_header_font_size = min(22, max(14, int(F * 1.1)))
turno_header_font_size = min(15, max(10, int(F * 0.85)))

# ============================================================
# 6. ESTILOS CSS DINÁMICOS
# ============================================================
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0f172a;
        color: #f8fafc;
    }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    [data-testid="stHeader"] {{display: none;}}
    [data-testid="stSidebar"] {{display: none;}}
    
    [data-testid="stAppViewContainer"] {{
        padding-top: 0px !important;
    }}
    .main .block-container {{
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }}
    
    .block-container {{
        padding-top: 0.1rem !important;
        padding-bottom: 2.2rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }}

    .monitor-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #1e293b;
        padding-bottom: 4px;
        margin-bottom: 8px;
        margin-top: 0px;
    }}
    .monitor-title {{
        font-size: 21px;
        font-weight: 800;
        color: #38bdf8;
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0;
    }}
    .monitor-timeinfo {{
        text-align: right;
    }}
    .timeinfo-date {{
        font-size: 13px;
        font-weight: 700;
        color: #f1f5f9;
        margin: 0;
    }}
    .timeinfo-refresh {{
        font-size: 10px;
        color: #64748b;
        margin: 0;
        font-weight: 600;
    }}

    .tv-col-header {{
        text-align: center;
        font-size: {col_header_font_size}px;
        font-weight: 800;
        padding: 4px;
        border-radius: 5px;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }}
    .tv-col-header.green {{
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    .tv-col-header.red {{
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }}
    .tv-col-header.grey {{
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }}

    .tv-subcolumns-wrapper {{
        column-gap: 12px;
    }}

    .turno-sub-header {{
        break-inside: avoid;
        display: block;
        font-size: {turno_header_font_size}px;
        font-weight: 800;
        color: #94a3b8;
        background-color: #1e293b;
        padding: 1px 6px;
        border-radius: 10px;
        margin-top: {M - 1 if M > 1 else 1}px;
        margin-bottom: {M - 1 if M > 1 else 1}px;
        border: 1px solid #334155;
        width: fit-content;
        letter-spacing: 0.5px;
    }}
    
    /* Indicador de color del Turno a la izquierda de la subcabecera */
    .turno-sub-header.turno-1 {{
        border-left: 3px solid #0ea5e9; /* Celeste */
    }}
    .turno-sub-header.turno-2 {{
        border-left: 3px solid #a855f7; /* Púrpura */
    }}
    .turno-sub-header.turno-3 {{
        border-left: 3px solid #f97316; /* Naranja */
    }}

    .tv-card {{
        break-inside: avoid;
        background-color: #1e293b;
        border-radius: 5px;
        padding: {P}px {P + 4}px;
        margin-bottom: {M}px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        border-left: {max(3, F // 3)}px solid #64748b;
        display: block;
    }}
    
    /* Indicadores de color del Turno en el borde izquierdo de las tarjetas (No semáforo) */
    .tv-card.turno-1 {{
        border-left-color: #0ea5e9 !important; /* Celeste */
    }}
    .tv-card.turno-2 {{
        border-left-color: #a855f7 !important; /* Púrpura */
    }}
    .tv-card.turno-3 {{
        border-left-color: #f97316 !important; /* Naranja */
    }}
    
    .tv-patient-name {{
        font-size: {F}px;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        line-height: 1.2;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: normal;
        word-break: break-word;
    }}

    .tv-footer {{
        position: fixed;
        bottom: 8px;
        left: 16px;
        font-size: 11px;
        color: #64748b;
        font-weight: 700;
        z-index: 999;
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 7. HEADER DEL MONITOR
# ============================================================
fecha_label = f"{hoy_arg.strftime('%d/%m/%Y')} — {DIAS_SEMANA[hoy_arg.weekday()]}"
actualizado_label = ahora_arg.strftime("%H:%M:%S")

st.markdown(
    f"""
    <div class="monitor-header">
        <div class="monitor-title">
            <span>🏥</span> NEFRA Valle de Uco — Monitor de Recepción
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
# 8. MAQUETADO DE GRILLA ADAPTATIVA
# ============================================================
if df_hoy.empty:
    st.info("No hay traslados programados para el día de hoy.")
else:
    # Definimos columnas generales asignando anchos proporcionales a sus subcolumnas
    col_presente, col_ausente, col_pendiente = st.columns([C_p, C_a, C_e])
    
    # 1. EN CAMINO (Presente)
    with col_presente:
        st.markdown('<div class="tv-col-header green">🟢 EN CAMINO</div>', unsafe_allow_html=True)
        if items_p:
            html_p = f'<div class="tv-subcolumns-wrapper" style="column-count: {C_p};">'
            for item in items_p:
                if item["type"] == "header":
                    t_num = item["text"].split(" ")[1]
                    html_p += f'<div class="turno-sub-header turno-{t_num}">{item["text"]}</div>'
                else:
                    html_p += f'<div class="tv-card {item["turno_class"]}"><p class="tv-patient-name">{item["name"]}</p></div>'
            html_p += '</div>'
            st.markdown(html_p, unsafe_allow_html=True)
                
    # 2. NO ASISTE (Ausente)
    with col_ausente:
        st.markdown('<div class="tv-col-header red">🔴 NO ASISTE</div>', unsafe_allow_html=True)
        if items_a:
            html_a = f'<div class="tv-subcolumns-wrapper" style="column-count: {C_a};">'
            for item in items_a:
                if item["type"] == "header":
                    t_num = item["text"].split(" ")[1]
                    html_a += f'<div class="turno-sub-header turno-{t_num}">{item["text"]}</div>'
                else:
                    html_a += f'<div class="tv-card {item["turno_class"]}"><p class="tv-patient-name">{item["name"]}</p></div>'
            html_a += '</div>'
            st.markdown(html_a, unsafe_allow_html=True)
                
    # 3. EN ESPERA (Pendiente)
    with col_pendiente:
        st.markdown('<div class="tv-col-header grey">🟡 EN ESPERA</div>', unsafe_allow_html=True)
        if items_e:
            html_e = f'<div class="tv-subcolumns-wrapper" style="column-count: {C_e};">'
            for item in items_e:
                if item["type"] == "header":
                    t_num = item["text"].split(" ")[1]
                    html_e += f'<div class="turno-sub-header turno-{t_num}">{item["text"]}</div>'
                else:
                    html_e += f'<div class="tv-card {item["turno_class"]}"><p class="tv-patient-name">{item["name"]}</p></div>'
            html_e += '</div>'
            st.markdown(html_e, unsafe_allow_html=True)

# ============================================================
# 9. FOOTER FIJO EN PANTALLA A LA IZQUIERDA
# ============================================================
st.markdown(
    """
    <div class="tv-footer">
        Desarrollado por <b>DIL Digital</b>
    </div>
    """,
    unsafe_allow_html=True
)
