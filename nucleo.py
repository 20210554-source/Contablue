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
    """Envía la imagen a la API web de Roboflow y devuelve la lista de predicciones.

    Llama directo a la API (sin librerías pesadas), así funciona en cualquier servidor."""
    import base64
    import io

    import requests

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    r = requests.post(
        f"{api_url}/{model_id.strip().strip('/')}",
        params={"api_key": api_key, "confidence": int(confianza * 100), "overlap": int(solape * 100)},
        data=base64.b64encode(buf.getvalue()),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:150]}")
    res = r.json()
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


def _coord(x, limite):
    try:
        v = float(x)
        if math.isnan(v) or abs(v) > limite:
            return None
        return round(v, 5)
    except (TypeError, ValueError):
        return None


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
    m["lat"] = _coord(d.get("lat"), 90)
    m["lon"] = _coord(d.get("lon"), 180)
    if m["lat"] is None or m["lon"] is None:
        m["lat"] = m["lon"] = None
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
                 "flores", "verdes", "maduras", "bayas", "modo", "nota", "lat", "lon"]


def _seguro(v):
    """Evita que un texto que empieza con = + - @ se interprete como fórmula en la hoja."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _para_hoja(m):
    return {c: _seguro("" if m.get(c) is None else m.get(c, "")) for c in COLUMNAS_HOJA}


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
            ("nota", "Nota"), ("lat", "Latitud"), ("lon", "Longitud")]
    cabecera(wm, 1, [t for _, t in cols])
    for i, m in enumerate(muestras, 2):
        for j, (k, _) in enumerate(cols, 1):
            c = wm.cell(row=i, column=j)
            texto_seguro(c, "" if m.get(k) is None else m.get(k, ""))
            c.border = borde
    wm.freeze_panes = "A2"
    wm.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(len(muestras) + 1, 2)}"
    anchos(wm, [19, 16, 14, 13, 13, 16, 22, 9, 9, 9, 13, 9, 30, 12, 12])

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



# =====================================================================
# Calidad de la foto, ubicación, evolución e informe
# =====================================================================
UMBRAL_NITIDEZ = 60.0


def calidad_foto(img):
    """Revisa la foto ANTES de gastar una consulta. Devuelve la lista de problemas (vacía si está bien)."""
    import numpy as np

    problemas = []
    if min(img.size) < 480:
        problemas.append("tiene muy poca resolución")
    ch = img.convert("L")
    ch.thumbnail((640, 640))
    g = np.asarray(ch, dtype="float32")
    brillo = float(g.mean())
    if brillo < 55:
        problemas.append("está muy oscura")
    elif brillo > 220:
        problemas.append("está muy clara (sobreexpuesta)")
    if g.shape[0] > 3 and g.shape[1] > 3:
        lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
        if float(lap.var()) < UMBRAL_NITIDEZ:
            problemas.append("salió movida o desenfocada")
    return problemas


def gps_exif(datos):
    """Lee la ubicación guardada dentro de la foto (si el celular la guardó). Devuelve (lat, lon) o None."""
    import io

    try:
        exif = Image.open(io.BytesIO(datos)).getexif()
        gps = exif.get_ifd(0x8825)
        if not gps or 2 not in gps or 4 not in gps:
            return None

        def grados(t):
            d, m, s = (float(x) for x in t)
            return d + m / 60.0 + s / 3600.0

        lat = grados(gps[2]) * (-1 if str(gps.get(1, "N")).upper().startswith("S") else 1)
        lon = grados(gps[4]) * (-1 if str(gps.get(3, "E")).upper().startswith("W") else 1)
        if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
            return None
        return round(lat, 5), round(lon, 5)
    except Exception:
        return None


def evolucion_madurez(muestras):
    """% de bayas maduras por lote y por día. Devuelve [{'fecha','lote','madurez','n'}] ordenado."""
    acum = {}
    for m in muestras:
        fecha = str(m.get("hora", ""))[:10]
        v, md = int(m.get("verdes", 0) or 0), int(m.get("maduras", 0) or 0)
        if len(fecha) != 10 or (v + md) == 0:
            continue
        a = acum.setdefault((fecha, m.get("lote", "Lote 1")), [0, 0, 0])
        a[0] += md
        a[1] += v + md
        a[2] += 1
    return [{"fecha": f, "lote": lt, "madurez": a[0] / a[1], "n": a[2]} for (f, lt), a in sorted(acum.items())]


def _fuente_pdf(tam, negrita=False):
    for nombre in (("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf") if negrita
                   else ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return _fuente(tam)


def informe_pdf(muestras, params, area_ha=1.0, titulo="Todos los lotes"):
    """Informe de una página (A4) en PDF, listo para compartir. Devuelve los bytes."""
    import io
    from datetime import datetime

    unidades_ha, factor, cuajado, peso = params
    W, H = 1240, 1754
    pag = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(pag)
    azul, oscuro, gris, claro = (63, 74, 158), (27, 31, 75), (91, 97, 144), (238, 241, 252)
    f = {k: _fuente_pdf(t, b) for k, (t, b) in {"gigante": (84, True), "titulo": (54, True), "h": (34, True),
                                                  "n": (28, False), "nb": (28, True), "s": (22, False)}.items()}

    def texto(x, y, t, fuente, color=oscuro, ancla="la"):
        d.text((x, y), str(t), font=f[fuente], fill=color, anchor=ancla)

    d.rectangle([0, 0, W, 190], fill=oscuro)
    texto(70, 55, "ContaBlue", "titulo", "white")
    texto(70, 125, "Informe de estimación de producción", "n", (200, 206, 245))
    texto(W - 70, 70, f"{datetime.now():%d/%m/%Y}", "n", (200, 206, 245), "ra")
    texto(W - 70, 115, titulo, "nb", "white", "ra")

    r = resumen(muestras, unidades_ha, factor, cuajado, peso)
    ton = r["kg_ha_total"] * area_ha / 1000.0
    d.rounded_rectangle([70, 240, W - 70, 520], radius=28, fill=azul)
    texto(110, 275, "Producción total estimada", "n", (214, 219, 250))
    texto(110, 320, f"{r['kg_ha_total']:,.0f} kg/ha", "gigante", "white")
    margen = f"± {r['margen']:,.0f} kg/ha (95 % de confianza)" if r["margen"] is not None else \
        "Faltan muestras para calcular el margen de error"
    texto(110, 425, margen, "n", (214, 219, 250))
    texto(110, 470, f"≈ {ton:,.2f} toneladas en {area_ha:g} ha  ·  Confianza {r['calidad'].lower()}", "nb", "white")

    tiles = [("Muestras", f"{r['n_muestras']}"), ("Flores / unidad", f"{r['flores_por_unidad']:.1f}"),
             ("Bayas / unidad", f"{r['bayas_por_unidad']:.1f}"),
             ("Madurez", f"{r['pct_madurez']:.0%}" if r["pct_madurez"] is not None else "—")]
    ancho = (W - 140 - 3 * 24) // 4
    for i, (et, val) in enumerate(tiles):
        x = 70 + i * (ancho + 24)
        d.rounded_rectangle([x, 560, x + ancho, 700], radius=20, fill=claro)
        texto(x + 24, 580, et, "s", gris)
        texto(x + 24, 622, val, "h")

    texto(70, 745, "Resultado por lote", "h")
    cols = [("Lote", 70, "la"), ("Muestras", 470, "ra"), ("Flores/u", 640, "ra"), ("Bayas/u", 800, "ra"),
            ("Madurez", 970, "ra"), ("kg/ha", W - 70, "ra")]
    d.rectangle([70, 800, W - 70, 850], fill=oscuro)
    for t, x, a in cols:
        texto(x + (20 if a == "la" else -10), 810, t, "s", "white", a)
    lotes = sorted({m["lote"] for m in muestras})[:10]
    y = 860
    datos_barra = []
    for i, lt in enumerate(lotes):
        rr = resumen([m for m in muestras if m["lote"] == lt], unidades_ha, factor, cuajado, peso)
        if i % 2 == 0:
            d.rectangle([70, y - 4, W - 70, y + 44], fill=(248, 249, 254))
        vals = [lt[:22], rr["n_muestras"], f"{rr['flores_por_unidad']:.1f}", f"{rr['bayas_por_unidad']:.1f}",
                f"{rr['pct_madurez']:.0%}" if rr["pct_madurez"] is not None else "—", f"{rr['kg_ha_total']:,.0f}"]
        for (t, x, a), v in zip(cols, vals):
            texto(x + (20 if a == "la" else -10), y + 4, v, "n", oscuro, a)
        datos_barra.append((lt[:14], rr["kg_ha_total"]))
        y += 52
    if len(lotes) < len({m["lote"] for m in muestras}):
        texto(70, y + 6, "…hay más lotes; descarga el Excel para verlos todos.", "s", gris)

    if len(datos_barra) > 1:
        top = max(v for _, v in datos_barra) or 1
        base_y, alto = 1560, 220
        texto(70, base_y - alto - 55, "Comparación de kg/ha entre lotes", "nb")
        ancho_b = min(110, (W - 140) // (len(datos_barra) * 2))
        for i, (nom, v) in enumerate(datos_barra):
            x = 90 + i * (ancho_b * 2)
            h = int(alto * v / top)
            d.rounded_rectangle([x, base_y - h, x + ancho_b, base_y], radius=8, fill=azul)
            texto(x + ancho_b // 2, base_y + 8, nom, "s", gris, "ma")

    texto(70, H - 130, f"Parámetros: {unidades_ha:,.0f} unidades/ha · oclusión ×{factor:g} · cuajado {cuajado:.0%} · "
          f"peso de baya {peso:g} g", "s", gris)
    texto(70, H - 90, "Estimación basada en conteo por fotos; contrástala con tu cosecha real.", "s", gris)
    buf = io.BytesIO()
    pag.save(buf, "PDF", resolution=150)
    return buf.getvalue()
