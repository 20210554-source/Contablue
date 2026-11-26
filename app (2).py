"""ContaBlue: cuenta flores y bayas de arándano con una foto (Roboflow) y estima la producción.

Ejecutar:  streamlit run app.py
"""
import hashlib
import io
from datetime import datetime

import pandas as pd
import streamlit as st

import nucleo

st.set_page_config(
    page_title="ContaBlue · Conteo de arándanos",
    page_icon="🫐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# =====================================================================
# Estilo (paleta arándano)
# =====================================================================
st.markdown(
    """
<style>
:root {
  --noche: #1b1f4b; --arandano: #3f4a9e; --azul: #4b5cc4; --lila: #a9b0e8;
  --bruma: #eef0fb; --flor: #e879a6; --hoja: #2f9e6e;
}
.block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 760px; }
footer { visibility: hidden; }

/* ---------- Cabecera ---------- */
.hero {
  position: relative; overflow: hidden; color: #fff;
  background: linear-gradient(135deg, #1b1f4b 0%, #3f4a9e 60%, #5d6cd6 100%);
  padding: 1.5rem 1.5rem 1.4rem 1.5rem; border-radius: 24px; margin-bottom: 1rem;
  box-shadow: 0 10px 26px rgba(27, 31, 75, 0.30);
}
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
.stTabs [data-baseweb="tab"] {
  background: #ffffff; border: 1px solid #dfe3f5; border-radius: 999px;
  padding: 0.45rem 1rem; height: auto; white-space: nowrap; color: #3f4a9e; font-weight: 600;
}
.stTabs [aria-selected="true"] { background: #4b5cc4; color: #ffffff !important; border-color: #4b5cc4; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* ---------- Títulos de sección ---------- */
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

/* ---------- Leyenda de clases ---------- */
.chipc { display: inline-block; color: #fff; border-radius: 999px; padding: 0.2rem 0.8rem;
  font-size: 0.85rem; font-weight: 600; margin: 0.2rem 0.4rem 0.2rem 0; }

/* ---------- Resultado ---------- */
.resultado { color: #fff; border-radius: 24px; padding: 1.4rem 1.5rem; margin: 0.8rem 0;
  background: linear-gradient(135deg, #1b1f4b 0%, #3f4a9e 100%);
  box-shadow: 0 10px 26px rgba(27, 31, 75, 0.28); }
.resultado .etq { font-size: 0.95rem; opacity: 0.9; }
.resultado .valor { font-size: 2.6rem; font-weight: 800; line-height: 1.1; }
.resultado .margen { font-size: 1rem; opacity: 0.95; margin-top: 0.1rem; }
.resultado .det { font-size: 0.92rem; opacity: 0.9; margin-top: 0.6rem; }
.resultado .ton { margin-top: 0.7rem; padding-top: 0.6rem; border-top: 1px solid rgba(255,255,255,0.25);
  font-size: 1.05rem; font-weight: 700; }
.badge { display: inline-block; border-radius: 999px; padding: 0.15rem 0.8rem; font-size: 0.82rem;
  font-weight: 700; color: #fff; margin-left: 0.5rem; vertical-align: middle; }
.badge.alta { background: #2f9e6e; } .badge.media { background: #e0a100; } .badge.baja { background: #d9534f; }

.estado { border-radius: 14px; padding: 0.6rem 1rem; font-weight: 700; margin: 0.5rem 0 0.7rem 0; color: #fff; }
.estado.madura { background: #4b5cc4; } .estado.verde { background: #2f9e6e; } .estado.mezcla { background: #7a6ad8; }

.vacio { text-align: center; padding: 2rem 1rem; color: #5b6190; background: #fff;
  border: 1px dashed #b9c0ee; border-radius: 20px; }
.vacio .ico { font-size: 2.4rem; }
</style>
""",
    unsafe_allow_html=True,
)


def paso(numero, texto):
    st.markdown(f'<div class="paso"><span class="num">{numero}</span>{texto}</div>', unsafe_allow_html=True)


# =====================================================================
# Estado y valores por defecto
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
}
for k, v in DEFECTOS.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("muestras", [])
st.session_state.setdefault("calib", [])

VARIEDADES = ["Biloxi", "Ventura", "Emerald", "Snowchaser", "Sekoya Pop", "Legacy", "Duke", "Misty", "Otra"]
ETAPAS = ["Floración", "Cuajado", "Fruto verde", "Maduración", "Cosecha"]
UNIDADES = ["Planta", "Metro de hilera", "Rama"]
MUESTRAS_META = 20


def csv_lista(texto):
    return [c.strip() for c in texto.split(",") if c.strip()]


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


# =====================================================================
# Cabecera
# =====================================================================
n_total = len(st.session_state.muestras)
st.markdown(
    f"""
<div class="hero">
<div class="bola b1"></div><div class="bola b2"></div><div class="bola b3"></div>
<div class="titulo">ContaBlue</div>
<div class="sub">Cuenta flores y bayas de arándano con una foto y estima tu cosecha.</div>
<div class="chips"><span class="chip">📷 {n_total} muestras</span><span class="chip">🫐 Roboflow</span><span class="chip">📈 kg/ha</span></div>
</div>
""",
    unsafe_allow_html=True,
)

tab_cap, tab_res, tab_aj, tab_guia = st.tabs(["📷 Capturar", "📊 Resumen", "⚙️ Ajustes", "📖 Guía"])

# =====================================================================
# AJUSTES (se define primero porque Capturar y Resumen leen estos valores)
# =====================================================================
with tab_aj:
    with st.expander("🔌 Conexión con Roboflow", expanded=not st.session_state.api_key):
        st.text_input("API key", type="password", key="api_key")
        st.text_input("Model ID (proyecto/versión)", placeholder="mi-proyecto/1", key="model_id")
        st.slider("Confianza mínima", 0.05, 0.95, step=0.05, key="confianza",
                  help="Sube este valor si detecta cosas que no son frutos; bájalo si se le pasan frutos.")
        st.slider("Solape máximo (NMS)", 0.1, 0.9, step=0.05, key="solape",
                  help="Controla que no se cuente dos veces el mismo fruto.")

    with st.expander("🏷️ Clases del modelo"):
        st.caption("Escribe los nombres tal como están en tu proyecto de Roboflow, separados por coma.")
        st.text_input("Clases de flores", key="clases_flor")
        st.text_input("Clases de bayas VERDES", key="clases_verde")
        st.text_input("Clases de bayas MADURAS", key="clases_madura")

    with st.expander("🌱 Parámetros de producción", expanded=True):
        st.number_input("Unidades de muestreo por hectárea", min_value=1.0, step=500.0, key="unidades_ha",
                        help="Si cada foto es una planta: plantas por hectárea. Si es 1 m de hilera: metros de hilera por hectárea.")
        st.number_input("Factor de corrección por oclusión", min_value=0.5, max_value=3.0, step=0.05, key="factor_oclusion",
                        help="Frutos reales ÷ frutos detectados. Cálculalo abajo con la calibración.")
        st.slider("Cuajado: flores que llegan a fruto", 0.0, 1.0, step=0.05, key="tasa_cuajado")
        st.number_input("Peso medio por baya (g)", min_value=0.1, step=0.1, key="peso_baya")

    with st.expander("🎯 Calibrar el factor de oclusión"):
        st.caption("Cuenta a mano una planta o tramo y compara con lo que detecta la app. "
                   "Añade entre 10 y 30 pares y calcula el factor.")
        cc1, cc2 = st.columns(2)
        cc1.number_input("Conteo real (a mano)", min_value=0, step=1, key="cal_real")
        cc2.number_input("Conteo de la app", min_value=0, step=1, key="cal_det")
        st.button("➕ Añadir par", on_click=agregar_par_calibracion, use_container_width=True)
        if st.session_state.calib:
            st.dataframe(pd.DataFrame(st.session_state.calib, columns=["Real", "App"]),
                         use_container_width=True, hide_index=True)
            f = nucleo.factor_calibracion(st.session_state.calib)
            if f:
                st.metric("Factor calculado", f"{f:.2f}")
                b1, b2 = st.columns(2)
                b1.button("✅ Usar este factor", on_click=aplicar_factor, use_container_width=True)
                b2.button("🗑️ Borrar pares", on_click=limpiar_calibracion, use_container_width=True)

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

# =====================================================================
# CAPTURAR
# =====================================================================
with tab_cap:
    with st.container(border=True):
        st.markdown("**📍 Datos de la muestra**")
        c1, c2 = st.columns(2)
        lote = c1.text_input("Lote / parcela", value="Lote 1")
        variedad = c2.selectbox("Variedad", VARIEDADES)
        c3, c4 = st.columns(2)
        etapa = c3.selectbox("Etapa del cultivo", ETAPAS)
        unidad = c4.selectbox("Unidad de muestreo", UNIDADES)
        c5, c6 = st.columns(2)
        etiqueta = c5.text_input("Etiqueta (opcional)", placeholder="Hilera 4 - planta 12")
        nota = c6.text_input("Nota (opcional)", placeholder="Sombra, poda reciente…")

    modo = st.radio("Modo de conteo", ["🤖 Automático (Roboflow)", "✍️ Manual (sin modelo)"], horizontal=True)
    automatico = modo.startswith("🤖")

    if automatico and not (api_key and model_id):
        st.info("Para el modo automático completa la **API key** y el **Model ID** en la pestaña "
                "**⚙️ Ajustes**. Mientras tanto puedes usar el modo manual.")

    paso(1, "Toma la foto")
    st.markdown(f'<div class="subt">Usa siempre la misma distancia y encuadre: cada foto es una '
                f'unidad de muestreo ({unidad.lower()}).</div>', unsafe_allow_html=True)
    origen = st.radio("Origen de la foto", ["📷 Cámara", "🖼️ Galería"], horizontal=True, label_visibility="collapsed")
    if origen.endswith("Cámara"):
        archivo = st.camera_input("Fotografía la planta o el tramo de hilera")
    else:
        archivo = st.file_uploader("Elige una foto", type=["jpg", "jpeg", "png"])

    flores = verdes = maduras = 0
    hay_foto = archivo is not None
    huella = None
    if hay_foto:
        datos = archivo.getvalue()
        huella = hashlib.md5(datos).hexdigest()

        if st.session_state.get("huella_foto") != huella:
            st.session_state.huella_foto = huella
            st.session_state.pred = None
            st.session_state.error = None
            try:
                st.session_state.img = nucleo.preparar_imagen(io.BytesIO(datos))
            except Exception as e:
                st.session_state.img = None
                st.session_state.error = f"No se pudo abrir la imagen: {e}"

            if automatico and api_key and model_id and st.session_state.img is not None:
                with st.spinner("Detectando flores y bayas…"):
                    try:
                        st.session_state.pred = nucleo.detectar(
                            st.session_state.img, api_key, model_id,
                            st.session_state.confianza, st.session_state.solape)
                    except Exception as e:
                        st.session_state.error = f"Error al consultar Roboflow: {e}"

    # Si cambias a modo automático después de tomar la foto, detecta ahora
    if (hay_foto and automatico and api_key and model_id and st.session_state.get("pred") is None
            and st.session_state.get("img") is not None and not st.session_state.get("error")):
        with st.spinner("Detectando flores y bayas…"):
            try:
                st.session_state.pred = nucleo.detectar(
                    st.session_state.img, api_key, model_id,
                    st.session_state.confianza, st.session_state.solape)
            except Exception as e:
                st.session_state.error = f"Error al consultar Roboflow: {e}"

    if hay_foto:
        paso(2, "Resultado")
        if st.session_state.get("error"):
            st.error(st.session_state.error)

        pred = st.session_state.get("pred")
        img = st.session_state.get("img")
        if img is not None:
            if automatico and pred is not None:
                t1, t2 = st.columns(2)
                mostrar_cajas = t1.toggle("Mostrar cajas", value=True)
                mostrar_nombres = t2.toggle("Mostrar si es verde o madura", value=True)
                if mostrar_cajas:
                    dibujo, color = nucleo.dibujar(img, pred, COLORES_CLASE, NOMBRES, mostrar_nombres)
                else:
                    dibujo, color = img, nucleo.dibujar(img, pred, COLORES_CLASE)[1]
                st.image(dibujo, use_container_width=True)
                conteo = nucleo.contar(pred)
                flores = sum(v for k, v in conteo.items() if k in clases_flor)
                verdes = sum(v for k, v in conteo.items() if k in clases_verde)
                maduras = sum(v for k, v in conteo.items() if k in clases_madura)
                sin_asignar = {k: v for k, v in conteo.items() if k not in clases_flor + clases_baya}
                if not conteo:
                    st.warning("No se detectó nada. Prueba bajando la confianza mínima en ⚙️ Ajustes.")
                if sin_asignar:
                    st.info(f"Clases detectadas que no se suman: {sin_asignar}. "
                            "Escribe esos nombres en ⚙️ Ajustes → Clases del modelo.")
            else:
                st.image(img, use_container_width=True)

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

        if st.button("➕ Guardar muestra", type="primary", use_container_width=True):
            n = len(st.session_state.muestras) + 1
            st.session_state.muestras.append({
                "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "lote": lote.strip() or "Lote 1",
                "variedad": variedad,
                "etapa": etapa,
                "unidad": unidad,
                "etiqueta": etiqueta or f"Muestra {n}",
                "flores": int(flores_f),
                "verdes": int(verdes_f),
                "maduras": int(maduras_f),
                "bayas": int(verdes_f) + int(maduras_f),
                "modo": "auto" if automatico else "manual",
                "nota": nota,
            })
            st.toast(f"Muestra {n} guardada. Toma la siguiente foto.", icon="✅")
            st.success(f"Muestra {n} guardada ({lote}). Toma la siguiente foto.")
    else:
        st.markdown('<div class="vacio"><div class="ico">📷</div>Toma o elige una foto para empezar.</div>',
                    unsafe_allow_html=True)

# =====================================================================
# RESUMEN
# =====================================================================
with tab_res:
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
<div class="etq">Producción total estimada<span class="badge {cal}">Confianza {r['calidad'].lower()}</span></div>
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
        k2.metric("🌸 Flores / unidad", f"{r['flores_por_unidad']:.1f}")
        k3.metric("🫐 Bayas / unidad", f"{r['bayas_por_unidad']:.1f}")
        if r["pct_madurez"] is not None:
            q1, q2, q3 = st.columns(3)
            q1.metric("🟢 Verdes / unidad", f"{r['verdes_por_unidad']:.1f}")
            q2.metric("🫐 Maduras / unidad", f"{r['maduras_por_unidad']:.1f}")
            q3.metric("Madurez", f"{r['pct_madurez']:.0%}")

        df = pd.DataFrame(muestras)
        df.insert(0, "N°", range(1, len(df) + 1))

        st.markdown("**Conteo por muestra**")
        if {"verdes", "maduras"}.issubset(df.columns) and (df["verdes"].astype(float) + df["maduras"].astype(float)).sum() > 0:
            st.bar_chart(df.set_index("N°")[["flores", "verdes", "maduras"]], color=["#e879a6", "#2f9e6e", "#4b5cc4"])
        else:
            st.bar_chart(df.set_index("N°")[["flores", "bayas"]], color=["#e879a6", "#4b5cc4"])

        if len(lotes) > 1 and sel.startswith("Todos"):
            st.markdown("**Comparación entre lotes**")
            filas = []
            for lt in lotes:
                ms = [m for m in todas if m["lote"] == lt]
                rr = nucleo.resumen(ms, *params)
                filas.append({"Lote": lt, "Muestras": rr["n_muestras"],
                              "Flores/u": round(rr["flores_por_unidad"], 1),
                              "Bayas/u": round(rr["bayas_por_unidad"], 1),
                              "kg/ha": round(rr["kg_ha_total"]), "Confianza": rr["calidad"]})
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        with st.expander("📋 Ver y editar muestras"):
            st.dataframe(df, use_container_width=True, hide_index=True)
            idx = st.selectbox("Eliminar la muestra N°", df["N°"].tolist())
            if st.button("🗑️ Eliminar esa muestra"):
                objetivo = muestras[idx - 1]
                st.session_state.muestras.remove(objetivo)
                st.rerun()

        st.markdown("**Guardar o restaurar tus datos**")
        csv_bytes = pd.DataFrame(todas).to_csv(index=False).encode("utf-8-sig")
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Descargar CSV", csv_bytes, "contablue_muestras.csv", "text/csv",
                           use_container_width=True)
        if d2.button("🗑️ Borrar todo", use_container_width=True):
            st.session_state.muestras = []
            st.rerun()

    with st.expander("⬆️ Cargar muestras guardadas (CSV)"):
        st.caption("Los datos se pierden al cerrar la app. Descarga el CSV al terminar y cárgalo aquí otro día.")
        sub = st.file_uploader("Archivo CSV de ContaBlue", type=["csv"], key="csv_in")
        if sub is not None and st.button("Cargar muestras", use_container_width=True):
            try:
                dfi = pd.read_csv(sub)
                req = {"lote", "flores", "bayas"}
                if not req.issubset(dfi.columns):
                    st.error("El archivo no tiene las columnas necesarias (lote, flores, bayas).")
                else:
                    dfi = dfi.fillna("")
                    for fila in dfi.to_dict("records"):
                        fila["flores"], fila["bayas"] = int(fila["flores"]), int(fila["bayas"])
                        fila["lote"] = str(fila["lote"])
                        for campo in ("verdes", "maduras"):
                            try:
                                fila[campo] = int(fila.get(campo, 0) or 0)
                            except (TypeError, ValueError):
                                fila[campo] = 0
                        st.session_state.muestras.append(fila)
                    st.success(f"Se cargaron {len(dfi)} muestras.")
                    st.rerun()
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")

# =====================================================================
# GUÍA
# =====================================================================
with tab_guia:
    st.markdown("### Cómo sacar buenos números")
    with st.expander("📷 Cómo tomar las fotos", expanded=True):
        st.markdown(
            "- Usa **siempre la misma distancia y el mismo encuadre**.\n"
            "- Toma la foto con buena luz, evita contraluz y sombras muy duras.\n"
            "- Cada foto es **una unidad de muestreo**: una planta, una rama o 1 metro de hilera.\n"
            "- Mantén el celular quieto para que no salga borrosa."
        )
    with st.expander("🟢🫐 Verde o madura"):
        st.markdown(
            "El modelo de Roboflow debe tener **clases distintas** para cada estado (por ejemplo "
            "`baya_verde` y `baya_madura`) y debes haber anotado así tus fotos. La app dibuja cada "
            "fruto con su color (verde = verde, azul = madura, rosa = flor) y cuenta cada grupo por separado. "
            "Si tus clases tienen otros nombres, escríbelos en **⚙️ Ajustes → Clases del modelo**."
        )
    with st.expander("📍 Cuántas muestras y dónde"):
        st.markdown(
            f"- Apunta a **{MUESTRAS_META} muestras o más por lote**; con menos de 10 el resultado es poco fiable.\n"
            "- Reparte los puntos por todo el lote (bordes, centro, zonas altas y bajas). "
            "No fotografíes solo las plantas más bonitas.\n"
            "- Si el lote es muy desigual, trátalo como dos lotes distintos."
        )
    with st.expander("🎯 Cómo calibrar"):
        st.markdown(
            "1. Elige 10–30 plantas o tramos.\n"
            "2. Cuenta a mano las bayas (o flores) reales y anota el número.\n"
            "3. Fotografíalas con la app y anota lo que detecta.\n"
            "4. En **⚙️ Ajustes → Calibrar** añade los pares y pulsa *Usar este factor*.\n\n"
            "Mide también el **peso medio de la baya** (pesa 100 bayas y divide entre 100) y la "
            "**tasa de cuajado** de tu variedad."
        )
    with st.expander("🧮 Cómo se calcula la producción"):
        st.markdown(
            "Para cada muestra:\n\n"
            "`kg/ha = (bayas + flores × cuajado) × factor de oclusión × unidades por ha × peso por baya`\n\n"
            "La app promedia todas las muestras del lote y calcula un **margen de error al 95 %**: "
            "cuanto más parecidas sean las muestras y más muestras tengas, más pequeño es."
        )
    with st.expander("💾 Tus datos"):
        st.markdown(
            "La app **no guarda datos en un servidor**: si cierras o recargas la página, las muestras se "
            "pierden. Antes de terminar, descarga el CSV en la pestaña **📊 Resumen**; puedes cargarlo "
            "de nuevo otro día."
        )
    st.caption("ContaBlue · los resultados son estimaciones, contrástalos con tu cosecha real.")
