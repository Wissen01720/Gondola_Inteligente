# Scapder Vision — Prototipo

Prototipo de escritorio para el reto de space management con visión
computacional (Scapder). Este primer entregable cubre el **Módulo 1:
Carga y Limpieza de Video**, construido para escalar hacia detección de
personas, tracking, eventos de interacción y dashboard de métricas.

---

## 1. Qué se construyó

Una app de escritorio en **Python + PySide6** (Qt) con arquitectura en
capas para que cada módulo del reto (carga, detección, tracking,
dashboard) sea una pieza independiente y no un solo archivo gigante.

```
scapder-vision/
├── app/
│   ├── main.py              # Punto de entrada de la aplicación
│   ├── ui/
│   │   └── main_window.py   # Ventana principal (QTabWidget). Cada módulo
│   │                         # futuro = una pestaña nueva.
│   ├── core/
│   │   ├── video_loader.py  # Carga de video + metadatos + validaciones
│   │   ├── video_cleaner.py # Limpieza: frames negros/congelados + reencode
│   │   └── workers.py       # QThread para que la UI no se congele al limpiar
│   └── utils/
│       └── config.py        # TODOS los parámetros ajustables del proyecto
├── data/
│   ├── raw/                 # (reservado para videos originales, opcional)
│   ├── processed/           # Videos ya limpios, listos para el pipeline de CV
│   └── logs/                # Miniaturas y logs locales
├── requirements.txt
├── run.sh / run.bat
└── README.md
```

### Flujo funcional de este módulo

1. **Cargar video(s)** → `video_loader.load_video()` abre el archivo,
   valida formato/peso/duración y extrae metadatos (resolución, fps,
   duración, tamaño) sin recorrer todo el video (rápido).
2. **Vista previa** → `video_loader.extract_thumbnail()` saca un frame
   al 10% de la duración para mostrarlo en el panel derecho.
3. **Limpiar** → `video_cleaner.clean_video()` recorre frame a frame:
   - Descarta frames negros (cámara tapada / corte de señal).
   - Descarta frames "congelados" (cámara trabada repitiendo el mismo
     frame más de N veces seguidas).
   - Reencoda todo a un codec/formato consistente.
   - Devuelve un reporte (frames leídos, escritos, descartados por cada
     motivo) que se muestra en la interfaz.
   - Además, guarda automáticamente ese reporte como un archivo `.json`
     junto al video limpio (mismo nombre, extensión `.json`), incluyendo
     el mapeo `frame_mapping`: la correspondencia entre cada frame del
     video limpio y su posición/timestamp en el video original. Esto es
     necesario porque al quitar frames negros/congelados los índices se
     corren, y esa correspondencia no se puede reconstruir después de
     limpiar — sin este archivo, un evento detectado en el frame N del
     video limpio no se podría ubicar en el video original de 12 horas.
4. Todo el paso 3 corre en `app/core/workers.py` (un `QThread`), para
   que la ventana no se congele mientras se procesa un video largo.

La separación es intencional: `video_loader.py` y `video_cleaner.py`
**no importan nada de Qt** — se pueden probar por consola, reutilizar en
un script de línea de comandos, o llamar después desde el módulo de
detección, sin acoplarlos a la interfaz.

---

## 2. Cómo correr el proyecto

**Requisitos:** Python 3.10+ instalado localmente. Esta es una app de
escritorio (no corre en el navegador).

**Linux / Mac**

```bash
chmod +x run.sh
./run.sh
```

**Windows**

```bat
.\run.bat
```

(Ambos dentro de terminal en VS)
Cualquiera de los dos scripts:

1. Crea un entorno virtual (`venv/`) si no existe.
2. Instala `PySide6`, `opencv-python` y `numpy` desde `requirements.txt`.
3. Lanza la app con `python -m app.main`.

**Despues cada ves que se quiera ejecutar la app**

1. .\venv\Scripts\Activate.ps1
2. Lanza la app con `python -m app.main`.

**Uso dentro de la app:**

- Botón _"Cargar video(s)"_ → selecciona uno o varios archivos.
- Click en un video de la lista → ver metadatos + miniatura a la derecha.
- Botón _"Limpiar seleccionados"_ o _"Limpiar todos"_ → procesa en
  segundo plano; el resultado queda en `data/processed/`.

---

## 3. Cómo limitar duración y peso de los videos cargados

Ya se agregaron los límites al código base. Para **cambiar los valores**,
edita únicamente este archivo — no hay que tocar nada más:

📄 **`app/utils/config.py`**

```python
# Duración máxima permitida en segundos. None = sin límite.
MAX_VIDEO_DURATION_SEC = 600        # 10 minutos

# Peso máximo permitido en MB. None = sin límite.
MAX_VIDEO_SIZE_MB = 500             # 500 MB
```

- Para permitir videos más largos: sube `MAX_VIDEO_DURATION_SEC` (está
  en segundos).
- Para permitir archivos más pesados: sube `MAX_VIDEO_SIZE_MB`.
- Para quitar el límite por completo: pon `None` en cualquiera de los dos.

La validación real ocurre en **`app/core/video_loader.py`**, dentro de
la función `load_video()` — no se necesita tocarla a menos que quieras
cambiar la _lógica_ (por ejemplo, avisar en vez de rechazar, o recortar
automáticamente el video a los primeros N minutos en lugar de
rechazarlo). Los dos puntos exactos son:

```python
# Línea ~61-66: valida el peso del archivo ANTES de abrirlo con OpenCV
size_mb = path.stat().st_size / (1024 * 1024)
if MAX_VIDEO_SIZE_MB is not None and size_mb > MAX_VIDEO_SIZE_MB:
    raise VideoLoadError(...)
```

```python
# Línea ~93-97: valida la duración DESPUÉS de leer los metadatos
if MAX_VIDEO_DURATION_SEC is not None and duration_sec > MAX_VIDEO_DURATION_SEC:
    raise VideoLoadError(...)
```

Si un video excede alguno de los dos límites, la app no lo carga y
muestra el motivo en el log de la interfaz (no se congela ni truena).

---

## 4. Privacidad por diseño (desde este primer módulo)

- Ni `video_loader.py` ni `video_cleaner.py` hacen reconocimiento facial,
  ni guardan ningún dato biométrico — solo metadatos técnicos (resolución,
  fps, duración, peso) y frames de imagen para preview **local**.
- Las miniaturas se guardan en `data/logs/`, que conviene excluir de
  cualquier respaldo o repositorio si en el futuro contienen rostros
  reconocibles (por ahora son solo para revisión visual del prototipo).
- Esta capa base no envía nada a internet: todo el procesamiento es local.

---

## 5. Sugerencias para continuar el desarrollo

El proyecto está pensado para que cada punto siguiente sea una pestaña
nueva en `app/ui/main_window.py` y un módulo nuevo en `app/core/`, sin
reescribir lo ya construido.

### Corto plazo (siguiente módulo lógico)

- **Detección y tracking de personas** (`app/core/detector.py` +
  `app/core/tracker.py`): correr YOLOv8/pose sobre los videos de
  `data/processed/`, asignar un ID efímero por persona con ByteTrack o
  DeepSORT, y guardar las trayectorias (no los frames con rostro) en un
  formato ligero (CSV/JSON) para las siguientes etapas.
- **Zonificación manual**: una pestaña simple donde el usuario dibuje
  polígonos sobre un frame del video (con clicks) para marcar "góndola
  1", "pasillo 2", etc. Esto es indispensable antes de poder calcular
  dwell time o mapas de calor por zona.

### Mediano plazo

- **Dwell time y mapas de calor**: usando las trayectorias + zonas ya
  definidas, calcular tiempo de permanencia por zona y generar heatmaps
  (se puede hacer con `matplotlib`/`seaborn` embebido en Qt, o exportar
  a imagen y mostrarla).
- **Detección de eventos de interacción (pick-up / put-back)**: empezar
  con heurísticas simples (pose estimation + proximidad mano-estante +
  dirección de movimiento) antes de intentar un clasificador de acción
  entrenado — es la parte de mayor riesgo técnico del reto completo.
- **Persistencia de resultados (parcialmente resuelto):** el reporte de
  limpieza de cada video (incluido el mapeo frame-a-frame contra el
  original) ya se guarda automáticamente como `.json` junto al video
  limpio en `data/processed/`. Lo que sigue pendiente es un **registro
  histórico consolidado** de todas las corridas (por ejemplo en SQLite):
  qué videos se procesaron, cuándo y con qué configuración de
  `config.py`, para poder auditar y comparar corridas entre sí — a
  diferencia del `.json` actual, que solo describe un video individual.

### Largo plazo

- **Dashboard de métricas accionables**: zonas frías/calientes, tasa de
  interacción, tasa de rechazo (put-back/pick-up), correlacionadas con
  el layout — la pieza que convierte los datos crudos en recomendaciones
  de space management.
- **Motor de recomendación** (deseable según el reto): empezar con
  reglas simples ("zona fría + alta tasa de rechazo → sugerir
  reubicación") antes de un modelo predictivo; es más rápido de validar
  y ya cumple el criterio de "accionabilidad de insights".
- **Optimización edge con OpenVINO**: una vez el pipeline de detección
  funcione con YOLO en PyTorch, exportar el modelo a formato OpenVINO
  para que corra en tiempo real en hardware modesto (criterio de
  evaluación explícito del reto: "viabilidad edge").
- **Exportar reportes**: un botón para exportar el dashboard final a PDF
  o Excel, útil para presentar resultados a un equipo de retail que no
  va a abrir la app directamente.

### Recomendación de orden de implementación

1. Detección + tracking (sin esto no hay nada más que construir).
2. Zonificación manual (necesaria para dwell time y heatmaps).
3. Dwell time + heatmaps (primer valor demostrable con datos reales).
4. Eventos de interacción (la parte más difícil — dejarla para cuando el
   resto del pipeline ya esté validado).
5. Dashboard consolidado.
6. Motor de recomendación basado en reglas.
7. Optimización edge (OpenVINO) como paso final de "productización".