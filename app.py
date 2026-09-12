# ======================================
# Importaciones
# ======================================
import html
import io
import json
import logging
import re
import time
import streamlit as st
import pandas as pd

from catalogo_tono_tema import CRITERIOS_TONO
from pipeline import process_dossier
from pkl_classifier import PklClassifierError, load_sklearn_estimator

logger = logging.getLogger("limpieza_grill")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

# ======================================
# CSS Personalizado (claro / oscuro)
# ======================================
THEME_LIGHT_VARS = """
:root,[data-testid="stApp"]{
    --bg:#f8f9fa;--s1:#ffffff;--s2:#f1f3f4;--s3:#e8eaed;
    --border:#dadce0;--border2:#bdc1c6;--border-focus:#f97316;
    --text:#202124;--text2:#3c4043;--text3:#5f6368;--text4:#9aa0a6;
    --accent:#f97316;--accent2:#ea580c;--accent3:#c2410c;
    --accent-bg:#fff7ed;--accent-bg2:#ffedd5;--accent-bdr:#fed7aa;
    --green:#059669;--green2:#047857;--green-bg:#ecfdf5;--green-bdr:#a7f3d0;
    --red:#dc2626;--amber:#d97706;--blue:#1a73e8;
    --success-bg:linear-gradient(135deg,#ecfdf5,#d1fae5);
    --success-title:#047857;
    --icon-dossier-bg:#fff7ed;
    --r:8px;--r2:12px;--r3:16px;--r4:20px;
    --shadow-sm:0 1px 2px rgba(60,64,67,0.1),0 1px 3px rgba(60,64,67,0.08);
    --shadow-md:0 1px 3px rgba(60,64,67,0.12),0 4px 8px rgba(60,64,67,0.08);
    --shadow-lg:0 2px 6px rgba(60,64,67,0.1),0 8px 24px rgba(60,64,67,0.1);
    --transition:all 0.2s cubic-bezier(0.4,0,0.2,1);
}
"""

THEME_DARK_VARS = """
:root,[data-testid="stApp"]{
    --bg:#121418;--s1:#1c1f26;--s2:#252830;--s3:#2e333c;
    --border:#3d4450;--border2:#5c6370;--border-focus:#f97316;
    --text:#e8eaed;--text2:#c5c8ce;--text3:#9aa0a6;--text4:#6e7480;
    --accent:#f97316;--accent2:#fb923c;--accent3:#fdba74;
    --accent-bg:#2a1c10;--accent-bg2:#3d2814;--accent-bdr:#9a5b28;
    --green:#34d399;--green2:#6ee7b7;--green-bg:#0f291e;--green-bdr:#065f46;
    --red:#f87171;--amber:#fbbf24;--blue:#60a5fa;
    --success-bg:linear-gradient(135deg,#0f291e,#134e3a);
    --success-title:#6ee7b7;
    --icon-dossier-bg:#2a1c10;
    --r:8px;--r2:12px;--r3:16px;--r4:20px;
    --shadow-sm:0 1px 2px rgba(0,0,0,0.4),0 1px 3px rgba(0,0,0,0.25);
    --shadow-md:0 1px 3px rgba(0,0,0,0.45),0 4px 8px rgba(0,0,0,0.3);
    --shadow-lg:0 2px 6px rgba(0,0,0,0.4),0 8px 24px rgba(0,0,0,0.35);
    --transition:all 0.2s cubic-bezier(0.4,0,0.2,1);
}
"""

def _default_theme() -> str:
    try:
        theme_obj = getattr(getattr(st, "context", None), "theme", None)
        theme_type = getattr(theme_obj, "type", None)
        if theme_type in ("dark", "light"):
            return theme_type
    except Exception:
        pass
    return "light"

def current_ui_theme() -> str:
    theme = st.session_state.get("ui_theme")
    if theme in ("dark", "light"):
        return theme
    return _default_theme()

def load_custom_css():
    theme_vars = THEME_DARK_VARS if current_ui_theme() == "dark" else THEME_LIGHT_VARS
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Google+Sans+Text:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
""" + theme_vars + """
html,body,[data-testid="stApp"]{
    background:var(--bg)!important;color:var(--text)!important;
    font-family:'Google Sans Text','Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    font-size:14px;-webkit-font-smoothing:antialiased;letter-spacing:0.01em;
}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
.block-container{padding-top:1rem!important;padding-bottom:0!important}
[data-testid="stAppViewBlockContainer"]{padding-top:1rem!important}
.app-header{background:var(--s1);border:1px solid var(--border);border-radius:var(--r3);padding:1rem 1.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem;box-shadow:var(--shadow-sm);position:relative;overflow:hidden;}
.app-header::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#f97316,#fb923c,#fdba74);}
.app-header-icon{width:40px;height:40px;background:linear-gradient(135deg,#f97316,#ea580c);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;color:white;flex-shrink:0;box-shadow:0 2px 8px rgba(249,115,22,0.3);}
.app-header-text{flex:1}
.app-header-title{font-family:'Google Sans',sans-serif;font-size:1.25rem;font-weight:700;color:var(--text);letter-spacing:-0.01em;line-height:1.3}
.app-header-version{font-family:'Roboto Mono',monospace;font-size:0.65rem;color:var(--text3);letter-spacing:0.03em;margin-top:0.15rem}
.app-header-badge{background:var(--accent-bg);border:1px solid var(--accent-bdr);color:var(--accent2);font-family:'Roboto Mono',monospace;font-size:0.6rem;font-weight:500;padding:0.25rem 0.75rem;border-radius:100px;letter-spacing:0.04em;text-transform:uppercase;white-space:nowrap;}
.metrics-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin:0.8rem 0}
.metric-card{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:0.8rem 0.6rem;text-align:center;transition:var(--transition);box-shadow:var(--shadow-sm);position:relative;overflow:hidden;}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:var(--r2) var(--r2) 0 0}
.metric-card.m-total::before{background:linear-gradient(90deg,#5f6368,#9aa0a6)}
.metric-card.m-unique::before{background:linear-gradient(90deg,#059669,#34d399)}
.metric-card.m-dup::before{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.metric-card.m-time::before{background:linear-gradient(90deg,#1a73e8,#4285f4)}
.metric-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.metric-val{font-family:'Google Sans',sans-serif;font-size:1.5rem;font-weight:700;line-height:1;margin-bottom:0.3rem;letter-spacing:-0.01em}
.metric-lbl{font-family:'Roboto Mono',monospace;font-size:0.62rem;color:var(--text3);text-transform:uppercase;letter-spacing:0.08em;font-weight:500}
[data-testid="stForm"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r3)!important;padding:1.2rem 1.5rem!important;box-shadow:var(--shadow-md)!important;}
.sec-label{font-family:'Google Sans',sans-serif;font-size:0.72rem;font-weight:700;color:var(--text2);letter-spacing:0.08em;text-transform:uppercase;padding-bottom:0.3rem;border-bottom:2px solid var(--s3);margin:0.8rem 0 0.5rem;display:flex;align-items:center;gap:0.5rem;}
.sec-label::before{content:'';display:inline-block;width:3px;height:12px;background:linear-gradient(180deg,#f97316,#ea580c);border-radius:2px}
.upload-zone{display:grid;grid-template-columns:1fr;gap:0.6rem;margin:0.3rem 0}
.upload-zone-card{background:var(--s1);border:1.5px dashed var(--border);border-radius:var(--r2);padding:0.6rem 0.8rem;display:flex;align-items:center;gap:0.6rem;transition:var(--transition);}
.upload-zone-card:hover{border-color:var(--accent);border-style:solid;transform:translateY(-1px);box-shadow:var(--shadow-md)}
.upload-zone-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;}
.upload-zone-icon.uz-dossier{background:var(--icon-dossier-bg);color:#f97316}
.upload-zone-icon.uz-pkl{background:var(--accent-bg);color:var(--accent2)}
.upload-zone-text{flex:1;min-width:0}
.upload-zone-title{font-family:'Google Sans',sans-serif;font-size:0.82rem;font-weight:700;color:var(--text);line-height:1.2}
.upload-zone-desc{font-size:0.7rem;color:var(--text3);line-height:1.3}
[data-testid="stFileUploader"]{background:var(--s1)!important;border:1.5px dashed var(--border)!important;border-radius:var(--r)!important;padding:0.4rem 0.6rem!important;transition:var(--transition)!important;min-height:auto!important;}
[data-testid="stFileUploader"]:hover{border-color:var(--accent)!important;border-style:solid!important;background:var(--accent-bg)!important;}
[data-testid="stFileUploader"] section{padding:0.2rem!important}
[data-testid="stFileUploader"] section>div{font-size:0.78rem!important;color:var(--text2)!important}
[data-testid="stFileUploader"] section small{font-size:0.7rem!important;color:var(--text3)!important}
[data-testid="stFileUploader"] button{background:var(--accent-bg)!important;border:1px solid var(--accent-bdr)!important;color:var(--accent2)!important;font-weight:500!important;font-size:0.75rem!important;border-radius:100px!important;padding:0.25rem 0.8rem!important;font-family:'Google Sans',sans-serif!important;transition:var(--transition)!important;}
[data-testid="stFileUploader"] button:hover{background:var(--accent)!important;color:white!important;border-color:var(--accent)!important}
[data-testid="stTextInput"] input{background:var(--s1)!important;border:1.5px solid var(--border)!important;color:var(--text)!important;border-radius:var(--r)!important;font-family:'Google Sans Text',sans-serif!important;font-size:0.9rem!important;padding:0.5rem 0.75rem!important;transition:var(--transition)!important;}
[data-testid="stTextInput"] input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(249,115,22,0.12)!important;}
label[data-testid="stWidgetLabel"] p{font-family:'Google Sans',sans-serif!important;color:var(--text2)!important;font-size:0.82rem!important;font-weight:500!important;margin-bottom:0.15rem!important;}
.stButton>button,[data-testid="stDownloadButton"]>button{background:var(--s1)!important;border:1.5px solid var(--border)!important;color:var(--text)!important;border-radius:100px!important;font-family:'Google Sans',sans-serif!important;font-weight:500!important;font-size:0.88rem!important;transition:var(--transition)!important;padding:0.5rem 1.2rem!important;box-shadow:none!important;}
.stButton>button:hover,[data-testid="stDownloadButton"]>button:hover{border-color:var(--accent)!important;color:var(--accent2)!important;background:var(--accent-bg)!important;box-shadow:var(--shadow-sm)!important;transform:translateY(-1px)!important;}
.stButton>button[kind="primary"],[data-testid="stDownloadButton"]>button[kind="primary"]{background:var(--accent)!important;border:none!important;color:#fff!important;font-weight:500!important;font-size:0.92rem!important;padding:0.6rem 1.5rem!important;box-shadow:0 1px 3px rgba(249,115,22,0.3),0 4px 12px rgba(249,115,22,0.15)!important;letter-spacing:0.01em!important;}
.stButton>button[kind="primary"]:hover,[data-testid="stDownloadButton"]>button[kind="primary"]:hover{background:var(--accent2)!important;box-shadow:0 2px 6px rgba(234,88,12,0.35),0 8px 24px rgba(234,88,12,0.18)!important;transform:translateY(-1px)!important;color:#fff!important;}
.success-banner{background:var(--success-bg);border:1px solid var(--green-bdr);border-left:4px solid var(--green);border-radius:var(--r2);padding:0.8rem 1.2rem;margin:0.5rem 0 0.8rem;display:flex;align-items:center;gap:0.8rem;}
.success-icon{width:34px;height:34px;background:linear-gradient(135deg,#059669,#047857);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:1rem;flex-shrink:0;}
.success-title{font-family:'Google Sans',sans-serif;font-size:1rem;font-weight:700;color:var(--success-title);margin-bottom:0.1rem}
.success-sub{font-size:0.8rem;color:var(--text2)}
.auth-wrap{max-width:380px;margin:8vh auto 0;text-align:center}
.auth-icon{width:60px;height:60px;background:linear-gradient(135deg,#f97316,#ea580c);border-radius:16px;display:inline-flex;align-items:center;justify-content:center;font-size:1.6rem;color:white;margin-bottom:1rem;box-shadow:0 4px 166px rgba(249,115,22,0.3);}
.auth-title{font-family:'Google Sans',sans-serif;font-size:1.5rem;font-weight:700;color:var(--text);margin-bottom:0.3rem}
.auth-sub{font-size:0.85rem;color:var(--text3);margin-bottom:2rem}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,#f97316,#fb923c,#fdba74)!important;border-radius:100px!important;height:5px!important;}
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:var(--r2)!important;box-shadow:var(--shadow-sm)!important;overflow:hidden!important;}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--s2);border-radius:3px}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}
.footer{font-family:'Roboto Mono',monospace;font-size:0.6rem;color:var(--text4);text-align:center;padding:0.8rem 0 0.5rem;letter-spacing:0.04em;border-top:1px solid var(--s3);margin-top:1rem;}
.stElementContainer{margin-bottom:0!important}
[data-testid="stVerticalBlock"]>div{gap:0.3rem!important}
[data-testid="stHorizontalBlock"]>div{gap:0.4rem!important}
hr{border-color:var(--s3)!important;margin:0.5rem 0!important}
.config-badge{display:inline-flex;align-items:center;gap:0.4rem;background:var(--s2);border:1px solid var(--border);border-radius:100px;padding:0.2rem 0.7rem;font-family:'Roboto Mono',monospace;font-size:0.62rem;color:var(--text3);margin-bottom:0.6rem;}
.live-panel{background:var(--s1);border:1px solid var(--border);border-radius:var(--r3);padding:1rem 1.2rem;margin:0.4rem 0 0.8rem;box-shadow:var(--shadow-md);position:relative;overflow:hidden;}
.live-panel::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#f97316,#fb923c,#fdba74);}
.live-head{display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;}
.live-pulse{width:12px;height:12px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 0 rgba(249,115,22,0.6);animation:livePulse 1.4s ease-out infinite;flex-shrink:0;}
@keyframes livePulse{0%{box-shadow:0 0 0 0 rgba(249,115,22,0.55)}70%{box-shadow:0 0 0 12px rgba(249,115,22,0)}100%{box-shadow:0 0 0 0 rgba(249,115,22,0)}}
.live-title{font-family:'Google Sans',sans-serif;font-size:1.02rem;font-weight:700;color:var(--text);line-height:1.2}
.live-sub{font-size:0.78rem;color:var(--text3);margin-top:0.15rem}
.live-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:0.5rem;margin:0.4rem 0 0.7rem}
.live-metric{background:var(--s2);border:1px solid var(--border);border-radius:var(--r);padding:0.55rem 0.5rem;text-align:center}
.live-metric-val{font-family:'Google Sans',sans-serif;font-size:1.15rem;font-weight:700;color:var(--accent2);line-height:1.1}
.live-metric-lbl{font-family:'Roboto Mono',monospace;font-size:0.58rem;color:var(--text3);text-transform:uppercase;letter-spacing:0.06em;margin-top:0.2rem}
.step-list{display:flex;flex-direction:column;gap:0.28rem;margin:0.2rem 0 0.6rem}
.step-item{display:flex;align-items:center;gap:0.5rem;font-size:0.8rem;color:var(--text3);padding:0.22rem 0.15rem}
.step-item .dot{width:18px;height:18px;border-radius:50%;border:1.5px solid var(--border2);display:flex;align-items:center;justify-content:center;font-size:0.65rem;flex-shrink:0;background:var(--s1)}
.step-item.is-done{color:var(--green2);font-weight:500}
.step-item.is-done .dot{background:var(--green);border-color:var(--green);color:#fff}
.step-item.is-active{color:var(--accent2);font-weight:700}
.step-item.is-active .dot{border-color:var(--accent);background:var(--accent-bg);color:var(--accent2);animation:livePulse 1.4s ease-out infinite}
.live-hint{background:var(--accent-bg);border:1px solid var(--accent-bdr);color:var(--accent3);border-radius:var(--r);padding:0.55rem 0.75rem;font-size:0.78rem;line-height:1.35}
.live-detail{font-size:0.8rem;color:var(--text2);margin-top:0.45rem;font-family:'Google Sans Text',sans-serif}
.theme-bar{display:flex;justify-content:flex-end;align-items:center;margin:0 0 0.6rem;gap:0.4rem}
.theme-bar .stButton>button{padding:0.35rem 0.85rem!important;font-size:0.78rem!important}
.pkl-hint{font-size:0.78rem;color:var(--text3);margin:0.15rem 0 0.55rem;line-height:1.35}
div[data-testid="stAlert"]{border-radius:var(--r2)!important}
[data-testid="stCheckbox"] p,[data-testid="stToggle"] p{color:var(--text2)!important}
[data-baseweb="select"]>div,[data-baseweb="input"]{background:var(--s1)!important;color:var(--text)!important}
.stMarkdown,.stCaption{color:var(--text2)}
@media(max-width:768px){
    .metrics-grid{grid-template-columns:repeat(2,1fr)}
    .live-metrics{grid-template-columns:1fr 1fr 1fr}
    .app-header{flex-direction:column;text-align:center;gap:0.5rem;padding:1rem}
}
</style>
""", unsafe_allow_html=True)

def _on_theme_toggle():
    st.session_state["ui_theme"] = "dark" if st.session_state.get("theme_toggle") else "light"

def render_theme_toggle():
    if "ui_theme" not in st.session_state:
        st.session_state["ui_theme"] = _default_theme()
    if "theme_toggle" not in st.session_state:
        st.session_state["theme_toggle"] = st.session_state["ui_theme"] == "dark"
    _, col_theme = st.columns([6, 1])
    with col_theme:
        st.toggle(
            "Modo oscuro",
            key="theme_toggle",
            on_change=_on_theme_toggle,
            help="Cambia entre tema claro y oscuro. El naranja de marca se conserva.",
        )

# ======================================
# Autenticación Básica
# ======================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    configurada = bool(st.secrets.get("APP_PASSWORD"))
    st.markdown("""
    <div class="auth-wrap">
        <div class="auth-icon">◈</div>
        <div class="auth-title">Sistema de Limpieza y Análisis</div>
        <div class="auth-sub">Ingresa tus credenciales para continuar</div>
    </div>""", unsafe_allow_html=True)
    if not configurada:
        st.warning("⚠️ No hay APP_PASSWORD en los Secrets: configura una contraseña antes de "
                   "publicar la app (Streamlit Cloud → Settings → Secrets).")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("pw"):
            pw = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
            if st.form_submit_button("Ingresar", use_container_width=True, type="primary"):
                if configurada and pw == st.secrets.get("APP_PASSWORD"):
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
    return False

# ======================================
# Configuración vía Google Sheets
# ======================================
CONFIG_CACHE_TTL = 300

@st.cache_data(ttl=CONFIG_CACHE_TTL, show_spinner=False)
def _fetch_map_from_csv(csv_url: str) -> dict:
    df = pd.read_csv(csv_url, header=None, dtype=str)
    df = df.dropna(how="all")
    mapping = pd.Series(
        df.iloc[:, 1].values,
        index=df.iloc[:, 0].astype(str).str.lower().str.strip()
    ).to_dict()
    mapping = {k: v for k, v in mapping.items() if k not in ("nan", "")}
    return mapping

def load_config_from_sheets():
    regiones_url = st.secrets.get("REGIONES_CSV_URL")
    internet_url = st.secrets.get("INTERNET_CSV_URL")

    if not regiones_url or not internet_url:
        st.error("❌ Faltan REGIONES_CSV_URL e INTERNET_CSV_URL en st.secrets.")
        st.stop()

    try:
        region_map = _fetch_map_from_csv(regiones_url)
        internet_map = _fetch_map_from_csv(internet_url)
    except Exception as e:
        st.error(f"❌ No se pudo leer la configuración desde Google Sheets: {e}")
        st.stop()

    return region_map, internet_map

def refresh_config_cache():
    _fetch_map_from_csv.clear()

# ======================================
# Proceso Principal
# ======================================
PIPELINE_STEPS = [
    ("config", "Cargar configuración"),
    ("read", "Leer el Excel"),
    ("norm", "Limpiar y normalizar"),
    ("dups", "Menciones y duplicadas"),
    ("ai", "Análisis IA (Tono, Tema, Subtema)"),
    ("export", "Generar archivo de resultado"),
]

def _fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} s"
    return f"{seconds // 60} min {seconds % 60:02d} s"

def _fmt_size(n_bytes: int) -> str:
    if not n_bytes: return ""
    mb = n_bytes / (1024 * 1024)
    if mb < 0.1: return f"{n_bytes / 1024:.0f} KB"
    return f"{mb:.1f} MB"

def _active_step(pct: int, msg: str) -> str:
    if pct >= 100 or "completad" in msg.lower():
        return "done"
    if pct >= 94 or "Generando archivo" in msg or "Guardando" in msg:
        return "export"
    if pct >= 70 or "IA" in msg or "Analizando" in msg or "semántica" in msg:
        return "ai"
    if pct >= 55 or "duplicad" in msg.lower() or "Expandiendo" in msg:
        return "dups"
    if pct >= 40 or "Normaliz" in msg or "Columnas" in msg:
        return "norm"
    if pct >= 8 or "Excel" in msg or "Leyendo" in msg:
        return "read"
    return "config"

def _render_live_html(pct, msg, elapsed, file_label, active_key):
    steps_html = []
    reached_active = False
    for key, label in PIPELINE_STEPS:
        if active_key == "done":
            cls, mark = "is-done", "✓"
        elif key == active_key:
            cls, mark = "is-active", "●"
            reached_active = True
        elif not reached_active:
            cls, mark = "is-done", "✓"
        else:
            cls, mark = "", ""
        steps_html.append(f'<div class="step-item {cls}"><span class="dot">{mark}</span>{label}</div>')
        
    file_line = f" · {html.escape(file_label)}" if file_label else ""
    title = "Limpieza completada" if active_key == "done" else "Procesando dossier de noticias"
    safe_msg = html.escape(str(msg or ""))
    
    return f"""
    <div class="live-panel">
      <div class="live-head">
        <div class="live-pulse"></div>
        <div>
          <div class="live-title">{title}</div>
          <div class="live-sub">El proceso sigue activo{file_line}. No cierres esta pestaña.</div>
        </div>
      </div>
      <div class="live-metrics">
        <div class="live-metric"><div class="live-metric-val">{int(pct)}%</div><div class="live-metric-lbl">Avance</div></div>
        <div class="live-metric"><div class="live-metric-val">{elapsed}</div><div class="live-metric-lbl">Tiempo</div></div>
        <div class="live-metric"><div class="live-metric-val">en curso</div><div class="live-metric-lbl">Estado</div></div>
      </div>
      <div class="step-list">{''.join(steps_html)}</div>
      <div class="live-hint">La deduplicación previa agrupa notas idénticas para procesar hasta 2.000 filas con alta velocidad.</div>
      <div class="live-detail">{safe_msg}</div>
    </div>
    """

def run_cleaning_process(df_file, file_meta=None, ai_config=None):
    file_meta = file_meta or {}
    file_label = file_meta.get("name", "")
    size_lbl = _fmt_size(file_meta.get("size") or 0)
    if file_label and size_lbl:
        file_label = f"{file_label} ({size_lbl})"

    t_start = time.time()
    panel = st.empty()
    progress_bar = st.progress(0, text="Iniciando…")

    def paint(pct, msg):
        elapsed = _fmt_elapsed(time.time() - t_start)
        active = _active_step(pct, msg)
        panel.markdown(_render_live_html(pct, msg, elapsed, file_label, active), unsafe_allow_html=True)
        progress_bar.progress(min(100, max(0, int(pct))), text=msg)

    paint(1, "Cargando configuración…")

    with st.status("Procesando dossier…", expanded=True) as status_widget:
        def on_progress(pct, msg):
            paint(pct, msg)
            status_widget.update(label=f"{int(pct)}% · {msg}")

        try:
            region_map, internet_map = load_config_from_sheets()
            result = process_dossier(
                df_file,
                region_map,
                internet_map,
                progress=on_progress,
                ai_config=ai_config
            )
            paint(100, "Limpieza completada")
            status_widget.update(label="✓ Limpieza completada con éxito", state="complete")
            time.sleep(0.4)
        except Exception as exc:
            logger.exception("Fallo en el proceso de limpieza")
            status_widget.update(label="Error durante el procesamiento", state="error")
            st.error(f"El proceso se interrumpió: {exc}")
            raise

    st.session_state["medios_sin_mapear"] = result.get("medios_sin_mapear") or None
    st.session_state["analisis"] = result.get("analisis") or {}
    st.session_state["output_data"] = result["output_data"]
    st.session_state["output_filename"] = result["output_filename"]
    st.session_state["processing_complete"] = True
    st.session_state.update({
        "total_rows": result["total_rows"],
        "unique_rows": result["unique_rows"],
        "duplicates": result["duplicates"],
        "process_duration": result["process_duration"],
    })

# ======================================
# Interfaz de Usuario
# ======================================
def main():
    st.set_page_config(
        page_title="Limpieza y Análisis de Noticias",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    load_custom_css()
    render_theme_toggle()
    if not check_password(): return

    st.markdown("""
    <div class="app-header">
        <div class="app-header-icon">◈</div>
        <div class="app-header-text">
            <div class="app-header-title">Limpieza y Análisis de Noticias</div>
            <div class="app-header-version">v4.0 · Tono/Tema/Subtema por reglas + IA · Realizado por Johnathan Cortés</div>
        </div>
        <div class="app-header-badge">Estructurador + IA</div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.get("pending_dossier"):
        blob = st.session_state.pop("pending_dossier")
        meta = st.session_state.pop("pending_meta", {}) or {}
        ai_cfg = st.session_state.pop("pending_ai_config", None)
        run_cleaning_process(io.BytesIO(blob), meta, ai_config=ai_cfg)
        st.rerun()

    if not st.session_state.get("processing_complete", False):
        col_cfg1, col_cfg2 = st.columns([4, 1])
        with col_cfg1:
            st.markdown(
                '<span class="config-badge">⚙ Configuración: Google Sheets (Regiones / Internet)</span>',
                unsafe_allow_html=True
            )
        with col_cfg2:
            if st.button("↻ Refrescar config", use_container_width=True):
                refresh_config_cache()
                st.success("Config recargada")

        with st.form("main_form"):
            st.markdown('<div class="sec-label">1. Sube el archivo de entrada</div>', unsafe_allow_html=True)
            st.markdown("""
            <div class="upload-zone">
                <div class="upload-zone-card">
                    <div class="upload-zone-icon uz-dossier">📋</div>
                    <div class="upload-zone-text">
                        <div class="upload-zone-title">Dossier de Noticias</div>
                        <div class="upload-zone-desc">Sube el .xlsx con las columnas Título y Resumen - Aclaracion.</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
            
            f1 = st.file_uploader("Dossier", type=["xlsx"], label_visibility="collapsed", key="f1")

            st.markdown('<div class="sec-label">2. Configuración de Análisis IA (Tono, Tema, Subtema)</div>', unsafe_allow_html=True)
            enable_ai = st.checkbox("Activar análisis reputacional con IA (gpt-4.1-nano-2025-04-14)", value=True)
            
            c_brand, c_alias = st.columns(2)
            with c_brand:
                brand_input = st.text_input(
                    "Marca o Cliente Principal*",
                    placeholder="Ej: Universidad de Antioquia, Ecopetrol, Bancolombia",
                    help="El tono se mide solo sobre esta marca, sus voceros y sus alias."
                )
            with c_alias:
                alias_input = st.text_input(
                    "Alias o términos relacionados (separados por coma o punto y coma)",
                    placeholder="Ej: UdeA; Alma Mater; rectoría; la universidad",
                    help="Variantes del nombre que deban atribuirse al cliente."
                )

            c_crit, c_voc = st.columns([3, 2])
            with c_crit:
                criterio = st.radio(
                    "Criterio del tono",
                    list(CRITERIOS_TONO.keys()),
                    index=0,
                    horizontal=False,
                    help=("Aspectual estricto: la crítica dirigida a la marca es lo único Negativo "
                          "(gobiernos, alcaldías, entidades públicas). Favorabilidad del sector: "
                          "cuenta cómo queda parado el sector aunque la marca no sea el actor (gremios, "
                          "cámaras, empresas de un sector)."),
                )
            with c_voc:
                voceros_input = st.text_input(
                    "Vocero(s) de la marca (opcional)",
                    placeholder="Ej: Gonzalo Moreno; el rector",
                    help="Personas cuyo nombre se atribuye a la marca para el tono."
                )
                tax_nombre = st.selectbox(
                    "Lista de Temas",
                    ["Automática según el archivo (recomendada)",
                     "Gobierno territorial (21 cubos)",
                     "Gremio o sector (16 cubos)"],
                    index=0,
                    help="Los clientes son muy distintos (universidades, sector público, privado, marcas), "
                         "así que lo recomendado es que la lista de Temas se genere leyendo los hechos "
                         "de este archivo. También puedes reutilizar la lista de un cliente concreta o "
                         "cargar una en JSON.",
                )

            with st.expander("⚙ Ajustes finos del análisis (opcional)"):
                ca, cb, cc, cd = st.columns(4)
                with ca:
                    tam_lote_input = st.slider("Grupos por llamada", 5, 30, 10, 1,
                                               help="Con gpt-4.1-nano 10 funciona mejor.")
                with cb:
                    workers_input = st.slider("Llamadas en paralelo", 1, 8, 4, 1,
                                              help="Sube para dossiers grandes; más hilos, más velocidad.")
                with cc:
                    umbral_titulo_input = st.slider("Similitud de titulares (%)", 75, 100, 92, 1,
                                                    help="Bájalo para fusionar la misma noticia publicada por "
                                                         "muchos medios con titulares distintos.")
                with cd:
                    umbral_cuerpo_input = st.slider("Similitud de resúmenes (%)", 70, 100, 85, 1)
                tax_file = st.file_uploader(
                    "Reutilizar la lista de Temas de un cliente (JSON, opcional)",
                    type=["json"], key="tax_json",
                    help="Si subes la lista que descargaste de un período anterior del mismo cliente, "
                         "los Temas se mantienen idénticos entre meses (mejor para comparar).",
                )
                cubos_objetivo_input = st.slider("Cubos objetivo cuando la lista es automática", 8, 25, 16, 1)
                votos_input = st.slider(
                    "Verificaciones del tono por grupo", 1, 3, 2, 1,
                    help="Cada grupo se etiqueta N veces y gana la mayoría; un empate cae a Neutro. "
                         "Con 2 se reducen los vaivenes de los modelos pequeños; con 3 sube el costo "
                         "una vez más.")

            st.markdown('<div class="sec-label">3. Modelos PKL del cliente (opcional)</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="pkl-hint">Puedes subir el PKL de tono, el de tema, ambos o ninguno. '
                "Si un eje no tiene PKL, se mantiene el análisis actual (IA). "
                "El subtema nunca se reemplaza por PKL.</div>",
                unsafe_allow_html=True,
            )
            st.markdown("""
            <div class="upload-zone">
                <div class="upload-zone-card">
                    <div class="upload-zone-icon uz-pkl">◆</div>
                    <div class="upload-zone-text">
                        <div class="upload-zone-title">Clasificadores sklearn (joblib)</div>
                        <div class="upload-zone-desc">Archivos .pkl con pipeline de texto (pasos tfidf + clf). No son obligatorios.</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
            c_tono, c_tema = st.columns(2)
            with c_tono:
                f_tono = st.file_uploader(
                    "PKL de tono",
                    type=["pkl"],
                    key="pkl_tono",
                    help="Modelo opcional de scikit-learn para tono. Si no se sube, se usa la IA existente.",
                )
            with c_tema:
                f_tema = st.file_uploader(
                    "PKL de tema",
                    type=["pkl"],
                    key="pkl_tema",
                    help="Modelo opcional de scikit-learn para tema. Si no se sube, se usa la IA existente.",
                )

            if st.form_submit_button("▶ Iniciar Limpieza y Análisis", use_container_width=True, type="primary"):
                if not f1:
                    st.error("Por favor, sube un archivo Excel.")
                elif enable_ai and not brand_input.strip():
                    st.error("Por favor indica la Marca o Cliente Principal para realizar el análisis enfocado.")
                else:
                    api_key = st.secrets.get("OPENAI_API_KEY")
                    if enable_ai and not api_key:
                        st.error("❌ Falta configurar OPENAI_API_KEY en los Secrets de Streamlit.")
                        st.stop()
                    
                    aliases_parsed = [
                        a.strip() for a in re.split(r"[,;]", alias_input) if a.strip()
                    ]
                    tax_cargada = None
                    if tax_file is not None:
                        try:
                            tax_cargada = json.loads(tax_file.getvalue().decode("utf-8"))
                            if not isinstance(tax_cargada, dict) or not tax_cargada.get("temas"):
                                raise ValueError("el JSON debe traer la clave 'temas' con la lista de cubos")
                            tax_cargada.setdefault("reglas", [])
                        except Exception as exc:
                            st.error(f"La lista de Temas (JSON) no es válida: {exc}")
                            st.stop()
                    tone_bytes = f_tono.getvalue() if f_tono else None
                    theme_bytes = f_tema.getvalue() if f_tema else None
                    try:
                        if tone_bytes:
                            load_sklearn_estimator(tone_bytes, "tono")
                        if theme_bytes:
                            load_sklearn_estimator(theme_bytes, "tema")
                    except PklClassifierError as exc:
                        st.error(str(exc))
                        st.stop()

                    st.session_state["pending_dossier"] = f1.getvalue()
                    st.session_state["pending_meta"] = {
                        "name": f1.name,
                        "size": int(getattr(f1, "size", 0) or len(st.session_state["pending_dossier"])),
                    }
                    if enable_ai or tone_bytes or theme_bytes:
                        st.session_state["pending_ai_config"] = {
                            "enabled": bool(enable_ai),
                            "brand": brand_input.strip(),
                            "aliases": aliases_parsed,
                            "voceros": [v.strip() for v in re.split(r"[,;]", voceros_input) if v.strip()],
                            "criterio": criterio,
                            "taxonomia": tax_cargada if tax_cargada else tax_nombre,
                            "cubos_objetivo": int(cubos_objetivo_input),
                            "votos": int(votos_input),
                            "permitir_cubos_nuevos": True,
                            "tam_lote": int(tam_lote_input),
                            "workers": int(workers_input),
                            "umbral_titulo": int(umbral_titulo_input),
                            "umbral_cuerpo": int(umbral_cuerpo_input),
                            "api_key": api_key if enable_ai else None,
                            "model": "gpt-4.1-nano-2025-04-14",
                            "tone_pkl_bytes": tone_bytes,
                            "theme_pkl_bytes": theme_bytes,
                        }
                    else:
                        st.session_state["pending_ai_config"] = None

                    st.rerun()
    else:
        total = st.session_state.total_rows
        uniq  = st.session_state.unique_rows
        dups  = st.session_state.duplicates
        dur   = st.session_state.process_duration
        
        st.markdown(
            '<div class="success-banner"><div class="success-icon">✓</div>'
            '<div><div class="success-title">Proceso completado</div>'
            '<div class="success-sub">El archivo estructurado y analizado con IA se encuentra listo para descargar</div></div></div>',
            unsafe_allow_html=True
        )

        medios_sin_mapear = st.session_state.get("medios_sin_mapear")
        if medios_sin_mapear:
            st.warning(
                "⚠️ Medios sin región asignada en Sheets (quedaron N/A): "
                f"{', '.join(medios_sin_mapear)}."
            )

        analisis = st.session_state.get("analisis") or {}
        if analisis:
            grupos = analisis.get("grupos")
            cubos_nuevos = analisis.get("cubos_nuevos") or []
            reglas = analisis.get("temas_por_regla")
            por_llm = analisis.get("temas_por_llm")
            fallback = len(analisis.get("grupos_con_fallback") or [])
            errores = analisis.get("errores_api") or []
            guarda = len(analisis.get("tono_corregido_por_guarda") or [])
            votos = analisis.get("votos_tono")
            piezas = []
            if grupos:
                piezas.append(f"{grupos} hechos únicos agrupados")
            if votos:
                piezas.append(f"tono verificado {votos}× por grupo")
            if guarda:
                piezas.append(f"guarda del tono: {guarda} Negativos sin señalamiento pasaron a Neutro")
            if reglas is not None:
                piezas.append(f"Tema por reglas: {reglas} · por IA: {por_llm or 0}")
            if cubos_nuevos:
                piezas.append("Cubos nuevos específicos: " + ", ".join(cubos_nuevos[:4]))
            if fallback:
                piezas.append(f"⚠️ {fallback} etiquetas con respaldo determinista")
            if piezas:
                st.info("Análisis de Tono/Tema/Sub-tema · " + " · ".join(piezas))
            if errores:
                st.caption("Avisos del modelo: " + " | ".join(map(str, errores[:2])))
            temas_gen = analisis.get("taxonomia") or []
            detalle_tax = analisis.get("taxonomia_detalle") or {}
            if temas_gen:
                modo = analisis.get("modo_taxonomia")
                etiqueta = ("generada desde el archivo" if modo == "automatica"
                            else "lista fija del cliente")
                with st.expander("Lista de Temas usada (%d cubos, %s)" % (len(temas_gen), etiqueta),
                                 expanded=(modo == "automatica")):
                    st.markdown(" · ".join("`%s`" % t for t in temas_gen))
                    if detalle_tax:
                        st.download_button(
                            "⬇ Descargar lista de Temas (JSON) para reutilizarla",
                            data=json.dumps(detalle_tax, ensure_ascii=False, indent=1),
                            file_name="temas_%s.json" % str(
                                st.session_state.get("output_filename", "cliente")).replace(".xlsx", ""),
                            mime="application/json",
                        )
                        st.caption("Súbela en «Reutilizar la lista de Temas de un cliente» para que el "
                                   "próximo período del mismo cliente use los mismos Temas y puedas "
                                   "comparar entre meses.")
        
        st.markdown(f"""
        <div class="metrics-grid">
          <div class="metric-card m-total"><div class="metric-val" style="color:var(--text)">{total}</div><div class="metric-lbl">Total Registros</div></div>
          <div class="metric-card m-unique"><div class="metric-val" style="color:var(--green)">{uniq}</div><div class="metric-lbl">Únicos</div></div>
          <div class="metric-card m-dup"><div class="metric-val" style="color:var(--amber)">{dups}</div><div class="metric-lbl">Duplicados</div></div>
          <div class="metric-card m-time"><div class="metric-val" style="color:var(--blue)">{dur}</div><div class="metric-lbl">Tiempo de Ejecución</div></div>
        </div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        c1.download_button(
            "⬇ Descargar Xlsx Estructurado con IA",
            data=st.session_state.output_data,
            file_name=st.session_state.output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
        if c2.button("Nuevo análisis", use_container_width=True):
            pwd = st.session_state.get("password_correct")
            theme = st.session_state.get("ui_theme")
            st.session_state.clear()
            st.session_state.password_correct = pwd
            if theme in ("dark", "light"):
                st.session_state.ui_theme = theme
            st.rerun()

    st.markdown(
        '<div class="footer">Estructuración y Limpieza · Johnathan Cortés ©</div>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
