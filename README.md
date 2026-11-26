# Conteo de bayas y flores 
App web que se usa desde el celular: tomas una foto, Roboflow detecta flores y bayas, y la app estima la producción por hectárea.

## Ejecutar en tu computador
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Usarla desde el celular (necesita HTTPS para abrir la cámara)
1. Sube esta carpeta a un repositorio de GitHub.
2. En https://share.streamlit.io crea una app apuntando a `app.py`.
3. En *Settings → Secrets* pega:
   ```toml
   ROBOFLOW_API_KEY = "tu_api_key"
   ROBOFLOW_MODEL_ID = "tu-proyecto/1"
   ```
4. Abre la URL en el celular (puedes "Agregar a pantalla de inicio").

## Antes de confiar en los números
- Los nombres de clase (panel lateral) deben coincidir con los de tu proyecto en Roboflow.
- Calibra el **factor de oclusión**: cuenta a mano 30–50 unidades, compáralas con el conteo del modelo y usa el cociente real/detectado.
- Mide el **peso medio de baya** y la **tasa de cuajado** de tu variedad.
- Usa la misma distancia y encuadre en todas las fotos, y reparte las muestras por todo el lote (mínimo ~10).

## Archivos
- `app.py`: interfaz.
- `nucleo.py`: llamada a Roboflow, dibujo de cajas y fórmula de estimación.
