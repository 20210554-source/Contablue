"""Lógica de la app: llamada a Roboflow, dibujo de cajas y estimación de producción."""
import base64
import io
from collections import Counter

import requests
from PIL import Image, ImageDraw, ImageOps

COLORES = ["#e63946", "#2a9d8f", "#f4a261", "#457b9d", "#9b5de5", "#fb8500", "#06d6a0"]


def preparar_imagen(archivo, max_lado=1280):
    """Abre la foto, corrige la orientación del celular y la reduce para subirla más rápido."""
    img = Image.open(archivo)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_lado, max_lado))
    return img


def detectar(img, api_key, model_id, confianza=0.4, solape=0.5, api_url="https://detect.roboflow.com"):
    """Envía la imagen a la API alojada de Roboflow y devuelve la lista de predicciones."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    cuerpo = base64.b64encode(buf.getvalue()).decode("ascii")
    url = f"{api_url.rstrip('/')}/{model_id.strip('/')}"
    r = requests.post(
        url,
        params={"api_key": api_key, "confidence": int(confianza * 100), "overlap": int(solape * 100)},
        data=cuerpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("predictions", [])


def dibujar(img, predicciones):
    """Dibuja las cajas detectadas, con un color por clase."""
    out = img.copy()
    d = ImageDraw.Draw(out)
    clases = sorted({p["class"] for p in predicciones})
    color = {c: COLORES[i % len(COLORES)] for i, c in enumerate(clases)}
    for p in predicciones:
        x0, y0 = p["x"] - p["width"] / 2, p["y"] - p["height"] / 2
        x1, y1 = p["x"] + p["width"] / 2, p["y"] + p["height"] / 2
        d.rectangle([x0, y0, x1, y1], outline=color[p["class"]], width=3)
    return out, color


def contar(predicciones):
    return Counter(p["class"] for p in predicciones)


def estimar(muestras, unidades_ha, factor_oclusion, tasa_cuajado, peso_baya_g):
    """
    muestras: lista de dicts {"flores": int, "bayas": int}, una por unidad de muestreo
              (una planta o un tramo de hilera fotografiado con el mismo protocolo).
    Devuelve el promedio por unidad y la producción estimada por hectárea.
    """
    n = len(muestras)
    if n == 0:
        return None
    flores_u = sum(m["flores"] for m in muestras) / n
    bayas_u = sum(m["bayas"] for m in muestras) / n

    bayas_ha = bayas_u * factor_oclusion * unidades_ha          # frutos ya formados
    flores_ha = flores_u * factor_oclusion * unidades_ha        # flores abiertas
    bayas_futuras_ha = flores_ha * tasa_cuajado                 # flores que llegarán a fruto

    kg = lambda frutos: frutos * peso_baya_g / 1000.0
    return {
        "n_muestras": n,
        "flores_por_unidad": flores_u,
        "bayas_por_unidad": bayas_u,
        "kg_ha_actual": kg(bayas_ha),
        "kg_ha_desde_flores": kg(bayas_futuras_ha),
        "kg_ha_total": kg(bayas_ha + bayas_futuras_ha),
    }
