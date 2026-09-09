# Scapder Vision — Prototipo

Prototipo de escritorio para el reto de space management con visión
computacional (Scapder). Este repositorio cubre, en capas incrementales:

- **Módulo 1: Carga y Limpieza de Video** — ingesta, validación y reencode.
- **Módulo 2: Detección y Eventos** — tracking, pose, zonas e interacciones.
- **Módulo 3: Trayectoria, Transporte y Backend Local** — muestras continuas
  de posición (heatmaps), bus de eventos in-process y almacenamiento SQLite.

---

## Índice

1. [Qué se construyó (visión general y estructura)](#1-qué-se-construyó-visión-general-y-estructura)
2. [Cómo correr el proyecto](#2-cómo-correr-el-proyecto)
3. [Módulo 1 — Carga y Limpieza de Video](#módulo-1--carga-y-limpieza-de-video)
   - [3.1 Qué se construyó (Módulo 1)](#31-qué-se-construyó-módulo-1)
   - [3.2 Cómo limitar duración y peso de los videos cargados](#32-cómo-limitar-duración-y-peso-de-los-videos-cargados)
   - [3.3 Qué contiene el reporte `.json` de cada limpieza](#33-qué-contiene-el-reporte-json-de-cada-limpieza)
4. [Módulo 2 — Pipeline de Detección](#módulo-2--pipeline-de-detección)
   - [4.1 Qué se construyó (Módulo 2)](#41-qué-se-construyó-módulo-2)
   - [4.2 Flujo funcional de este módulo (Módulo 2)](#42-flujo-funcional-de-este-módulo-módulo-2)
   - [4.3 Cómo correr (Módulo 2)](#43-cómo-correr-módulo-2)
   - [4.4 Qué contiene el `Event Object` (Módulo 2)](#44-qué-contiene-el-event-object-módulo-2)
5. [Módulo 3 — Trayectoria, Transporte In-Process y Backend Local](#módulo-3--trayectoria-transporte-in-process-y-backend-local)
   - [5.1 Captura de trayectoria continua (`PositionSample`)](#51-captura-de-trayectoria-continua-positionsample)
   - [5.2 Fuentes de frames: video limpio y cámara en vivo](#52-fuentes-de-frames-video-limpio-y-cámara-en-vivo)
   - [5.3 Transporte in-process (señales Qt)](#53-transporte-in-process-señales-qt)
   - [5.4 Edición de zonas (ROI) en la UI](#54-edición-de-zonas-roi-en-la-ui)
   - [5.5 Backend local (SQLite + heatmap)](#55-backend-local-sqlite--heatmap)
6. [Contratos de datos documentados](#6-contratos-de-datos-documentados)
7. [Privacidad por diseño](#7-privacidad-por-diseño)
8. [Sugerencias para continuar el desarrollo](#8-sugerencias-para-continuar-el-desarrollo)

---

## 1. Qué se construyó (visión general y estructura)

Una app de escritorio en **Python + PySide6** (Qt) con arquitectura en
capas para que cada módulo del reto (carga, detección, tracking,
dashboard) sea una pieza independiente y no un solo archivo gigante.
El código se reorganizó en subpaquetes por propiedad de equipo
(ver [`MIGRATION.md`](MIGRATION.md) para el historial de movimientos):

```
scapder-vision/
├── app/
│   ├── main.py                    # Punto de entrada de la aplicación
│   ├── ui/
│   │   ├── main_window.py         # Ventana principal (QTabWidget). Cada módulo
│   │   │                          # futuro = una pestaña nueva.
│   │   └── zone_editor_tab.py     # Pestaña 2: dibujo manual de zonas (ROI)
│   ├── core/
│   │   ├── ingestion/             # Team 1 — cámara/IoT e ingesta de frames
│   │   │   ├── video_loader.py    #   Carga de video + metadatos + validaciones
│   │   │   ├── video_cleaner.py   #   Limpieza: frames negros/congelados + reencode
│   │   │   ├── workers.py         #   QThread para que la UI no se congele (limpieza)
│   │   │   └── frame_source.py    #   FrameSource: video limpio + mapping / cámara en vivo (stub)
│   │   ├── detection/             # Team 2 — pipeline de detección
│   │   │   ├── tracker.py         #   Detección + tracking con ByteTrack integrado (YOLOv11, clase 0 COCO)
│   │   │   ├── pose.py            #   Estimación de pose corporal (17 keypoints)
│   │   │   ├── zone.py            #   Zonas + señales geométricas (ZoneManager)
│   │   │   ├── state_machine.py   #   Máquina de estados IDLE→REACHING→HOLDING
│   │   │   ├── frame_mapping.py   #   Traducción de timestamps limpio → original
│   │   │   ├── schemas.py         #   Contratos Pydantic (fuente de verdad)
│   │   │   ├── event_publisher.py #   Bus de eventos (file / stdout / in-process Qt)
│   │   │   ├── trajectory.py      #   Captura continua de posición (PositionSample)
│   │   │   ├── pipeline_worker.py #   QThread para correr el pipeline sin congelar la UI
│   │   │   └── pipeline.py        #   Orquestador frame a frame (consume FrameSource)
│   │   └── backend/               # Team 3 — almacenamiento y agregación
│   │       ├── event_store.py     #   SQLite local (eventos + muestras) + suscripción al bus
│   │       └── heatmap.py         #   Cuadrícula de densidad (grid + blur gaussiano)
│   └── utils/
│       └── config.py              # TODOS los parámetros ajustables del proyecto
├── data/
│   ├── processed/                 # Videos ya limpios, listos para el pipeline de CV
│   ├── zones/                     # Polígonos de zona (.json, esquema Zone)
│   ├── events/                    # Log local de eventos (.jsonl) para debug
│   └── logs/                      # Miniaturas y logs locales
├── docs/
│   ├── event_schema.md            # Contrato de datos del bus (auto-generado)
│   └── zone_schema.md             # Contrato de datos de zonas (auto-generado)
├── scripts/
│   ├── run_pipeline_debug.py      # Debug visual sin UI (bboxes, keypoints, zonas)
│   └── generate_schema_docs.py    # Genera docs/event_schema.md y docs/zone_schema.md
├── tests/                         # Tests unitarios (state machine, trayectoria, fuentes, backend)
├── requirements.txt
├── run.sh / run.bat
└── README.md
```

### Flujo funcional de este módulo (Módulo 1)

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
4. Todo el paso 3 corre en `app/core/ingestion/workers.py` (un
   `QThread`), para que la ventana no se congele mientras se procesa un
   video largo.

La separación es intencional: `video_loader.py` y `video_cleaner.py`
**no importan nada de Qt** — se pueden probar por consola, reutilizar en
un script de línea de comandos, o llamar después desde el módulo de
detección, sin acoplarlos a la interfaz.

- **Flujo completo**: video original → limpieza (`Módulo 1`) → pipeline
  de detección (`Módulo 2`) → trayectoria + eventos → SQLite/heatmap
  (`Módulo 3`).
- **Hilos**: la UI nunca corre trabajo pesado; limpieza y detección
  corren en `QThread` workers que reportan por señales Qt.
- **Transporte de eventos**: in-process vía señales Qt (MVP). Los modos
  `file`/`stdout` quedan para debug. Un transporte de red (WebSocket/MQTT)
  es trabajo futuro explícitamente fuera de alcance — ver
  [`docs/event_schema.md`](docs/event_schema.md).

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
2. Instala `PySide6`, `opencv-python`, `numpy`, `ultralytics`, `shapely`
   y `pydantic` desde `requirements.txt`.
3. Lanza la app con `python -m app.main`.

**Despues cada ves que se quiera ejecutar la app**

1. `.\venv\Scripts\Activate.ps1` (Windows) o `source venv/bin/activate` (Linux/Mac)
2. Lanza la app con `python -m app.main`.

**Uso dentro de la app:**

- Pestaña _"1. Carga y Limpieza de Video"_:
  - Botón _"Cargar video(s)"_ → selecciona uno o varios archivos.
  - Click en un video de la lista → ver metadatos + miniatura a la derecha.
  - Botón _"Limpiar seleccionados"_ o _"Limpiar todos"_ → procesa en
    segundo plano; el resultado queda en `data/processed/`.
- Pestaña _"2. Edición de Zonas (ROI)"_:
  - Botón _"Cargar video (frame de referencia)"_ → extrae el frame sobre
    el que se dibujará la zona.
  - Clics sobre el frame agregan vértices del polígono; _"Deshacer
    punto"_ / _"Limpiar puntos"_ corrigen el dibujo; escribe un nombre y
    _"Guardar zona"_ persiste en `data/zones/` con el esquema `Zone`.

---

# Módulo 1 — Carga y Limpieza de Video

## 3.1 Qué se construyó (Módulo 1)

Ya descrito en la sección [1](#1-qué-se-construyó-visión-general-y-estructura):
carga, validación, limpieza (frames negros/congelados), reencode y el
reporte `.json` con el `frame_mapping` — la pieza que conecta cada frame
limpio con su momento en el video original.

## 3.2 Cómo limitar duración y peso de los videos cargados

Ya se agregaron los límites al código base. Para **cambiar los valores**,
edita únicamente este archivo — no hay que tocar nada más:

📄 **`app/utils/config.py`**

```python
# Duración máxima permitida en segundos. None = sin límite.
MAX_VIDEO_DURATION_SEC = 43200       # 12 horas

# Peso máximo permitido en MB. None = sin límite.
MAX_VIDEO_SIZE_MB = 10000            # 10 GB
```

- Para permitir videos más largos: sube `MAX_VIDEO_DURATION_SEC` (está
  en segundos).
- Para permitir archivos más pesados: sube `MAX_VIDEO_SIZE_MB`.
- Para quitar el límite por completo: pon `None` en cualquiera de los dos.

La validación real ocurre en `app/core/ingestion/video_loader.py`, dentro
de la función `load_video()` — no se necesita tocarla a menos que quieras
cambiar la _lógica_ (por ejemplo, avisar en vez de rechazar, o recortar
automáticamente el video a los primeros N minutos en lugar de
rechazarlo). Los dos puntos exactos son:

```python
# Valida el peso del archivo ANTES de abrirlo con OpenCV
size_mb = path.stat().st_size / (1024 * 1024)
if MAX_VIDEO_SIZE_MB is not None and size_mb > MAX_VIDEO_SIZE_MB:
    raise VideoLoadError(...)
```

```python
# Valida la duración DESPUÉS de leer los metadatos
if MAX_VIDEO_DURATION_SEC is not None and duration_sec > MAX_VIDEO_DURATION_SEC:
    raise VideoLoadError(...)
```

Si un video excede alguno de los dos límites, la app no lo carga y
muestra el motivo en el log de la interfaz (no se congela ni truena).

## 3.3 Qué contiene el reporte `.json` de cada limpieza

Cada vez que se limpia un video, junto al video de salida en
`data/processed/` se genera un archivo con el mismo nombre y extensión
`.json` (por ejemplo `mi_video_clean.json`). Ejemplo real de contenido:

```json
{
  "frames_read": 500,
  "frames_written": 480,
  "black_frames_removed": 15,
  "frozen_frames_removed": 5,
  "output_fps": 30.0,
  "output_resolution": [1280, 720],
  "output_path": "data/processed/mi_video_clean.mp4",
  "frame_mapping": [
    {"clean_frame": 0, "original_frame": 0, "original_timestamp_sec": 0.0},
    {"clean_frame": 1, "original_frame": 1, "original_timestamp_sec": 0.033},
    {"clean_frame": 2, "original_frame": 4, "original_timestamp_sec": 0.133}
  ]
}
```

- Los primeros campos (`frames_read`, `frames_written`, etc.) son el
  resumen general de la limpieza.
- `frame_mapping` es la parte clave para las siguientes etapas del
  pipeline: por cada frame que quedó en el video limpio, indica qué
  posición y qué segundo tenía ese mismo contenido en el video
  **original** (antes de quitar frames negros/congelados). Sin esto, un
  evento detectado en el video limpio no se podría ubicar en el video
  original de hasta 12 horas.
- Si el video no tenía frames negros ni congelados, `frame_mapping`
  simplemente queda 1 a 1 (`clean_frame` == `original_frame` en cada
  fila) — se genera igual, por consistencia entre todos los videos
  procesados.

---

# Módulo 2 — Pipeline de Detección

Módulo que realiza el análisis computacional en video: detecta personas,
las sigue entre frames, estima la pose corporal, chequea zonas geométricas
de interacción con estantes y genera eventos cuando se detectan acciones
(alcanzar, sostener, tomar producto, devolver producto). Diseñado como
una capa puramente computacional: sin Qt, sin interfaz — solo cálculos y
eventos emitidos a través de un bus generalizado.

## 4.1 Qué se construyó (Módulo 2)

Un pipeline de visión computacional con una arquitectura modular donde
cada componente tiene una responsabilidad clara (todos en
`app/core/detection/`):

```
app/core/detection/
├── tracker.py           # Detección + tracking con ByteTrack integrado (YOLOv11, clase 0 COCO)
├── pose.py              # Estimación de pose corporal (17 keypoints COCO)
├── zone.py              # Validación de zonas y cálculo de señales geométricas
├── state_machine.py     # Máquina de estados: IDLE → REACHING → HOLDING → EVENTO
├── frame_mapping.py     # Traducción de timestamps desde video limpio al original
├── schemas.py           # Contratos Pydantic para validación de datos
├── event_publisher.py   # Bus de eventos (archivo / stdout / in-process Qt)
├── trajectory.py        # Captura continua de posición (PositionSample, Módulo 3)
├── pipeline_worker.py   # QThread para correr el pipeline sin bloquear la UI
└── pipeline.py          # Orquestador que corre todo el flujo frame a frame
```

## 4.2 Flujo funcional de este módulo (Módulo 2)

1. **Cargar frames** → `pipeline.run(source)` acepta una `FrameSource`:
   un video limpio de `data/processed/` con su `.json` de `frame_mapping`
   (comportamiento original, construido por `VideoFileFrameSource`) o una
   fuente en vivo (stub de Team 1). El pipeline ya no sabe si la entrada
   es archivo o cámara.

2. **Tracking de personas** → `tracker.track(frame, frame_index)` detecta
   y sigue personas usando YOLOv11 + ByteTrack. Cada persona recibe un
   `track_id` único que persiste a lo largo del video (se reinicia en cada
   ejecución, no es identidad persistente entre sesiones).

3. **Estimación de pose** → `pose_estimator.estimate(frame, tracked_people)`
   calcula 17 keypoints COCO (muñecas, codos, hombros, caderas, etc.) y
   los asocia a cada persona trackeada por proximidad de bounding box + IoU.

4. **Chequeo geométrico de zona** → `check_zone_signal(pose, zones)` verifica:
   - ¿Está la muñeca dentro del polígono de la zona? (`wrist_inside`)
   - ¿Está el brazo extendido? (`arm_extended`, usando relación
     distancia(muñeca, hombro) / distancia(hombro, codo) ≥ threshold)
   - **Filtro de confianza**: ambos keypoints (muñeca y hombro) deben tener
     confianza ≥ `MIN_KEYPOINT_CONFIDENCE` (0.3 por defecto) para ser válidos.

5. **Máquina de estados** → `state_machine.process(zone_signals)` sigue la
   interacción de cada persona con cada zona según este flujo:
   - **IDLE** → si `wrist_inside=True` y `arm_extended=True`, transiciona a
     **REACHING**.
   - **REACHING** → si el brazo se mantiene extendido dentro, incrementa un
     contador. Al alcanzar `MIN_FRAMES_REACHING_TO_HOLDING` (5 frames por
     defecto), transiciona a **HOLDING**. **Detección de atasco**: si la
     muñeca sigue dentro pero el brazo NO está extendido durante más de
     `MAX_SECONDS_STUCK_REACHING` (1 segundo = ~30 frames a 30 fps), la
     máquina resetea a IDLE sin emitir evento — evita falsos positivos.
   - **HOLDING** → si la muñeca permanece dentro durante al menos
     `MIN_FRAMES_HOLDING` (8 frames), y luego sale de la zona, emite un
     evento con `action="taken"`.
   - Pérdida de tracking: si una persona desaparece durante más de
     `MAX_FRAMES_MISSING_TO_RESET` (10 frames), todos sus estados se
     reinician a IDLE sin emitir eventos.

6. **Traducción de timestamps** → la `FrameSource` devuelve cada frame con
   su timestamp ya resuelto: `VideoFileFrameSource` usa `frame_mapping.py`
   para convertir el índice del video limpio al segundo absoluto del video
   original (crítico para ubicar eventos en la timeline original); una
   fuente en vivo usaría wall-clock sin mapeo.

7. **Publicación de eventos** → `event_publisher.publish(event)` emite cada
   evento (`InteractionEvent` y `PositionSample`) según el modo configurado:
   - `"file"`: guarda JSON local en `data/events/` (respaldo persistente).
   - `"stdout"`: imprime en consola (para debug).
   - `"inprocess"`: señal Qt `Signal(dict)` — transporte del MVP, ver Módulo 3.

## 4.3 Cómo correr (Módulo 2)

**Script de debug visual (sin interfaz de usuario):**

```bash
python -m scripts.run_pipeline_debug --video data/processed/mi_video_clean.mp4
```

Visualiza en tiempo real:
- Bounding boxes de personas detectadas, coloreadas por **estado de
  interacción**: azul = IDLE, amarillo = REACHING, rojo = HOLDING.
- Keypoints de pose superpuestos como **círculos amarillos**,
  únicamente si superan el umbral de confianza (`MIN_KEYPOINT_CONFIDENCE`,
  0.3 por defecto); los que no lo superan simplemente **no se dibujan**.
- Polígonos de zonas siempre en verde.
- Eventos de interacción impresos en consola a medida que ocurren.

**Ejecutar tests unitarios:**

```bash
pytest tests/ -v
```

Verifica:
- Transiciones correctas de máquina de estados (IDLE → REACHING → HOLDING).
- Detección de atascos en REACHING (resetea a IDLE sin evento).
- Pérdida de tracking y reset automático.
- Independencia entre múltiples personas y zonas simultáneamente.
- Trayectoria continua (`PositionSample`), fuentes de frames y backend.

## 4.4 Qué contiene el `Event Object` (Módulo 2)

Un objeto `InteractionEvent` serializado a JSON se ve así:

```json
{
  "track_id": 42,
  "zone_id": "shelf_A1",
  "action": "taken",
  "timestamp": 125.4,
  "event_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- `track_id` (int): identificador efímero de la persona en esta sesión de
  video (reinicia en 0 para cada video, no es persistente entre sesiones).
- `zone_id` (str): nombre único de la zona de góndola donde ocurrió la
  interacción (ej: "shelf_A1", "shelf_B2"). Definido por el usuario en el
  editor manual de zonas (pestaña 2 de la app).
- `action` (str, enum): tipo de interacción detectada:
  - `"taken"`: persona extrajo producto de la zona (salió del estado HOLDING).
  - Nota: por diseño actual, no se distingue "pick-up" vs "put-back" solo
    con pose — se necesaría detectar producto o movimiento bidireccional. Por
    ahora se emite `"taken"` como placeholder.
- `timestamp` (float): segundos desde el inicio del video **original** (antes
  de limpieza), alineado con la duración real de la cámara. Calculado usando
  `frame_mapping` para reproducibilidad exacta.
- `event_id` (str, UUID): identificador único del evento, generado al
  instante. Útil para auditoría y deduplicación si un evento se publica a
  múltiples destinos.

Ejemplo de un archivo de log generado en `data/events/`:

```json
[
  {"track_id": 1, "zone_id": "shelf_A1", "action": "taken", "timestamp": 12.5, "event_id": "..."},
  {"track_id": 2, "zone_id": "shelf_A1", "action": "taken", "timestamp": 15.3, "event_id": "..."},
  {"track_id": 3, "zone_id": "shelf_B2", "action": "taken", "timestamp": 18.7, "event_id": "..."}
]
```

---

# Módulo 3 — Trayectoria, Transporte In-Process y Backend Local

Este módulo cierra los tres vacíos que el Módulo 2 dejó pendientes:
captura de posición continua (la base del heatmap — prioridad #1 del
jurado), desacople de la entrada ("solo video limpio") y un transporte de
eventos sin red para el dashboard.

## 5.1 Captura de trayectoria continua (`PositionSample`)

Los eventos de interacción (`InteractionEvent`) son **discretos** (se
disparan cuando alguien toma un producto). Para un heatmap de
"dónde circula y dónde no la gente" se necesitan **muestras continuas**:

- `trajectory.py` (`TrajectoryCapture`) registra, por cada frame procesado
  y por cada persona activa: `track_id`, `frame_index`, timestamp original
  (traducido por la `FrameSource`, sin duplicar `frame_mapping.py`) y la
  posición del pie — el **bottom-center del bbox** como proxy razonable.
- Se emite como su propio esquema ligero `PositionSample`
  (`schemas.py`), **sin sobrecargar** `InteractionEvent`, por el **mismo**
  `EventPublisher` — el receptor no necesita dos transportes distintos.
- La frecuencia se ajusta con `TRAJECTORY_SAMPLE_EVERY_N_FRAMES` en
  `config.py` (por defecto 1 = todos los frames).

## 5.2 Fuentes de frames: video limpio y cámara en vivo

`app/core/ingestion/frame_source.py` define la interfaz `FrameSource`:

- `VideoFileFrameSource(video_path)` — comportamiento original: video
  limpio + `frame_mapping.json` sidecar; traduce timestamps al video
  original. `pipeline.run()` y `pipeline.run_video(path)` lo usan tal cual.
- `LiveFrameSource` — **stub para Team 1** (webcam/RTSP): sin video
  original que mapear, timestamps wall-clock que pasan sin cambios.

El pipeline no tiene ninguna rama "si es archivo vs si es cámara" dentro
del bucle: solo consume `FrameSource.next_frame()`.

## 5.3 Transporte in-process (señales Qt)

`app/core/detection/event_publisher.py`:

- `EventPublisher.publish(event)` ahora acepta **cualquier modelo Pydantic**
  (no solo `InteractionEvent`) — un solo bus para eventos y muestras.
- `InProcessPublisher`: nueva subclase que emite `event_emitted =
  Signal(dict)` con `event.model_dump()`; cualquier widget se conecta
  directamente (las conexiones entre hilos se ponen en cola solas).
- `DetectionPipelineWorker` (`pipeline_worker.py`) corre el pipeline en un
  `QThread` (mismo patrón que `workers.py` del Módulo 1), así el stream
  frecuente de `PositionSample` nunca bloquea la UI.
- Los modos `file` y `stdout` siguen intactos para debug/logging.
- **Explícitamente fuera de alcance del MVP**: un transporte de red
  (WebSocket o MQTT) es trabajo futuro razonable si esto corre en varias
  máquinas — documentado en `docs/event_schema.md`. No se implementó el
  placeholder de WebSocket que existía.

## 5.4 Edición de zonas (ROI) en la UI

`app/ui/zone_editor_tab.py` (pestaña "2. Edición de Zonas (ROI)"):

- Carga un video y usa la utilidad `extract_thumbnail` del Módulo 1 como
  frame de referencia (a resolución completa).
- Cada click agrega un vértice del polígono; los vértices se guardan en
  coordenadas del frame **original** (no del lienzo escalado).
- Se nombra la zona y se guarda con el **`ZoneManager` existente**
  (`app/core/detection/zone.py`) → `data/zones/<zone_id>.json`, sin
  inventar un formato nuevo (ver `docs/zone_schema.md`).

## 5.5 Backend local (SQLite + heatmap)

`app/core/backend/` (stubs con TODOs — trabajo activo de Team 3):

- `event_store.py` — `EventStore`: tablas `events` y `position_samples`
  en SQLite local (`data/scapder_events.db`,
  `EVENT_STORE_DB_PATH` en `config.py`); `connect_store_to_publisher()`
  suscribe el almacén a la señal de `InProcessPublisher` — persistencia
  automática sin red.
- `heatmap.py` — `build_density_grid()`: convierte `PositionSample`
  acumuladas en una cuadrícula 2D (`numpy` + `cv2.GaussianBlur`, no
  conteos crudos) lista para el dashboard (Team 4).

---

## 6. Contratos de datos documentados

| Contrato | Archivo | Generado por |
|----------|---------|--------------|
| Eventos del bus (`InteractionEvent`, `PositionSample`) | [`docs/event_schema.md`](docs/event_schema.md) | `scripts/generate_schema_docs.py` |
| Zonas (`Zone`, `ZoneSignal`, formato de archivo) | [`docs/zone_schema.md`](docs/zone_schema.md) | `scripts/generate_schema_docs.py` |

Los `.md` se **generan desde el código real** (los modelos Pydantic de
`app/core/detection/schemas.py` y `zone.py` son la fuente de verdad):
si el esquema cambia, se regeneran con
`python -m scripts.generate_schema_docs` — nunca se editan a mano.

---

## 7. Privacidad por diseño

### Módulo 1

- Ni `video_loader.py` ni `video_cleaner.py` hacen reconocimiento facial,
  ni guardan ningún dato biométrico — solo metadatos técnicos (resolución,
  fps, duración, peso) y frames de imagen para preview **local**.
- Las miniaturas se guardan en `data/logs/`, que conviene excluir de
  cualquier respaldo o repositorio si en el futuro contienen rostros
  reconocibles (por ahora son solo para revisión visual del prototipo).
- Esta capa base no envía nada a internet: todo el procesamiento es local.

### Módulo 2 y 3

- **Sin reconocimiento facial**: el sistema solo calcula bounding boxes de
  cuerpo completo y coordenadas numéricas de articulaciones (muñeca, codo,
  hombro). No entrena ni usa modelos de identidad facial.
- **Sin biometría**: no se guardan características biométricas (gait, altura,
  forma corporal específica de la persona).
- **Sin almacenamiento de imágenes**: los keypoints y las muestras de
  trayectoria son coordenadas (x, y, confidence) — no se guardan crops de
  imagen, no se archivan rostros ni siluetas.
- **Track IDs efímeros**: los identificadores de persona se generan
  dinámicamente durante la ejecución y se descartan al cerrar el video. No
  persisten entre sesiones ni se pueden usar para re-identificar a la misma
  persona en otro video (no hay base de datos de identidades).
- **Timestamps traceable al original**: los eventos y las muestras de
  posición se pueden ubicar exactamente en el video original, útil para
  auditoría y revisión manual en caso de disputa o error del sistema.

---

## 8. Sugerencias para continuar el desarrollo

El proyecto está pensado para que cada punto siguiente sea una pestaña
nueva en `app/ui/main_window.py` y un módulo nuevo en `app/core/`, sin
reescribir lo ya construido.

### Corto plazo (siguiente iteración)

- **Dashboard de heatmap (Team 4 + Team 3)**: los datos ya fluyen
  (`PositionSample` → `EventStore`); falta la pestaña que lea el SQLite,
  genere el grid con `heatmap.build_density_grid()` y lo pinte
  (Qt/matplotlib embebido). Es la pieza más visible para el jurado.
- **Implementar la cámara en vivo (Team 1)**: reemplazar el stub
  `LiveFrameSource` por `cv2.VideoCapture` de webcam/RTSP con timestamps
  wall-clock — el resto del pipeline no cambia.
- **Distinción pick-up vs put-back**: actualmente todos los eventos se
  emiten como `action="taken"`. Para distinguir si la persona **extrajo** o
  **devolvió** el producto, se podría:
  - Detectar el movimiento de la mano (ascendente = tomar, descendente = devolver).
  - Usar una red clasificadora pequeña entrenada con anotaciones locales.
  - Combinar con información de carrito / zona de compra cercana.

### Mediano plazo

- **Dwell time por zona**: con las muestras de trayectoria ya guardadas,
  calcular cuánto tiempo pasa cada persona dentro de cada polígono de zona
  (los datos están listos; falta la agregación por zona).
- **Mejora de robustez en pose bajo oclusión**: si el estante ocluye
  parcialmente al brazo, puede que los keypoints fallen. Se podría:
  - Usar modelos de pose más robustos (YOLOv11-pose-large, MediaPipe).
  - Implementar predicción de keypoints ocultos usando interpolación temporal.
- **Multizona simultánea**: hoy cada persona puede interactuar con una zona a
  la vez (por diseño del `state_machine`). Para permitir que una persona
  tenga eventos simultáneos en dos estantes (ej: comparar precios), se
  necesaría revisar la lógica de estado.
- **Persistencia de resultados consolidada**: el reporte de limpieza de cada
  video (incluido el mapeo frame-a-frame contra el original) ya se guarda
  automáticamente como `.json` junto al video limpio en `data/processed/`.
  Lo que sigue pendiente es un **registro histórico consolidado** de todas
  las corridas (por ejemplo en SQLite): qué videos se procesaron, cuándo y
  con qué configuración de `config.py`, para poder auditar y comparar
  corridas entre sí.
- **"ROI Auto-Suggest" automático**: en lugar de dibujar cada zona a mano,
  se podría entrenar un modelo ligero para detectar estantes
  automáticamente en un frame de referencia y sugerir los polígonos. La
  herramienta manual ya existe (pestaña 2); esto sería una mejora sobre
  ella.

### Largo plazo

- **Dashboard de métricas accionables**: zonas frías/calientes, tasa de
  interacción, tasa de rechazo (put-back/pick-up), correlacionadas con
  el layout — la pieza que convierte los datos crudos en recomendaciones
  de space management.
- **Análisis de patrones**: con un histórico de eventos, detectar patrones
  anómalos (ej: misma persona, mismo producto, en segundos — posible hurto o
  problema de reabastecimiento).
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

1. Detección + tracking (sin esto no hay nada más que construir) — **hecho**.
2. Zonificación manual (necesaria para dwell time y heatmaps) — **hecho**
   (pestaña 2).
3. Captura de trayectoria continua para heatmaps — **hecho** (Módulo 3).
4. Dashboard de heatmap + dwell time (primer valor demostrable con datos
   reales) — **pendiente** (datos listos, falta la pestaña).
5. Eventos de interacción pick-up vs put-back (distinción fina).
6. Dashboard consolidado de métricas.
7. Motor de recomendación basado en reglas.
8. Optimización edge (OpenVINO) como paso final de "productización".