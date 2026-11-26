"""Lógica de la app: llamada a Roboflow, dibujo de cajas y estimación de producción."""
from collections import Counter

from PIL import Image, ImageDraw, ImageFont, ImageOps

COLORES = ["#e63946", "#2a9d8f", "#f4a261", "#457b9d", "#9b5de5", "#fb8500", "#06d6a0"]


try:  # fotos HEIC/HEIF del iPhone (si la librería está instalada)
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass


def preparar_imagen(archivo, max_lado=1280):
    """Abre la foto, corrige la orientación del celular y la reduce para subirla más rápido."""
    Image.MAX_IMAGE_PIXELS = None  # fotos de cámaras de muchos megapíxeles
    img = Image.open(archivo)
    img.draft("RGB", (max_lado * 2, max_lado * 2))  # JPEG grandes: lectura reducida, más rápida y liviana
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGB")
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


# =====================================================================
# Mosaicos (para bayas muy pequeñas) y NMS
# =====================================================================
def _iou(a, b):
    ax0, ay0, ax1, ay1 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2, a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
    bx0, by0, bx1, by1 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2, b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    iw, ih = min(ax1, bx1) - max(ax0, bx0), min(ay1, by1) - max(ay0, by0)
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    return inter / union if union > 0 else 0.0


def nms(preds, iou_max=0.5):
    """Quita detecciones duplicadas de la misma clase (se queda con la de mayor confianza)."""
    out = []
    for p in sorted(preds, key=lambda q: q.get("confidence", 0), reverse=True):
        if all(p["class"] != q["class"] or _iou(p, q) <= iou_max for q in out):
            out.append(p)
    return out


def detectar_mosaicos(img, detector, n=2, traslape=0.12, iou_max=0.5):
    """
    Divide la imagen en n×n mosaicos con un pequeño traslape, detecta en cada uno
    con `detector(imagen)->predicciones` y junta los resultados en coordenadas globales.
    """
    W, H = img.size
    tw, th = W / n, H / n
    ox, oy = tw * traslape, th * traslape
    todas = []
    for i in range(n):
        for j in range(n):
            x0, y0 = max(0, int(j * tw - ox)), max(0, int(i * th - oy))
            x1, y1 = min(W, int((j + 1) * tw + ox)), min(H, int((i + 1) * th + oy))
            for p in detector(img.crop((x0, y0, x1, y1))):
                q = dict(p)
                q["x"], q["y"] = p["x"] + x0, p["y"] + y0
                todas.append(q)
    return nms(todas, iou_max)


# =====================================================================
# Autoguardado en el enlace y limpieza de datos
# =====================================================================
import base64
import json
import math
import uuid
import zlib

CAMPOS_TEXTO = ("id", "hora", "responsable", "lote", "variedad", "etapa", "unidad", "etiqueta", "modo", "nota", "sync")
MAX_CODIGO = 9000  # largo máximo razonable para un enlace


def _int(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return 0
        return max(0, int(float(x)))
    except (TypeError, ValueError):
        return 0


def _txt(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x)


def sanear_muestra(d):
    """Devuelve una muestra limpia y con todos los campos, venga de donde venga."""
    m = {k: _txt(d.get(k)) for k in CAMPOS_TEXTO}
    m["lote"] = m["lote"] or "Lote 1"
    m["id"] = m["id"] or uuid.uuid4().hex[:10]
    m["sync"] = "ok" if m["sync"] == "ok" else ""
    m["flores"] = _int(d.get("flores"))
    m["verdes"] = _int(d.get("verdes"))
    m["maduras"] = _int(d.get("maduras"))
    m["bayas"] = m["verdes"] + m["maduras"] if (m["verdes"] + m["maduras"]) > 0 else _int(d.get("bayas"))
    return m


def codificar_estado(estado):
    """Convierte un dict en un texto corto y seguro para ir en la URL. None si es demasiado largo."""
    raw = json.dumps(estado, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    txt = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return txt if len(txt) <= MAX_CODIGO else None


def decodificar_estado(txt):
    """Inverso de codificar_estado. Lanza excepción si el texto no es válido."""
    datos = base64.urlsafe_b64decode(txt + "=" * (-len(txt) % 4))
    d = zlib.decompressobj()
    raw = d.decompress(datos, 1_000_000)  # límite de tamaño por seguridad
    estado = json.loads(raw.decode("utf-8"))
    if not isinstance(estado, dict):
        raise ValueError("estado inválido")
    return estado


# =====================================================================
# Google Sheets (mediante un script de Apps Script del propio usuario)
# =====================================================================
COLUMNAS_HOJA = ["id", "hora", "responsable", "lote", "variedad", "etapa", "unidad", "etiqueta",
                 "flores", "verdes", "maduras", "bayas", "modo", "nota"]


def _seguro(v):
    """Evita que un texto que empieza con = + - @ se interprete como fórmula en la hoja."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _para_hoja(m):
    return {c: _seguro(m.get(c, "")) for c in COLUMNAS_HOJA}


def url_hoja_valida(url):
    return isinstance(url, str) and url.strip().startswith("https://script.google.com/")


def enviar_a_hoja(url, token, muestras, accion="agregar", validar=True, timeout=30):
    """
    Envía muestras al script de Apps Script. Devuelve el dict de respuesta
    ({"ok": True, "agregadas": n, "actualizadas": m}). Lanza excepción si algo falla.
    """
    import requests

    if validar and not url_hoja_valida(url):
        raise ValueError("La dirección del script debe empezar por https://script.google.com/")
    carga = {"token": token, "accion": accion, "muestras": [_para_hoja(m) for m in muestras]}
    r = requests.post(url.strip(), data=json.dumps(carga), headers={"Content-Type": "text/plain;charset=utf-8"},
                      timeout=timeout)
    r.raise_for_status()
    try:
        res = r.json()
    except ValueError:
        raise ValueError("El script no respondió como se esperaba. Revisa que lo implementaste con acceso "
                         "«Cualquier usuario» y que copiaste la dirección que termina en /exec.")
    if not res.get("ok"):
        raise ValueError(res.get("error", "error desconocido"))
    return res


# =====================================================================
# Excel
# =====================================================================
def generar_excel(muestras, params, area_ha=1.0):
    """Devuelve los bytes de un .xlsx con las hojas Resumen, Muestras y Parámetros."""
    import io
    from datetime import datetime

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    unidades_ha, factor, cuajado, peso = params
    cab_fill = PatternFill("solid", fgColor="3F4A9E")
    cab_font = Font(bold=True, color="FFFFFF")
    fino = Side(style="thin", color="DFE3F5")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)

    def texto_seguro(celda, valor):
        celda.value = valor
        if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
            celda.data_type = "s"

    def cabecera(ws, fila, titulos):
        for j, t in enumerate(titulos, 1):
            c = ws.cell(row=fila, column=j, value=t)
            c.fill, c.font, c.border = cab_fill, cab_font, borde
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def anchos(ws, valores):
        for j, w in enumerate(valores, 1):
            ws.column_dimensions[get_column_letter(j)].width = w

    wb = Workbook()

    # ---------------- Resumen ----------------
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = "ContaBlue · Estimación de producción"
    ws["A1"].font = Font(bold=True, size=16, color="1B1F4B")
    ws["A2"] = f"Generado el {datetime.now():%d/%m/%Y %H:%M}"
    ws["A2"].font = Font(italic=True, color="5B6190")
    titulos = ["Lote", "Muestras", "Flores / unidad", "Bayas / unidad", "Verdes / unidad", "Maduras / unidad",
               "Madurez", "kg/ha estimados", "± margen (95 %)", "Confianza", f"Toneladas en {area_ha:g} ha"]
    cabecera(ws, 4, titulos)
    fila = 5
    lotes = sorted({m["lote"] for m in muestras})
    for nombre, ms in [(lt, [m for m in muestras if m["lote"] == lt]) for lt in lotes] + [("TODOS LOS LOTES", muestras)]:
        if not ms:
            continue
        r = resumen(ms, unidades_ha, factor, cuajado, peso)
        valores = [nombre, r["n_muestras"], r["flores_por_unidad"], r["bayas_por_unidad"], r["verdes_por_unidad"],
                   r["maduras_por_unidad"], r["pct_madurez"] if r["pct_madurez"] is not None else "—",
                   r["kg_ha_total"], r["margen"] if r["margen"] is not None else "—", r["calidad"],
                   r["kg_ha_total"] * area_ha / 1000.0]
        for j, v in enumerate(valores, 1):
            c = ws.cell(row=fila, column=j)
            texto_seguro(c, v)
            c.border = borde
            if j in (3, 4, 5, 6):
                c.number_format = "0.0"
            elif j == 7 and isinstance(v, float):
                c.number_format = "0%"
            elif j in (8, 9) and isinstance(v, (int, float)):
                c.number_format = "#,##0"
            elif j == 11:
                c.number_format = "#,##0.00"
            if nombre == "TODOS LOS LOTES":
                c.font = Font(bold=True)
        fila += 1
    ws.cell(row=fila + 1, column=1, value="Las estimaciones dependen de los parámetros de la hoja «Parámetros».").font = \
        Font(italic=True, color="5B6190")
    anchos(ws, [22, 11, 14, 14, 14, 16, 11, 16, 16, 12, 18])
    ws.row_dimensions[4].height = 32
    ws.freeze_panes = "A5"

    # ---------------- Muestras ----------------
    wm = wb.create_sheet("Muestras")
    cols = [("hora", "Fecha y hora"), ("responsable", "Responsable"), ("lote", "Lote"), ("variedad", "Variedad"),
            ("etapa", "Etapa"), ("unidad", "Unidad"), ("etiqueta", "Etiqueta"), ("flores", "Flores"),
            ("verdes", "Verdes"), ("maduras", "Maduras"), ("bayas", "Bayas (total)"), ("modo", "Modo"),
            ("nota", "Nota")]
    cabecera(wm, 1, [t for _, t in cols])
    for i, m in enumerate(muestras, 2):
        for j, (k, _) in enumerate(cols, 1):
            c = wm.cell(row=i, column=j)
            texto_seguro(c, m.get(k, ""))
            c.border = borde
    wm.freeze_panes = "A2"
    wm.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(len(muestras) + 1, 2)}"
    anchos(wm, [19, 16, 14, 13, 13, 16, 22, 9, 9, 9, 13, 9, 30])

    # ---------------- Parámetros ----------------
    wp = wb.create_sheet("Parámetros")
    cabecera(wp, 1, ["Parámetro", "Valor"])
    filas = [("Unidades de muestreo por hectárea", unidades_ha), ("Factor de corrección por oclusión", factor),
             ("Cuajado (flores que llegan a fruto)", cuajado), ("Peso medio por baya (g)", peso),
             ("Área del lote (ha)", area_ha)]
    for i, (k, v) in enumerate(filas, 2):
        wp.cell(row=i, column=1, value=k).border = borde
        c = wp.cell(row=i, column=2, value=v)
        c.border = borde
        if k.startswith("Cuajado"):
            c.number_format = "0%"
    wp.cell(row=len(filas) + 3, column=1,
            value="kg/ha = (bayas + flores × cuajado) × factor de oclusión × unidades por ha × peso por baya").font = \
        Font(italic=True, color="5B6190")
    anchos(wp, [40, 16])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
