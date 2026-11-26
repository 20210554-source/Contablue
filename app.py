"""App móvil (web) para contar bayas y flores con Roboflow y estimar la producción.

Ejecutar:  streamlit run app.py
"""
import csv
import io
from datetime import datetime

import streamlit as st

import nucleo

st.set_page_config(page_title="Conteo de bayas y flores", page_icon="🫐", layout="centered")
st.title("🫐 Conteo de bayas y flores")

# ---------- Configuración ----------
def secreto(nombre, defecto=""):
    try:
        return st.secrets.get(nombre, defecto)
    except Exception:
        return defecto


with st.sidebar:
    st.header("Roboflow")
    api_key = st.text_input("API key", value=secreto("ROBOFLOW_API_KEY"), type="password")
    model_id = st.text_input("Model ID (proyecto/versión)", value=secreto("ROBOFLOW_MODEL_ID"),
                             placeholder="mi-proyecto/1")
    confianza = st.slider("Confianza mínima", 0.05, 0.95, 0.40, 0.05)
    solape = st.slider("Solape máximo (NMS)", 0.1, 0.9, 0.50, 0.05)

    st.header("Clases del modelo")
    st.caption("Escribe los nombres tal como están en tu proyecto de Roboflow, separados por coma.")
    clases_flor = [c.strip() for c in st.text_input("Flores", "flor").split(",") if c.strip()]
    clases_baya = [c.strip() for c in st.text_input("Bayas", "baya_verde, baya_madura").split(",") if c.strip()]

    st.header("Parámetros de producción")
    unidades_ha = st.number_input("Unidades de muestreo por hectárea", min_value=1.0, value=10000.0, step=500.0,
                                  help="Si cada foto es una planta: plantas/ha. Si es 1 m de hilera: metros de hilera/ha.")
    factor_oclusion = st.number_input("Factor de corrección por oclusión", min_value=1.0, value=1.3, step=0.05,
                                      help="Frutos reales ÷ frutos detectados. Calíbralo contando a mano 30–50 plantas.")
    tasa_cuajado = st.slider("Cuajado: flores que llegan a fruto", 0.0, 1.0, 0.60, 0.05)
    peso_baya = st.number_input("Peso medio por baya (g)", min_value=0.1, value=2.0, step=0.1)

if "muestras" not in st.session_state:
    st.session_state.muestras = []

# ---------- Captura ----------
st.subheader("1. Toma la foto")
st.caption("Usa siempre la misma distancia y encuadre: cada foto es una unidad de muestreo.")
modo = st.radio("Origen", ["Cámara", "Galería"], horizontal=True, label_visibility="collapsed")
if modo == "Cámara":
    archivo = st.camera_input("Fotografía la planta o el tramo de hilera")
else:
    archivo = st.file_uploader("Elige una foto", type=["jpg", "jpeg", "png"])
etiqueta = st.text_input("Etiqueta de la muestra (opcional)", placeholder="Lote A - planta 12")

if archivo is not None:
    if not api_key or not model_id:
        st.warning("Completa la API key y el Model ID en el panel lateral (☰ arriba a la izquierda).")
    else:
        # Procesa cada foto una sola vez
        huella = (archivo.name, archivo.size)
        if st.session_state.get("ultima_huella") != huella:
            with st.spinner("Detectando…"):
                try:
                    img = nucleo.preparar_imagen(archivo)
                    st.session_state.img = img
                    st.session_state.pred = nucleo.detectar(img, api_key, model_id, confianza, solape)
                    st.session_state.ultima_huella = huella
                except Exception as e:
                    st.error(f"Error al consultar Roboflow: {e}")
                    st.session_state.pop("ultima_huella", None)

        if st.session_state.get("ultima_huella") == huella:
            st.subheader("2. Resultado")
            pred = st.session_state.pred
            dibujo, color = nucleo.dibujar(st.session_state.img, pred)
            st.image(dibujo, use_container_width=True)

            conteo = nucleo.contar(pred)
            flores = sum(v for k, v in conteo.items() if k in clases_flor)
            bayas = sum(v for k, v in conteo.items() if k in clases_baya)

            c1, c2 = st.columns(2)
            c1.metric("🌸 Flores", flores)
            c2.metric("🫐 Bayas", bayas)
            sin_asignar = {k: v for k, v in conteo.items() if k not in clases_flor + clases_baya}
            if sin_asignar:
                st.info(f"Clases detectadas sin asignar (no se suman): {sin_asignar}. "
                        "Ajusta los nombres en el panel lateral.")

            st.caption("Si el modelo se equivocó, corrige los valores antes de guardar:")
            e1, e2 = st.columns(2)
            flores_f = e1.number_input("Flores (ajuste manual)", min_value=0, value=int(flores), key=f"f{huella}")
            bayas_f = e2.number_input("Bayas (ajuste manual)", min_value=0, value=int(bayas), key=f"b{huella}")

            if st.button("➕ Guardar muestra", type="primary", use_container_width=True):
                st.session_state.muestras.append({
                    "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "etiqueta": etiqueta or f"Muestra {len(st.session_state.muestras) + 1}",
                    "flores": int(flores_f),
                    "bayas": int(bayas_f),
                })
                st.success("Muestra guardada. Toma la siguiente foto.")

# ---------- Estimación ----------
st.subheader("3. Estimación de producción")
muestras = st.session_state.muestras
if not muestras:
    st.write("Aún no hay muestras guardadas.")
else:
    st.dataframe(muestras, use_container_width=True, hide_index=True)
    r = nucleo.estimar(muestras, unidades_ha, factor_oclusion, tasa_cuajado, peso_baya)

    m1, m2, m3 = st.columns(3)
    m1.metric("Muestras", r["n_muestras"])
    m2.metric("Flores / unidad", f"{r['flores_por_unidad']:.1f}")
    m3.metric("Bayas / unidad", f"{r['bayas_por_unidad']:.1f}")

    st.metric("Producción total estimada", f"{r['kg_ha_total']:,.0f} kg/ha")
    st.caption(f"Bayas ya formadas: {r['kg_ha_actual']:,.0f} kg/ha · "
               f"Proyección desde flores: {r['kg_ha_desde_flores']:,.0f} kg/ha")
    if r["n_muestras"] < 10:
        st.warning("Con menos de ~10 muestras bien repartidas por el lote la estimación es muy poco fiable.")

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(muestras[0].keys()))
    w.writeheader()
    w.writerows(muestras)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Descargar CSV", buf.getvalue(), "muestras.csv", "text/csv", use_container_width=True)
    if d2.button("🗑️ Borrar muestras", use_container_width=True):
        st.session_state.muestras = []
        st.rerun()
