"""Lógica de la app: llamada a Roboflow, dibujo de cajas y estimación de producción."""
from collections import Counter

from PIL import Image, ImageDraw, ImageFont, ImageOps

COLORES = ["#e63946", "#2a9d8f", "#f4a261", "#457b9d", "#9b5de5", "#fb8500", "#06d6a0"]


def preparar_imagen(archivo, max_lado=1280):
    """Abre la foto, corrige la orientación del celular y la reduce para subirla más rápido."""
    img = Image.open(archivo)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_lado, max_lado))
    return img


def detectar(img, api_key, model_id, confianza=0.4, solape=0.5, api_url="https://serverless.roboflow.com"):
    """Envía la imagen a la API en la nube de Roboflow y devuelve la lista de predicciones."""
    from inference_sdk import InferenceConfiguration, InferenceHTTPClient

    try:
        cfg = InferenceConfiguration(confidence_threshold=confianza, iou_threshold=solape,
                                     api_key_transport="header")
    except TypeError:  # versiones antiguas del SDK
        cfg = InferenceConfiguration(confidence_threshold=confianza, iou_threshold=solape)
    cliente = InferenceHTTPClient(api_url=api_url, api_key=api_key).configure(cfg)
    res = cliente.infer(img, model_id=model_id.strip())
    if isinstance(res, list):
        res = res[0] if res else {}
    preds = res.get("predictions", [])
    return [p for p in preds if p.get("confidence", 1.0) >= confianza]


def _fuente(tam):
    try:
        return ImageFont.load_default(size=tam)
    except TypeError:  # Pillow antiguo
        return ImageFont.load_default()


def dibujar(img, predicciones, colores=None, nombres=None, etiquetas=False):
    """
    Dibuja las cajas detectadas.
    colores: {clase: "#rrggbb"}; nombres: {clase: texto corto a mostrar}; etiquetas: escribir el nombre sobre cada caja.
    Devuelve (imagen, {clase: color}).
    """
    out = img.copy()
    d = ImageDraw.Draw(out)
    clases = sorted({p["class"] for p in predicciones})
    color = {c: (colores or {}).get(c) or COLORES[i % len(COLORES)] for i, c in enumerate(clases)}
    grosor = max(2, out.width // 350)
    fuente = _fuente(max(11, out.width // 55)) if etiquetas else None
    for p in predicciones:
        x0, y0 = p["x"] - p["width"] / 2, p["y"] - p["height"] / 2
        x1, y1 = p["x"] + p["width"] / 2, p["y"] + p["height"] / 2
        c = color[p["class"]]
        d.rectangle([x0, y0, x1, y1], outline=c, width=grosor)
        if etiquetas:
            texto = (nombres or {}).get(p["class"], p["class"])
            caja = d.textbbox((0, 0), texto, font=fuente)
            w, h = caja[2] - caja[0] + 6, caja[3] - caja[1] + 4
            ty = y0 - h if y0 - h >= 0 else y0
            d.rectangle([x0, ty, x0 + w, ty + h], fill=c)
            d.text((x0 + 3, ty + 1), texto, fill="#ffffff", font=fuente)
    return out, color


def contar(predicciones):
    return Counter(p["class"] for p in predicciones)


# Valores críticos t de Student (95 %, dos colas) para 1..30 grados de libertad
_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
         2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
         2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def _t_crit(gl):
    return _T975[gl - 1] if 1 <= gl <= 30 else 1.96


def kg_muestra(m, unidades_ha, factor_oclusion, tasa_cuajado, peso_baya_g):
    """kg/ha que proyecta UNA muestra: bayas ya formadas y flores que llegarán a fruto."""
    k = unidades_ha * peso_baya_g / 1000.0
    actual = m["bayas"] * factor_oclusion * k
    futuro = m["flores"] * factor_oclusion * tasa_cuajado * k
    return actual, futuro


def calidad(n, cv):
    """Semáforo simple de confianza según nº de muestras y variabilidad entre ellas."""
    if n < 10 or cv > 0.40:
        return "Baja"
    if n >= 20 and cv <= 0.25:
        return "Alta"
    return "Media"


def resumen(muestras, unidades_ha, factor_oclusion, tasa_cuajado, peso_baya_g):
    """Promedio por unidad y producción estimada (kg/ha) con margen de error al 95 %."""
    n = len(muestras)
    if n == 0:
        return None
    partes = [kg_muestra(m, unidades_ha, factor_oclusion, tasa_cuajado, peso_baya_g) for m in muestras]
    totales = [a + f for a, f in partes]
    maduras = sum(m.get("maduras", 0) for m in muestras) / n
    verdes = sum(m.get("verdes", 0) for m in muestras) / n
    media = sum(totales) / n
    sd = (sum((t - media) ** 2 for t in totales) / (n - 1)) ** 0.5 if n > 1 else 0.0
    margen = _t_crit(n - 1) * sd / n ** 0.5 if n > 1 else None
    cv = sd / media if media > 0 else 0.0
    return {
        "n_muestras": n,
        "flores_por_unidad": sum(m["flores"] for m in muestras) / n,
        "bayas_por_unidad": sum(m["bayas"] for m in muestras) / n,
        "maduras_por_unidad": maduras,
        "verdes_por_unidad": verdes,
        "pct_madurez": maduras / (maduras + verdes) if (maduras + verdes) > 0 else None,
        "kg_ha_maduras": maduras * factor_oclusion * unidades_ha * peso_baya_g / 1000.0,
        "kg_ha_actual": sum(a for a, _ in partes) / n,
        "kg_ha_desde_flores": sum(f for _, f in partes) / n,
        "kg_ha_total": media,
        "margen": margen,
        "cv": cv,
        "calidad": calidad(n, cv),
    }


def factor_calibracion(pares):
    """pares: lista de (conteo_real_a_mano, conteo_detectado). Devuelve real/detectado."""
    real = sum(r for r, _ in pares)
    det = sum(d for _, d in pares)
    return real / det if det > 0 else None
