"""ContaBlue: cuenta flores y bayas de arándano con una foto (Roboflow) y estima la producción.

Ejecutar:  streamlit run app.py     (requiere Streamlit >= 1.52)
"""
import hashlib
import io
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image

import nucleo

try:
    import imagenes_guia
    _ICONO = imagenes_guia.imagen("icono")
except Exception:  # sin el módulo de imágenes la app funciona igual
    imagenes_guia, _ICONO = None, "🫐"

st.set_page_config(
    page_title="ContaBlue · Conteo de arándanos",
    page_icon=_ICONO,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =====================================================================
# Estilo (paleta arándano, pensado para celular)
# =====================================================================
st.markdown(
    """
<style>
.block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 760px; }
footer { visibility: hidden; }

/* ---------- Cabecera ---------- */
.hero { position: relative; overflow: hidden; color: #fff;
  background: linear-gradient(135deg, #1b1f4b 0%, #3f4a9e 60%, #5d6cd6 100%);
  padding: 1.5rem 1.5rem 1.3rem 1.5rem; border-radius: 24px; margin-bottom: 1rem;
  box-shadow: 0 10px 26px rgba(27, 31, 75, 0.30); }
.hero .titulo { font-size: 2.2rem; font-weight: 800; letter-spacing: -0.5px; line-height: 1.05; }
.hero .sub { opacity: 0.92; margin-top: 0.4rem; font-size: 1rem; max-width: 80%; }
.hero .chips { margin-top: 0.8rem; }
.hero .chip { display: inline-block; background: rgba(255,255,255,0.16); border-radius: 999px;
  padding: 0.18rem 0.7rem; font-size: 0.82rem; margin: 0 0.3rem 0.3rem 0; }
.bola { position: absolute; border-radius: 50%;
  background: radial-gradient(circle at 30% 28%, #9aa6ff 0%, #4b5cc4 42%, #1b1f4b 100%);
  box-shadow: inset -4px -6px 10px rgba(0,0,0,0.25); }
.bola::after { content: ""; position: absolute; top: 12%; left: 40%; width: 20%; height: 20%;
  border-radius: 50%; background: rgba(15,18,50,0.55); }
.b1 { width: 92px; height: 92px; right: -14px; top: -18px; opacity: 0.95; }
.b2 { width: 58px; height: 58px; right: 78px; bottom: -14px; opacity: 0.85; }
.b3 { width: 38px; height: 38px; right: 22px; bottom: 34px; opacity: 0.8; }

/* ---------- Pestañas ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; overflow-x: auto; padding-bottom: 0.2rem; }
.stTabs [data-baseweb="tab"] { background: #ffffff; border: 1px solid #dfe3f5; border-radius: 999px;
  padding: 0.45rem 1rem; height: auto; white-space: nowrap; color: #3f4a9e; font-weight: 600; }
.stTabs [aria-selected="true"] { background: #4b5cc4; color: #ffffff !important; border-color: #4b5cc4; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* ---------- Secciones ---------- */
.paso { display: flex; align-items: center; gap: 0.6rem; margin: 1.3rem 0 0.4rem 0;
  font-size: 1.2rem; font-weight: 800; color: #1b1f4b; }
.paso .num { background: #4b5cc4; color: #fff; width: 1.8rem; height: 1.8rem; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center; font-size: 0.95rem; }
.subt { color: #5b6190; font-size: 0.92rem; margin-bottom: 0.4rem; }

/* ---------- Tarjetas y métricas ---------- */
[data-testid="stMetric"] { background: #ffffff; border: 1px solid #dfe3f5; border-radius: 18px;
  padding: 0.8rem 1rem; box-shadow: 0 2px 10px rgba(27, 31, 75, 0.07); }
[data-testid="stMetricLabel"] { color: #5b6190; }
[data-testid="stMetricValue"] { color: #1b1f4b; font-weight: 800; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; }
.stButton > button, .stDownloadButton > button { border-radius: 14px; font-weight: 700; min-height: 3rem; }
img { border-radius: 16px; }

/* En celular las columnas se quedan lado a lado (no se apilan) */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.5rem !important; }
  [data-testid="stColumn"], [data-testid="column"] { min-width: 0 !important; flex: 1 1 0 !important; width: auto !important; }
  [data-testid="stMetric"] { padding: 0.6rem 0.6rem; }
  [data-testid="stMetricValue"] { font-size: 1.35rem; }
  .hero .titulo { font-size: 1.9rem; } .hero .sub { max-width: 100%; }
}

/* ---------- Estado de madurez y resultado ---------- */
.estado { border-radius: 14px; padding: 0.6rem 1rem; font-weight: 700; margin: 0.5rem 0 0.7rem 0; color: #fff; }
.estado.madura { background: #4b5cc4; } .estado.verde { background: #2f9e6e; } .estado.mezcla { background: #7a6ad8; }
.resultado { color: #fff; border-radius: 24px; padding: 1.4rem 1.5rem; margin: 0.8rem 0;
  background: linear-gradient(135deg, #1b1f4b 0%, #3f4a9e 100%); box-shadow: 0 10px 26px rgba(27, 31, 75, 0.28); }
.resultado .etq { font-size: 0.95rem; opacity: 0.9; }
.resultado .valor { font-size: 2.6rem; font-weight: 800; line-height: 1.1; }
.resultado .margen { font-size: 1rem; opacity: 0.95; margin-top: 0.1rem; }
.resultado .det { font-size: 0.92rem; opacity: 0.9; margin-top: 0.5rem; }
.resultado .ton { margin-top: 0.7rem; padding-top: 0.6rem; border-top: 1px solid rgba(255,255,255,0.25);
  font-size: 1.05rem; font-weight: 700; }
.badge { display: inline-block; border-radius: 999px; padding: 0.15rem 0.8rem; font-size: 0.82rem;
  font-weight: 700; color: #fff; margin-left: 0.5rem; vertical-align: middle; }
.badge.alta { background: #2f9e6e; } .badge.media { background: #e0a100; } .badge.baja { background: #d9534f; }
.vacio { text-align: center; padding: 2rem 1rem; color: #5b6190; background: #fff;
  border: 1px dashed #b9c0ee; border-radius: 20px; }
.vacio .ico { font-size: 2.4rem; }
.inicio { background: #fff; border: 1px solid #dfe3f5; border-left: 6px solid #4b5cc4; border-radius: 16px;
  padding: 0.9rem 1.1rem; margin-bottom: 0.8rem; color: #1b1f4b; }
</style>
""",
    unsafe_allow_html=True,
)


def paso(numero, texto):
    st.markdown(f'<div class="paso"><span class="num">{numero}</span>{texto}</div>', unsafe_allow_html=True)


# =====================================================================
# Estado, valores por defecto y recuperación desde el enlace
# =====================================================================
def secreto(nombre, defecto=""):
    try:
        return st.secrets.get(nombre, defecto)
    except Exception:
        return defecto


DEFECTOS = {
    "api_key": secreto("ROBOFLOW_API_KEY"),
    "model_id": secreto("ROBOFLOW_MODEL_ID"),
    "confianza": 0.40,
    "solape": 0.50,
    "clases_flor": "flor, flores, flower",
    "clases_verde": "baya_verde, verde, green, unripe",
    "clases_madura": "baya_madura, madura, maduro, ripe, azul",
    "unidades_ha": 10000.0,
    "factor_oclusion": 1.30,
    "tasa_cuajado": 0.60,
    "peso_baya": 2.0,
    "area_ha": 1.0,
    "responsable": "",
    "hoja_url": secreto("SHEETS_URL"),
    "hoja_token": secreto("SHEETS_TOKEN"),
    "hoja_enlace": secreto("SHEETS_LINK"),
    "hoja_auto": True,
}
# Ajustes que se guardan en el enlace (nunca la API key)
PERSISTENTES = ["confianza", "solape", "clases_flor", "clases_verde", "clases_madura",
                "unidades_ha", "factor_oclusion", "tasa_cuajado", "peso_baya", "area_ha", "responsable"]

for k, v in DEFECTOS.items():
    st.session_state.setdefault(k, v)
for k, v in {"muestras": [], "calib": [], "ver": 0, "ed_ver": 0, "mosaicos": False}.items():
    st.session_state.setdefault(k, v)

if "restaurado" not in st.session_state:
    st.session_state.restaurado = True
    cod = st.query_params.get("d")
    if cod:
        try:
            est = nucleo.decodificar_estado(cod)
            rec = [nucleo.sanear_muestra(m) for m in est.get("m", []) if isinstance(m, dict)][:500]
            st.session_state.muestras = rec
            for k, v in est.get("a", {}).items():
                if k in PERSISTENTES:
                    if isinstance(DEFECTOS[k], float) and isinstance(v, (int, float)):
                        st.session_state[k] = float(v)
                    elif isinstance(DEFECTOS[k], str) and isinstance(v, str):
                        st.session_state[k] = v
            if rec:
                st.session_state.flash = f"💾 Se recuperaron {len(rec)} muestras que tenías guardadas."
        except Exception:
            pass  # enlace inválido: se ignora

VARIEDADES = ["Biloxi", "Ventura", "Emerald", "Snowchaser", "Sekoya Pop", "Legacy", "Duke", "Misty", "Otra"]
ETAPAS = ["Floración", "Cuajado", "Fruto verde", "Maduración", "Cosecha"]
UNIDADES = ["Planta", "Metro de hilera", "Rama"]
MUESTRAS_META = 20
NUEVO_LOTE = "➕ Nuevo lote…"


def csv_lista(texto):
    return [c.strip() for c in texto.split(",") if c.strip()]


def mensaje_error(e):
    t = str(e)
    tl = t.lower()
    if any(s in tl for s in ("401", "403", "unauthorized", "forbidden", "invalid api key")):
        return "La **API key** no es válida o no tiene permiso. Revísala en ⚙️ Ajustes → Conexión."
    if "404" in tl or "not found" in tl or "no such model" in tl:
        return "No se encontró el modelo. Revisa que el **Model ID** esté bien copiado y que el modelo esté entrenado."
    if any(s in tl for s in ("timeout", "timed out", "connection", "resolve", "unreachable")):
        return "No hay conexión con Roboflow. Revisa tu internet e inténtalo de nuevo."
    if "429" in tl or "rate" in tl or "quota" in tl or "limit" in tl:
        return "Se alcanzó el límite de uso de tu cuenta de Roboflow. Espera un momento o revisa tu plan."
    return f"No se pudo analizar la foto: {t[:200]}"


def mensaje_hoja_error(e):
    t = str(e)
    tl = t.lower()
    if any(s in tl for s in ("timeout", "timed out", "connection", "resolve", "unreachable", "max retries")):
        return ("Sin conexión con tu hoja. La muestra quedó guardada en el celular; "
                "podrás enviarla después desde 📊 Resumen.")
    if "404" in tl:
        return "No se encontró el script. Revisa la dirección (debe terminar en /exec)."
    return t[:220]


def hoja_configurada():
    return bool(st.session_state.hoja_url and st.session_state.hoja_token)


def enviar_pendientes(lista=None):
    """Envía a la hoja las muestras pendientes (o la lista dada). Devuelve (mensaje, ok)."""
    pend = lista if lista is not None else [m for m in st.session_state.muestras if m.get("sync") != "ok"]
    if not pend:
        return "No hay muestras pendientes de enviar.", True
    try:
        res = nucleo.enviar_a_hoja(st.session_state.hoja_url, st.session_state.hoja_token, pend)
    except Exception as e:
        return "⚠️ " + mensaje_hoja_error(e), False
    for m in pend:
        m["sync"] = "ok"
    return f"☁️ Enviadas a tu hoja: {res.get('agregadas', 0)} nuevas, {res.get('actualizadas', 0)} actualizadas.", True


# ---------- Callbacks (cambian ajustes antes de redibujar la pantalla) ----------
def agregar_par_calibracion():
    real, det = st.session_state.get("cal_real", 0), st.session_state.get("cal_det", 0)
    if det > 0:
        st.session_state.calib.append((int(real), int(det)))


def aplicar_factor():
    f = nucleo.factor_calibracion(st.session_state.calib)
    if f:
        st.session_state["factor_oclusion"] = round(min(max(f, 0.5), 3.0), 2)


def limpiar_calibracion():
    st.session_state.calib = []


def usar_valor(clave, valor):
    st.session_state[clave] = valor


def restablecer_ajustes():
    for k in PERSISTENTES:
        st.session_state[k] = DEFECTOS[k]


# =====================================================================
# Cabecera
# =====================================================================
n_total = len(st.session_state.muestras)
chip_guardado = '<span class="chip">💾 Autoguardado</span>' if n_total else ""
if hoja_configurada():
    chip_guardado += '<span class="chip">☁️ Hoja conectada</span>'
st.markdown(
    f"""
<div class="hero">
<div class="bola b1"></div><div class="bola b2"></div><div class="bola b3"></div>
<div class="titulo">ContaBlue</div>
<div class="sub">Cuenta flores y bayas de arándano con una foto y estima tu cosecha.</div>
<div class="chips"><span class="chip">📷 {n_total} muestras</span><span class="chip">🫐 Roboflow</span><span class="chip">📈 kg/ha</span>{chip_guardado}</div>
</div>
""",
    unsafe_allow_html=True,
)

tab_cap, tab_res, tab_aj, tab_guia = st.tabs(["📷 Capturar", "📊 Resumen", "⚙️ Ajustes", "📖 Guía"])

# =====================================================================
# AJUSTES (se define primero: Capturar y Resumen leen estos valores)
# =====================================================================
BLOQ_RF = bool(secreto("ROBOFLOW_API_KEY") and secreto("ROBOFLOW_MODEL_ID"))
BLOQ_HOJA = bool(secreto("SHEETS_URL") and secreto("SHEETS_TOKEN"))

with tab_aj:
    with st.expander("🔌 Conexión con Roboflow", expanded=not st.session_state.api_key):
        if BLOQ_RF:
            st.success("🔒 Conexión configurada de forma segura en el servidor. "
                       "La API key y el Model ID no se muestran aquí.")
        else:
            st.text_input("API key", type="password", key="api_key")
            st.text_input("Model ID (proyecto/versión)", placeholder="mi-proyecto/1", key="model_id")
        st.slider("Confianza mínima", 0.05, 0.95, step=0.05, key="confianza",
                  help="Súbela si detecta cosas que no son frutos; bájala si se le pasan frutos.")
        st.slider("Solape máximo (NMS)", 0.1, 0.9, step=0.05, key="solape",
                  help="Evita contar dos veces el mismo fruto.")
        if st.button("🔎 Probar conexión con Roboflow", width="stretch"):
            if not (st.session_state.api_key and st.session_state.model_id):
                st.warning("Escribe primero la API key y el Model ID.")
            else:
                try:
                    with st.spinner("Probando…"):
                        nucleo.detectar(Image.new("RGB", (96, 96), "white"), st.session_state.api_key,
                                        st.session_state.model_id, 0.5, 0.5)
                    st.success("✅ Conexión correcta: tu API key y tu modelo funcionan.")
                except Exception as e:
                    st.error(mensaje_error(e))

    with st.expander("☁️ Hoja de cálculo (Google Sheets)", expanded=not hoja_configurada()):
        st.caption("Guarda cada muestra en tu hoja de Google. Los pasos para conectarla están en la pestaña 📖 Guía.")
        if BLOQ_HOJA:
            st.success("🔒 Hoja conectada de forma segura en el servidor. La dirección y la clave no se muestran.")
        else:
            st.text_input("Dirección del script (termina en /exec)", key="hoja_url")
            st.text_input("Clave secreta", type="password", key="hoja_token")
        st.text_input("Enlace de tu hoja (opcional, para abrirla desde la app)", key="hoja_enlace")
        st.toggle("Enviar automáticamente al guardar cada muestra", key="hoja_auto")
        if st.button("🔎 Probar conexión con la hoja", width="stretch"):
            if not hoja_configurada():
                st.warning("Escribe primero la dirección del script y la clave secreta.")
            else:
                try:
                    with st.spinner("Probando…"):
                        nucleo.enviar_a_hoja(st.session_state.hoja_url, st.session_state.hoja_token, [], accion="probar")
                    st.success("✅ Conexión correcta: la app puede escribir en tu hoja.")
                except Exception as e:
                    st.error(mensaje_hoja_error(e))
        st.caption("Para no escribir estos datos cada vez, guárdalos en los *Secrets* de Streamlit "
                   "(SHEETS_URL, SHEETS_TOKEN y SHEETS_LINK).")

    with st.expander("🏷️ Clases del modelo"):
        st.caption("Escribe los nombres tal como están en tu proyecto de Roboflow, separados por coma.")
        st.text_input("Clases de flores", key="clases_flor")
        st.text_input("Clases de bayas VERDES", key="clases_verde")
        st.text_input("Clases de bayas MADURAS", key="clases_madura")

    with st.expander("🌱 Parámetros de producción", expanded=True):
        st.number_input("Unidades de muestreo por hectárea", min_value=1.0, step=500.0, key="unidades_ha",
                        help="Si cada foto es una planta: plantas por hectárea. Si es 1 m de hilera: metros de hilera por hectárea.")
        st.number_input("Factor de corrección por oclusión", min_value=0.5, max_value=3.0, step=0.05, key="factor_oclusion",
                        help="Frutos reales ÷ frutos detectados. Calcúlalo abajo con la calibración.")
        st.slider("Cuajado: flores que llegan a fruto", 0.0, 1.0, step=0.05, key="tasa_cuajado")
        st.number_input("Peso medio por baya (g)", min_value=0.1, step=0.1, key="peso_baya")
        st.button("↩️ Restablecer valores de ejemplo", on_click=restablecer_ajustes, width="stretch")

    with st.expander("🧰 Calculadoras de ayuda"):
        st.markdown("**Plantas o metros de hilera por hectárea**")
        h1, h2 = st.columns(2)
        d_hil = h1.number_input("Distancia entre hileras (m)", min_value=0.1, value=3.0, step=0.1, key="d_hil")
        d_pla = h2.number_input("Distancia entre plantas (m)", min_value=0.1, value=1.0, step=0.1, key="d_pla")
        plantas_ha = 10000.0 / (d_hil * d_pla)
        metros_ha = 10000.0 / d_hil
        g1, g2 = st.columns(2)
        g1.button(f"Usar {plantas_ha:,.0f} plantas/ha", on_click=usar_valor, args=("unidades_ha", float(round(plantas_ha))),
                  width="stretch")
        g2.button(f"Usar {metros_ha:,.0f} m de hilera/ha", on_click=usar_valor, args=("unidades_ha", float(round(metros_ha))),
                  width="stretch")

        st.markdown("**Peso medio de la baya**")
        p1, p2 = st.columns(2)
        n_b = p1.number_input("Nº de bayas pesadas", min_value=1, value=100, step=10, key="n_bayas_peso")
        g_b = p2.number_input("Peso total (g)", min_value=0.1, value=200.0, step=10.0, key="g_bayas_peso")
        prom = g_b / n_b
        st.button(f"Usar {prom:.2f} g por baya", on_click=usar_valor, args=("peso_baya", float(round(prom, 2))),
                  width="stretch")

        st.markdown("**Tasa de cuajado**")
        q1, q2 = st.columns(2)
        fl_m = q1.number_input("Flores marcadas", min_value=1, value=100, step=10, key="fl_marcadas")
        fr_c = q2.number_input("Frutos que cuajaron", min_value=0, value=60, step=5, key="fr_cuajados")
        tasa = min(fr_c / fl_m, 1.0)
        st.button(f"Usar cuajado de {tasa:.0%}", on_click=usar_valor, args=("tasa_cuajado", round(round(tasa / 0.05) * 0.05, 2)),
                  width="stretch")

    with st.expander("🎯 Calibrar el factor de oclusión"):
        st.caption("Cuenta a mano una planta o tramo y compara con lo que detecta la app. "
                   "Añade entre 10 y 30 pares y calcula el factor.")
        cc1, cc2 = st.columns(2)
        cc1.number_input("Conteo real (a mano)", min_value=0, step=1, key="cal_real")
        cc2.number_input("Conteo de la app", min_value=0, step=1, key="cal_det")
        st.button("➕ Añadir par", on_click=agregar_par_calibracion, width="stretch")
        if st.session_state.calib:
            st.dataframe(pd.DataFrame(st.session_state.calib, columns=["Real", "App"]), hide_index=True)
            f = nucleo.factor_calibracion(st.session_state.calib)
            if f:
                st.metric("Factor calculado", f"{f:.2f}")
                b1, b2 = st.columns(2)
                b1.button("✅ Usar este factor", on_click=aplicar_factor, width="stretch")
                b2.button("🗑️ Borrar pares", on_click=limpiar_calibracion, width="stretch")

# Lectura de ajustes
api_key = st.session_state.api_key
model_id = st.session_state.model_id
clases_flor = csv_lista(st.session_state.clases_flor)
clases_verde = csv_lista(st.session_state.clases_verde)
clases_madura = csv_lista(st.session_state.clases_madura)
clases_baya = clases_verde + clases_madura
NOMBRES = {c: "Flor" for c in clases_flor}
NOMBRES.update({c: "Verde" for c in clases_verde})
NOMBRES.update({c: "Madura" for c in clases_madura})
COLORES_CLASE = {c: "#e879a6" for c in clases_flor}
COLORES_CLASE.update({c: "#2f9e6e" for c in clases_verde})
COLORES_CLASE.update({c: "#4b5cc4" for c in clases_madura})
params = (st.session_state.unidades_ha, st.session_state.factor_oclusion,
          st.session_state.tasa_cuajado, st.session_state.peso_baya)


def analizar(img, usar_mosaicos):
    def una(tile):
        return nucleo.detectar(tile, api_key, model_id, st.session_state.confianza, st.session_state.solape)
    return nucleo.detectar_mosaicos(img, una) if usar_mosaicos else una(img)


# =====================================================================
# CAPTURAR
# =====================================================================
with tab_cap:
    if st.session_state.get("flash"):
        _f = st.session_state.pop("flash")
        (st.warning if "⚠️" in _f else st.success)(_f)

    if not st.session_state.muestras:
        st.markdown(
            '<div class="inicio"><b>Cómo empezar</b><br>'
            '1️⃣ Elige el lote y la variedad.<br>2️⃣ Toma una foto de la planta o del tramo.<br>'
            '3️⃣ Revisa el conteo y pulsa <b>Guardar muestra</b>.<br>'
            '4️⃣ Repite en 20 puntos del lote y mira el resultado en <b>📊 Resumen</b>.</div>',
            unsafe_allow_html=True,
        )

    lotes_exist = sorted({m["lote"] for m in st.session_state.muestras})
    with st.container(border=True):
        st.markdown("**📍 Datos de la muestra**")
        c1, c2 = st.columns(2)
        opciones = lotes_exist + [NUEVO_LOTE]
        ultimo = st.session_state.get("ultimo_lote")
        idx = opciones.index(ultimo) if ultimo in opciones else 0
        sel_lote = c1.selectbox("Lote / parcela", opciones, index=idx)
        variedad = c2.selectbox("Variedad", VARIEDADES)
        if sel_lote == NUEVO_LOTE:
            lote = st.text_input("Nombre del lote nuevo", value=f"Lote {len(lotes_exist) + 1}")
        else:
            lote = sel_lote
        with st.expander("Más datos (opcional)"):
            c3, c4 = st.columns(2)
            etapa = c3.selectbox("Etapa del cultivo", ETAPAS)
            unidad = c4.selectbox("Unidad de muestreo", UNIDADES)
            st.text_input("Tu nombre (responsable)", key="responsable", placeholder="Ana Pérez")
            etiqueta = st.text_input("Etiqueta", placeholder="Hilera 4 - planta 12")
            nota = st.text_input("Nota", placeholder="Sombra, poda reciente…")

    modo = st.radio("Modo de conteo", ["🤖 Automático (Roboflow)", "✍️ Manual (sin modelo)"], horizontal=True)
    automatico = modo.startswith("🤖")
    if automatico:
        st.toggle("🔬 Alta precisión (mosaicos)", key="mosaicos",
                  help="Analiza la foto en 4 partes. Detecta mejor las bayas muy pequeñas o lejanas, "
                       "pero tarda más y usa 4 consultas por foto.")
        if not (api_key and model_id):
            st.info("Para el modo automático completa la **API key** y el **Model ID** en la pestaña "
                    "**⚙️ Ajustes**. Mientras tanto puedes usar el modo manual.")

    paso(1, "Toma la foto")
    st.markdown(f'<div class="subt">Misma distancia y encuadre en todas las fotos: cada foto es una '
                f'unidad de muestreo ({unidad.lower()}).</div>', unsafe_allow_html=True)
    origen = st.radio("Origen de la foto", ["📱 Tomar o subir foto", "📸 Cámara en vivo"], horizontal=True,
                      label_visibility="collapsed")
    if origen.startswith("📱"):
        archivo = st.file_uploader("Toca aquí y elige: cámara o galería", key=f"up_{st.session_state.ver}",
                                   help="Acepta fotos de la galería en cualquier formato (JPG, PNG, HEIC, etc.).")
        st.caption("Elige «Cámara» o «Galería» cuando el celular te lo pregunte.")
    else:
        archivo = st.camera_input("Fotografía la planta o el tramo de hilera", key=f"cam_{st.session_state.ver}")
        st.caption("Si se abre la cámara frontal, cambia de cámara en el navegador o usa «Tomar o subir foto».")

    flores = verdes = maduras = 0
    hay_foto = archivo is not None
    pred = img = None
    huella = None
    if hay_foto:
        datos = archivo.getvalue()
        huella = hashlib.md5(datos).hexdigest()
        usar_mos = bool(st.session_state.mosaicos and automatico)

        if st.session_state.get("firma_img") != (huella, usar_mos):
            st.session_state.firma_img = (huella, usar_mos)
            st.session_state.pred = None
            st.session_state.error = None
            try:
                st.session_state.img = nucleo.preparar_imagen(io.BytesIO(datos), 1600 if usar_mos else 1280)
            except Exception as e:
                st.session_state.img = None
                st.session_state.error = ("Ese archivo no parece una foto que pueda leer. Prueba con otra foto de la galería "
                                          "o toma una nueva con la cámara.")

        if (automatico and api_key and model_id and st.session_state.get("pred") is None
                and st.session_state.get("img") is not None and not st.session_state.get("error")):
            with st.spinner("Detectando flores y bayas…" + (" (mosaicos)" if usar_mos else "")):
                try:
                    st.session_state.pred = analizar(st.session_state.img, usar_mos)
                except Exception as e:
                    st.session_state.error = mensaje_error(e)

        paso(2, "Resultado")
        if st.session_state.get("error"):
            st.error(st.session_state.error)
        pred = st.session_state.get("pred")
        img = st.session_state.get("img")

        if automatico and api_key and model_id and (pred is not None or st.session_state.get("error")):
            if st.button("🔄 Volver a analizar", width="stretch"):
                st.session_state.pred = None
                st.session_state.error = None
                st.rerun()

        if img is not None:
            if automatico and pred is not None:
                t1, t2 = st.columns(2)
                mostrar_cajas = t1.toggle("Mostrar cajas", value=True)
                mostrar_nombres = t2.toggle("Verde o madura", value=True)
                if mostrar_cajas:
                    dibujo, color = nucleo.dibujar(img, pred, COLORES_CLASE, NOMBRES, mostrar_nombres)
                else:
                    dibujo = img
                st.image(dibujo, width="stretch")
                conteo = nucleo.contar(pred)
                flores = sum(v for k, v in conteo.items() if k in clases_flor)
                verdes = sum(v for k, v in conteo.items() if k in clases_verde)
                maduras = sum(v for k, v in conteo.items() if k in clases_madura)
                sin_asignar = {k: v for k, v in conteo.items() if k not in clases_flor + clases_baya}
                if not conteo:
                    st.warning("No se detectó nada. Prueba bajando la confianza mínima en ⚙️ Ajustes, "
                               "o activa «Alta precisión».")
                if sin_asignar:
                    st.info(f"Clases detectadas que no se suman: {sin_asignar}. "
                            "Escribe esos nombres en ⚙️ Ajustes → Clases del modelo.")
            else:
                st.image(img, width="stretch")

        if automatico and pred is not None:
            total_f = verdes + maduras
            if total_f > 0:
                pct = maduras / total_f
                if pct >= 0.7:
                    est, cls = "Predominan las bayas MADURAS", "madura"
                elif pct <= 0.3:
                    est, cls = "Predominan las bayas VERDES", "verde"
                else:
                    est, cls = "Mezcla de bayas verdes y maduras", "mezcla"
                st.markdown(f'<div class="estado {cls}">{est} · {pct:.0%} maduras</div>', unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("🌸 Flores", flores)
            m2.metric("🟢 Verdes", verdes)
            m3.metric("🫐 Maduras", maduras)

        st.caption("Revisa los valores y corrígelos si hace falta antes de guardar:" if automatico
                   else "Cuenta la foto a ojo y escribe los valores:")
        e1, e2, e3 = st.columns(3)
        flores_f = e1.number_input("🌸 Flores", min_value=0, value=int(flores), step=1, key=f"f_{huella}_{modo}")
        verdes_f = e2.number_input("🟢 Verdes", min_value=0, value=int(verdes), step=1, key=f"v_{huella}_{modo}")
        maduras_f = e3.number_input("🫐 Maduras", min_value=0, value=int(maduras), step=1, key=f"m_{huella}_{modo}")

        if st.button("➕ Guardar muestra", type="primary", width="stretch"):
            n = len(st.session_state.muestras) + 1
            nueva = nucleo.sanear_muestra({
                "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "responsable": st.session_state.responsable,
                "lote": (lote or "").strip() or "Lote 1",
                "variedad": variedad,
                "etapa": etapa,
                "unidad": unidad,
                "etiqueta": etiqueta or f"Muestra {n}",
                "flores": flores_f,
                "verdes": verdes_f,
                "maduras": maduras_f,
                "modo": "auto" if automatico else "manual",
                "nota": nota,
            })
            st.session_state.muestras.append(nueva)
            st.session_state.ultimo_lote = nueva["lote"]
            aviso = f"✅ Muestra {n} guardada en «{nueva['lote']}». Toma la siguiente foto."
            if hoja_configurada() and st.session_state.hoja_auto:
                with st.spinner("Enviando a tu hoja…"):
                    texto_hoja, _ok = enviar_pendientes([nueva])
                aviso += " " + texto_hoja
            st.session_state.flash = aviso
            st.session_state.ver += 1          # limpia la cámara para la próxima foto
            st.rerun()
    else:
        st.markdown('<div class="vacio"><div class="ico">📷</div>Toma o elige una foto para empezar.</div>',
                    unsafe_allow_html=True)

# =====================================================================
# RESUMEN
# =====================================================================
with tab_res:
    if st.session_state.get("flash_res"):
        _f = st.session_state.pop("flash_res")
        (st.warning if "⚠️" in _f else st.success)(_f)
    todas = st.session_state.muestras
    if not todas:
        st.markdown('<div class="vacio"><div class="ico">🫐</div>Aún no hay muestras guardadas.<br>'
                    'Ve a <b>📷 Capturar</b>, toma una foto y pulsa <b>Guardar muestra</b>.</div>',
                    unsafe_allow_html=True)
    else:
        lotes = sorted({m["lote"] for m in todas})
        sel = st.selectbox("Lote a analizar", ["Todos los lotes"] + lotes)
        muestras = todas if sel.startswith("Todos") else [m for m in todas if m["lote"] == sel]
        r = nucleo.resumen(muestras, *params)

        n = r["n_muestras"]
        st.progress(min(n / MUESTRAS_META, 1.0), text=f"{n} de {MUESTRAS_META} muestras recomendadas")

        area = st.number_input("Área del lote (ha)", min_value=0.01, step=0.5, key="area_ha",
                               help="Sirve para convertir kg/ha en toneladas del lote.")
        margen_txt = (f'<div class="margen">± {r["margen"]:,.0f} kg/ha (95 % de confianza)</div>'
                      if r["margen"] is not None else
                      '<div class="margen">Añade más muestras para ver el margen de error</div>')
        ton = r["kg_ha_total"] * area / 1000.0
        cal = r["calidad"].lower()
        st.markdown(
            f"""
<div class="resultado">
<div class="etq">Producción total estimada<span class="badge {cal}">Confianza {cal}</span></div>
<div class="valor">{r['kg_ha_total']:,.0f} kg/ha</div>
{margen_txt}
<div class="det">🫐 Bayas ya formadas: {r['kg_ha_actual']:,.0f} kg/ha &nbsp;·&nbsp; 🌸 Desde flores: {r['kg_ha_desde_flores']:,.0f} kg/ha</div>
<div class="det">✅ Maduras ahora (listas para cosechar): {r['kg_ha_maduras']:,.0f} kg/ha</div>
<div class="ton">≈ {ton:,.2f} toneladas en {area:g} ha</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if r["calidad"] == "Baja":
            st.warning("Confianza baja: toma más muestras (idealmente 20 o más) y repártelas por todo el lote. "
                       "Si las muestras son muy distintas entre sí, la estimación también pierde fiabilidad.")

        k1, k2, k3 = st.columns(3)
        k1.metric("Muestras", n)
        k2.metric("🌸 Flores / u.", f"{r['flores_por_unidad']:.1f}")
        k3.metric("🫐 Bayas / u.", f"{r['bayas_por_unidad']:.1f}")
        if r["pct_madurez"] is not None:
            q1, q2, q3 = st.columns(3)
            q1.metric("🟢 Verdes / u.", f"{r['verdes_por_unidad']:.1f}")
            q2.metric("🫐 Maduras / u.", f"{r['maduras_por_unidad']:.1f}")
            q3.metric("Madurez", f"{r['pct_madurez']:.0%}")

        df = pd.DataFrame(muestras)
        df.insert(0, "N°", range(1, len(df) + 1))
        st.markdown("**Conteo por muestra**")
        if (df["verdes"] + df["maduras"]).sum() > 0:
            st.bar_chart(df.set_index("N°")[["flores", "verdes", "maduras"]], color=["#e879a6", "#2f9e6e", "#4b5cc4"])
        else:
            st.bar_chart(df.set_index("N°")[["flores", "bayas"]], color=["#e879a6", "#4b5cc4"])

        if len(lotes) > 1 and sel.startswith("Todos"):
            st.markdown("**Comparación entre lotes**")
            filas = []
            for lt in lotes:
                rr = nucleo.resumen([m for m in todas if m["lote"] == lt], *params)
                filas.append({"Lote": lt, "Muestras": rr["n_muestras"],
                              "Flores/u": round(rr["flores_por_unidad"], 1),
                              "Bayas/u": round(rr["bayas_por_unidad"], 1),
                              "Madurez": f"{rr['pct_madurez']:.0%}" if rr["pct_madurez"] is not None else "—",
                              "kg/ha": round(rr["kg_ha_total"]), "Confianza": rr["calidad"]})
            st.dataframe(pd.DataFrame(filas), hide_index=True)

        st.markdown("**📤 Resumen para compartir**")
        texto = (
            f"ContaBlue · {sel} · {datetime.now():%d/%m/%Y}\n"
            f"Muestras: {n}\n"
            f"Flores por unidad: {r['flores_por_unidad']:.1f}\n"
            f"Bayas por unidad: {r['bayas_por_unidad']:.1f}"
            + (f" (madurez {r['pct_madurez']:.0%})" if r["pct_madurez"] is not None else "") + "\n"
            f"Producción estimada: {r['kg_ha_total']:,.0f} kg/ha"
            + (f" ± {r['margen']:,.0f}" if r["margen"] is not None else "") + "\n"
            f"≈ {ton:,.2f} t en {area:g} ha · Confianza {r['calidad'].lower()}"
        )
        st.code(texto, language=None)
        st.caption("Toca el icono de copiar y pégalo en WhatsApp o correo.")

        with st.expander("📋 Ver y editar todas las muestras"):
            columnas = ["etiqueta", "lote", "variedad", "etapa", "flores", "verdes", "maduras", "responsable",
                        "nota", "hora", "modo", "unidad", "sync", "id", "bayas"]
            base = pd.DataFrame(todas).reindex(columns=columnas)
            editado = st.data_editor(
                base, key=f"editor_{st.session_state.ed_ver}", num_rows="dynamic",
                disabled=["hora", "modo", "unidad", "sync"],
                column_config={
                    "flores": st.column_config.NumberColumn("🌸 Flores", min_value=0, step=1),
                    "verdes": st.column_config.NumberColumn("🟢 Verdes", min_value=0, step=1),
                    "maduras": st.column_config.NumberColumn("🫐 Maduras", min_value=0, step=1),
                    "sync": st.column_config.TextColumn("Enviada"),
                    "id": None, "bayas": None,
                },
            )
            st.caption("Edita los valores, o elimina filas con el icono de papelera, y pulsa guardar. "
                       "Las filas borradas aquí no se borran de tu hoja de Google.")
            if st.button("💾 Guardar cambios de la tabla", width="stretch"):
                originales = {m["id"]: m for m in todas}
                nuevas = []
                for fila in editado.to_dict("records"):
                    m = nucleo.sanear_muestra(fila)
                    vacia = not m["etiqueta"] and (m["flores"] + m["verdes"] + m["maduras"] + m["bayas"]) == 0
                    if vacia:
                        continue
                    o = originales.get(m["id"])
                    campos = ("lote", "variedad", "etapa", "etiqueta", "flores", "verdes", "maduras", "responsable", "nota")
                    if o is None or any(o.get(c) != m.get(c) for c in campos):
                        m["sync"] = ""        # cambió: hay que volver a enviarla
                    nuevas.append(m)
                st.session_state.muestras = nuevas
                st.session_state.ed_ver += 1
                st.session_state.flash_res = "💾 Cambios guardados."
                st.rerun()

        st.markdown("**☁️ Hoja de cálculo y Excel**")
        if hoja_configurada():
            pend = [m for m in todas if m.get("sync") != "ok"]
            st.caption(f"{len(todas) - len(pend)} muestras enviadas a tu hoja · {len(pend)} pendientes")
            if st.button(f"☁️ Enviar {len(pend)} pendientes a la hoja", disabled=not pend, width="stretch"):
                with st.spinner("Enviando…"):
                    st.session_state.flash_res, _ok = enviar_pendientes()
                st.rerun()
            if st.session_state.hoja_enlace:
                st.link_button("📄 Abrir mi hoja de Google", st.session_state.hoja_enlace, width="stretch")
        else:
            st.caption("Conecta tu hoja de Google en ⚙️ Ajustes → Hoja de cálculo para guardar todo en la nube.")
        st.download_button(
            "📥 Descargar Excel (.xlsx)", nucleo.generar_excel(todas, params, st.session_state.area_ha),
            "contablue.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

        st.markdown("**Guardar o restaurar tus datos**")
        guardado_ok = nucleo.codificar_estado({"m": todas, "a": {k: st.session_state[k] for k in PERSISTENTES}}) is not None
        if guardado_ok:
            st.caption("💾 Tus muestras se **autoguardan en el enlace** de esta página: si el navegador se recarga, "
                       "vuelven solas. Aun así, descarga el CSV como copia de seguridad.")
        else:
            st.warning("Tienes demasiadas muestras para el autoguardado del enlace. Descarga el CSV para no perderlas.")
        csv_bytes = pd.DataFrame(todas).to_csv(index=False).encode("utf-8-sig")
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Descargar CSV", csv_bytes, "contablue_muestras.csv", "text/csv", width="stretch")
        confirmar = d2.checkbox("Confirmo borrar todo")
        if st.button("🗑️ Borrar todas las muestras", disabled=not confirmar, width="stretch"):
            st.session_state.muestras = []
            st.session_state.ed_ver += 1
            st.rerun()

    with st.expander("⬆️ Cargar muestras guardadas (CSV)"):
        st.caption("Carga un CSV descargado antes de ContaBlue para continuar donde lo dejaste.")
        sub = st.file_uploader("Archivo CSV de ContaBlue", type=["csv"], key="csv_in")
        if sub is not None and st.button("Cargar muestras", width="stretch"):
            try:
                dfi = pd.read_csv(sub)
                if not {"lote", "flores"}.issubset(dfi.columns):
                    st.error("El archivo no tiene las columnas necesarias (lote, flores).")
                else:
                    nuevas = [nucleo.sanear_muestra(f) for f in dfi.to_dict("records")]
                    st.session_state.muestras.extend(nuevas)
                    st.session_state.flash_res = f"⬆️ Se cargaron {len(nuevas)} muestras."
                    st.rerun()
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")

# =====================================================================
# GUÍA
# =====================================================================
def mostrar_guia(nombre, pie, foto_real=False):
    """Muestra tu foto (assets/mi_<nombre>.jpg) si existe; si no, la imagen incluida."""
    if imagenes_guia is None:
        return
    img, propia = imagenes_guia.imagen_guia(nombre)
    st.image(img, width="stretch")
    st.caption(pie + ("" if (propia or foto_real) else " · Ilustración de referencia"))


with tab_guia:
    st.markdown("### Guía rápida")
    with st.expander("📷 Cómo tomar la foto", expanded=True):
        mostrar_guia("distancia", "A 40–50 cm de la rama, de frente y con el celular firme.")
        st.markdown("✅ **Misma distancia y mismo ángulo** en todas las fotos  \n"
                    "✅ **Luz pareja**, sin contraluz  \n"
                    "✅ **Una foto = una planta** (o 1 m de hilera)")
        mostrar_guia("angulos", "Picado, frontal y cenital. Elige uno y úsalo siempre.", foto_real=True)
    with st.expander("🟢🫐 Verde o madura"):
        mostrar_guia("madurez", "Verde, pintona y madura: así se cuenta cada una.")
        st.markdown("🟢 **Verde** = aún no está lista  \n"
                    "🟣 **Pintona** (rosada o azul a medias) = cuenta como verde  \n"
                    "🫐 **Madura** = azul oscuro parejo")
    with st.expander("📱 Poner ContaBlue como icono en el celular"):
        st.markdown("**Android (Chrome):** menú ⋮ → **Instalar app**  \n"
                    "**iPhone (Safari):** Compartir ⬆️ → **Añadir a pantalla de inicio**")
        st.caption("Si tarda en abrir, la app estaba dormida: espera unos 30 segundos.")
    with st.expander("📍 Cuántas fotos hacer"):
        st.markdown(f"Al menos **{MUESTRAS_META} por lote** (con menos de 10 el resultado no es fiable), "
                    "repartidas por todo el lote: bordes, centro, zonas altas y bajas.")
    with st.expander("💾 Guardar en Excel o Google Sheets"):
        st.markdown("📊 **Excel:** en **Resumen** pulsa **Descargar Excel**.  \n"
                    "☁️ **Google Sheets:** conéctalo en **Ajustes → Hoja de cálculo**; cada muestra se envía sola.")
        st.caption("Sin internet, la muestra queda pendiente y la envías después desde Resumen.")
    with st.expander("🎯 Calibrar y cómo se calcula (avanzado)"):
        st.markdown(
            "**Calibrar:** cuenta a mano 10–30 plantas, compáralas con lo que detecta la app y usa "
            "**⚙️ Ajustes → Calibrar**.\n\n"
            "**Fórmula:** `kg/ha = (bayas + flores × cuajado) × oclusión × unidades por ha × peso por baya`. "
            "Se promedian las muestras y se da un margen de error del 95 %."
        )
    with st.expander("🔒 Privacidad"):
        st.markdown("Las **fotos no se guardan**. Tus conteos quedan en el enlace de la página y en tu CSV, Excel "
                    "u hoja. La API key va solo en los *Secrets* de Streamlit.")
    st.caption("ContaBlue · los resultados son estimaciones, contrástalos con tu cosecha real.")

# =====================================================================
# Autoguardado en el enlace (se ejecuta al final de cada pasada)
# =====================================================================
try:
    hay_cambios = any(st.session_state[k] != DEFECTOS[k] for k in PERSISTENTES)
    if st.session_state.muestras or hay_cambios:
        cod = nucleo.codificar_estado({"m": st.session_state.muestras,
                                       "a": {k: st.session_state[k] for k in PERSISTENTES}})
        if cod is not None and st.query_params.get("d") != cod:
            st.query_params["d"] = cod
    elif "d" in st.query_params:
        del st.query_params["d"]
except Exception:
    pass
