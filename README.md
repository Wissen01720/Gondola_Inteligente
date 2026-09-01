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

## 4. Qué contiene el reporte `.json` de cada limpieza

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

## 5. Privacidad por diseño (desde este primer módulo)

- Ni `video_loader.py` ni `video_cleaner.py` hacen reconocimiento facial,
  ni guardan ningún dato biométrico — solo metadatos técnicos (resolución,
  fps, duración, peso) y frames de imagen para preview **local**.
- Las miniaturas se guardan en `data/logs/`, que conviene excluir de
  cualquier respaldo o repositorio si en el futuro contienen rostros
  reconocibles (por ahora son solo para revisión visual del prototipo).
- Esta capa base no envía nada a internet: todo el procesamiento es local.

---

## 6. Sugerencias para continuar el desarrollo

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

---

Módulo que realiza el análisis computacional en video: detecta personas,
las sigue entre frames, estima la pose corporal, chequea zonas geométricas
de interacción con estantes y genera eventos cuando se detectan acciones
(alcanzar, sostener, tomar producto, devolver producto). Diseñado como
una capa puramente computacional: sin Qt, sin interfaz — solo cálculos y
eventos emitidos a través de un bus generalizado.

---

## 7. Qué se construyó (Módulo 2)

Un pipeline de visión computacional con una arquitectura modular donde
cada componente tiene una responsabilidad clara:

```
app/core/
├── detector.py          # Detección de personas con YOLOv11 (clase 0 COCO)
├── tracker.py           # Tracking persistente con ByteTrack integrado
├── pose.py              # Estimación de pose corporal (17 keypoints COCO)
├── zone.py              # Validación de zonas y cálculo de señales geométricas
├── state_machine.py     # Máquina de estados: IDLE → REACHING → HOLDING → EVENTO
├── position.py          # Estimación híbrida de posición de pies (tobillos / bbox)
├── presence.py          # Dwell time: tiempo de permanencia por zona de producto
├── roi_suggest.py       # Sugerencia automática de zonas por detección de bordes (opcional)
├── staff.py             # Detección heurística de empleados por zona staff
├── frame_mapping.py     # Traducción de timestamps desde video limpio al original
├── schemas.py           # Contratos Pydantic para validación de datos
├── event_publisher.py   # Bus de eventos generalizado (archivo / stdout / WebSocket)
├── pipeline.py          # Orquestador que corre todo el flujo frame a frame
├── video_loader.py      # (reutilizado de Módulo 1)
├── workers.py           # (reutilizado de Módulo 1)
└── video_cleaner.py     # (reutilizado de Módulo 1)

scripts/
├── run_pipeline_debug.py    # Script visual de debug sin UI (dibuja bboxes, keypoints, zonas)
└── draw_zone_helper.py      # Herramienta temporal para dibujar zonas por click

tests/
├── test_state_machine.py    # Tests unitarios de transiciones de estado
├── test_presence.py         # Tests unitarios de dwell time
└── test_staff.py            # Tests unitarios de detección heurística de staff
```

---

## 8. Flujo funcional de este módulo (Módulo 2)

1. **Cargar video limpio + mapeo de frames** → `pipeline.run(video_path)`
   abre un archivo `.mp4` de `data/processed/` y carga el `.json` asociado
   (que contiene el `frame_mapping` del Módulo 1 — dónde fue cada frame en
   el video original).

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

6. **Traducción de timestamps** → `translate_to_original_timestamp()` usa el
   `frame_mapping` del Módulo 1 para convertir el timestamp relativo al video
   limpio al timestamp absoluto en el video original de 12 horas. Esto es
   crítico para ubicar eventos en la timeline original.

7. **Publicación de eventos** → `event_publisher.publish(event)` emite cada
   evento (`InteractionEvent`) según el modo configurado:
   - `"file"`: guarda JSON local en `data/events/` (respaldo persistente).
   - `"stdout"`: imprime en consola (para debug).
   - `"websocket"`: preparado para transporte final con Team 3 (aún no
     implementado, placeholder de contrato).

---

## 8.5. Nuevos tipos de evento (Módulo 2 — Extensión)

### PositionSample

Cada frame, por cada persona trackeada, se genera un `PositionSample` con la mejor
estimación disponible de **dónde toca el suelo** (coordenadas de píxel del frame de
cámara, no metros reales del piso de la tienda). Dos fuentes posibles:

- **`ankle_keypoint`** (verde en debug): usa los tobillos COCO si la pose fue
  detectada con confianza suficiente. Más preciso pero no siempre disponible.
- **`bbox_bottom_center`** (naranja en debug): centro inferior del bounding box.
  Respaldo cuando la pose no se detectó o los tobillos no superan el umbral.

`PositionSample` alimenta el futuro heatmap de circulación (Módulo 4). Las
coordenadas son en píxeles del frame de cámara, no en metros reales del piso —
convertir a coordenadas reales requeriría calibración de cámara por instalación,
fuera de alcance de este MVP.

### DwellRecord

Mide **tiempo de permanencia** frente a una zona de producto (diferencia explícita
con `InteractionEvent`: dwell time mide presencia, no interacción física con el
producto). Se genera un `DwellRecord` por cada vez que una persona **sale** de una
zona product, incluyendo `entry_timestamp`, `exit_timestamp` y `duration_sec`.

Zonas `zone_type="staff"` se ignoran para dwell time — no tiene sentido medir
"cuánto tiempo pasó un empleado frente a un producto" con este mecanismo.

### Detección heurística de empleados

El sistema marca como empleado a cualquier persona que haya estado dentro de una
zona con `zone_type="staff"` en alguna parte del video. El marcado es **"sticky"**
por sesión: una vez marcado como empleado, se queda así el resto del video (una
persona no dejaría de ser empleado por moverse por la tienda). Es puramente
geométrica (¿está el punto de pies dentro del polígono staff?), no reconocimiento
de personas — no hay ningún dato biométrico involucrado.

---

## 9. Cómo correr (Módulo 2)

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

---

## 10. Qué contiene el `Event Object` (Módulo 2)

Un objeto `InteractionEvent` serializado a JSON se ve así:

```json
{
  "event_type": "interaction",
  "track_id": 42,
  "zone_id": "shelf_A1",
  "action": "taken",
  "timestamp": 125.4,
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_employee": false
}
```

- `event_type` (str, enum): discriminador del tipo de evento. Para interacciones
  siempre vale `"interaction"`. Permite a cualquier consumidor del archivo de
  eventos filtrar por tipo sin inferirlo por la presencia de campos.
- `track_id` (int): identificador efímero de la persona en esta sesión de
  video (reinicia en 0 para cada video, no es persistente entre sesiones).
- `zone_id` (str): nombre único de la zona de góndola donde ocurrió la
  interacción (ej: "shelf_A1", "shelf_B2"). Definido por el usuario en el
  editor manual de zonas.
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
- `is_employee` (bool): indica si la persona que generó el evento fue
  clasificada como empleado (por su paso por una zona `staff`). `false` por
  defecto.

Ejemplo de un archivo de log generado en `data/events/`. El nombre real del
archivo es `events_session_<timestamp>.jsonl` y el formato es **JSON Lines
(.jsonl)**: una línea JSON por evento, sin corchetes de array ni comas entre
líneas. Las líneas pueden mezclar los tres tipos de evento (`interaction`,
`position` y `dwell`):

```jsonl
{"event_type": "interaction", "track_id": 1, "zone_id": "shelf_A1", "action": "taken", "timestamp": 12.5, "event_id": "...", "is_employee": false}
{"event_type": "position", "track_id": 1, "frame_index": 312, "timestamp": 12.6, "x": 520.0, "y": 340.0, "source": "ankle_keypoint", "is_employee": false, "event_id": "..."}
{"event_type": "interaction", "track_id": 2, "zone_id": "shelf_A1", "action": "taken", "timestamp": 15.3, "event_id": "...", "is_employee": false}
{"event_type": "interaction", "track_id": 3, "zone_id": "shelf_B2", "action": "taken", "timestamp": 18.7, "event_id": "...", "is_employee": false}
{"event_type": "dwell", "track_id": 3, "zone_id": "shelf_B2", "entry_timestamp": 17.9, "exit_timestamp": 21.2, "duration_sec": 3.3, "is_employee": false, "event_id": "..."}
```

---

## 11. Privacidad por diseño (Módulo 2)

- **Sin reconocimiento facial**: el sistema solo calcula bounding boxes de
  cuerpo completo y coordenadas numéricas de articulaciones (muñeca, codo,
  hombro). No entrena ni usa modelos de identidad facial.
- **Sin biometría**: no se guardan características biométricas (gait, altura,
  forma corporal específica de la persona).
- **Sin almacenamiento de imágenes**: los keypoints son coordenadas (x, y,
  confidence), no se guardan crops de imagen, no se archivan rostros ni
  siluetas.
- **Track IDs efímeros**: los identificadores de persona se generan dinámicamente
  durante la ejecución y se descartan al cerrar el video. No persisten entre
  sesiones ni se pueden usar para re-identificar a la misma persona en otro
  video (no hay base de datos de identidades).
- **Timestamps traceable al original**: los eventos se pueden ubicar
  exactamente en el video original, útil para auditoría y revisión manual en
  caso de disputa o error del sistema.

---

## 12. Sugerencias para continuar el desarrollo (Módulo 2)

### Corto plazo (siguiente iteración)

- **Integración del transporte final con Team 3**: Los eventos están listos para
  ser publicados. Actualmente se guardan localmente en `data/events/`. El paso
  siguiente es implementar `WebSocketEventPublisher` como una subclase de
  `EventPublisher` que envíe eventos en tiempo real a un servidor definido en
  `config.py`. El contrato de datos (`InteractionEvent`) ya es agnóstico del
  medio de transporte.

- **"ROI Auto-Suggest" automático ya está implementado**: el auto-suggest está
  construido en `app/core/roi_suggest.py`, usando **visión clásica** (detección
  de bordes con `cv2.Canny` + análisis de contornos), NO un modelo entrenado. Se
  activa opcionalmente con el flag `--auto-suggest` en `scripts/draw_zone_helper.py`,
  y sugiere hasta 3 candidatos rectangulares que el usuario puede aceptar (teclas
  `1`/`2`/`3`) y seguir ajustando, o ignorar y dibujar manualmente. La evaluación
  con datos reales mostró **utilidad mixta** (buen punto de partida, no siempre
  preciso), por eso queda como opcional, no como comportamiento por defecto. La
  definición manual de zonas mediante `ZoneManager` sigue siendo el camino
  principal.

### Mediano plazo

- **Distinción pick-up vs put-back**: actualmente todos los eventos se emiten
  como `action="taken"`. Para distinguir si la persona **extrajo** o **devolvió**
  el producto, se podría:
  - Detectar el movimiento de la mano (ascendente = tomar, descendente = devolver).
  - Usar una red clasificadora pequeña entrenada con anotaciones locales.
  - Combinar con información de carrito / zona de compra cercana.

- **Mejora de robustez en pose bajo oclusión**: si el estante ocluye parcialmente
  al brazo, puede que los keypoints fallen. Se podría:
  - Usar modelos de pose más robustos (YOLOv11-pose-large, MediaPipe).
  - Implementar predicción de keypoints ocultos usando interpolación temporal.

- **Multizona simultánea**: ya está soportado. El `state_machine` indexa su
  diccionario de estados por `(track_id, zone_id)`, de modo que cada combinación
  persona-zona tiene su propio estado independiente, sin ninguna restricción a
  una sola zona por persona. Una persona puede interactuar con múltiples zonas a
  la vez (ej: comparar precios en dos estantes) sin requerir cambios de lógica.

### Largo plazo

- **Dwell time + heatmaps**: usando `frame_mapping` y timestamps precisos,
  calcular cuánto tiempo pasa una persona en cada zona y generar mapas de calor
  de permanencia para identificar cuellos de botella.

- **Análisis de patrones**: con un histórico de eventos, detectar patrones
  anómalos (ej: misma persona, mismo producto, en segundos — posible hurto o
  problema de reabastecimiento).

- **Optimización edge con OpenVINO**: una vez validado, exportar modelos a
  formato OpenVINO para que el pipeline corra en hardware modesto sin dependencia
  de PyTorch en producción.

- **Mapa de calor de flujo (heatmap de circulación general)**: el `Event Object`
  de este módulo captura eventos discretos de interacción (`track_id`, `zone_id`,
  `action`, `timestamp`), no la trayectoria continua de cada persona a lo largo
  del video. Un heatmap de "dónde circula y dónde no la gente" (mencionado como
  funcionalidad esperada en el reto original) requeriría capturar y agregar la
  posición de cada persona en cada frame, un tipo de dato distinto que este
  módulo no produce. **Pendiente**: confirmar con el equipo completo qué módulo
  será responsable de capturar esa trayectoria continua, ya que por diseño actual
  del pipeline ningún módulo la está calculando.

- **Herramienta de dibujo visual de ROI**: Módulo 2 expone y consume el contrato
  `Zone` (`zone_id`, `name`, `polygon`) a través de `ZoneManager`
  (`app/core/zone.py`), incluyendo guardado/carga de polígonos en `data/zones/`,
  pero la interfaz donde el usuario dibuja el polígono con clicks sobre un frame
  es responsabilidad de la UI (Team 4). **Pendiente**: confirmar con Team 4 que el
  formato de salida de su herramienta de dibujo coincide exactamente con el
  esquema `Zone` definido en `app/core/schemas.py`.

## 13. Herramienta temporal para dibujar zonas (Módulo 2)

### Qué es y para qué sirve

`scripts/draw_zone_helper.py` es una herramienta temporal de línea de comandos
para definir manualmente las zonas de góndola (ROI) sobre el **primer frame** de
un video, mediante clicks, mientras Team 4 no tiene lista su herramienta visual
de dibujo en la UI. **No la reemplaza**: solo habilita temporalmente la capacidad
de dibujar zonas para poder probar el Módulo 2 mientras tanto.

### Comando de uso

```bash
uv run python -m scripts.draw_zone_helper --video "data/processed/<archivo>.mp4" --zone-id zone_1 --name "Estanteria Principal" --zone-type product
```

### Flag opcional `--auto-suggest`

Agregando `--auto-suggest` al comando anterior, la herramienta dibuja hasta **3
candidatos rectangulares en naranja** sobre el frame (antes de que empieces a
hacer click), generados con visión clásica (`cv2.Canny` + análisis de contornos)
en `app/core/roi_suggest.py`.

- **Cómo usarlo**: basta con añadir `--auto-suggest` al comando ya documentado.
- **Cómo aceptar una sugerencia**: pulsa las teclas `1`/`2`/`3` para cargar los
  puntos del candidato correspondiente. Después puedes seguir ajustándolo con
  clicks normales, o guardarlo directamente con `'s'`. Si prefieres no usar las
  sugerencias, ignóralas y dibuja manualmente como siempre (las teclas `1`/`2`/`3`
  solo actúan sobre los candidatos naranjas).
- **Sin el flag**, el comportamiento es exactamente el mismo de siempre: no se
  dibujan candidatos y todo funciona como hasta ahora, sin cambios.

### Comando para visualizar la zona dibujada

Una vez guardada la zona, corre el pipeline de debug sobre el mismo video para confirmar visualmente que quedó bien ajustada al estante:

```bash
uv run python -m scripts.run_pipeline_debug --video "data/processed/<archivo>.mp4"
```

Deberías ver el polígono verde dibujado sobre el frame, en el lugar donde hiciste los clics. Si hay más de un estante en el mismo video, repite el comando de dibujo (arriba) una vez por cada estante, usando un `--zone-id` distinto en cada ejecución (ej. `zone_1`, `zone_2`) — nunca intentes dibujar dos zonas en una sola ejecución conectando sus puntos entre sí, porque el polígono resultante se cruza a sí mismo y no representa correctamente ninguna de las dos zonas.

### Controles

- **Click izquierdo**: agrega un punto del polígono, en orden (cada click se
  dibuja sobre la imagen para dar feedback visual inmediato).
- **'s' (save)**: guarda la zona (requiere un mínimo de 3 puntos).
- **'r' (reset)**: borra los puntos capturados hasta ahora y permite empezar de
  nuevo, sin cerrar la ventana.
- **'q' (quit)**: cierra sin guardar (o después de guardar, para terminar).

### Regla importante de uso

Cada estante/zona física debe dibujarse en una ejecución **SEPARADA** del script,
con un `--zone-id` **distinto** cada vez (ej. `zone_1` para un estante, `zone_2`
para otro). **Nunca** se debe intentar dibujar dos zonas distintas en una sola
ejecución conectando sus puntos en un mismo polígono continuo: el resultado sería
una figura que se cruza a sí misma y no representa correctamente ninguna de las
dos zonas.

### Dónde queda guardado

Cada zona se guarda como `data/zones/<video_id>/<zone_id>.json`, donde
`<video_id>` es el nombre del archivo de video sin extensión. Así las zonas
quedan independientes por video y no se mezclan entre distintas
grabaciones/tiendas.

---

## 14. Limitaciones conocidas

- **Intercambios de track_id (ID switches)**: cuando dos personas se ocluyen
  mutuamente desde el ángulo de la cámara, ByteTrack puede intercambiar sus
  identificadores. No se resuelve con re-identificación porque eso requeriría
  análisis biométrico, fuera de alcance del proyecto por diseño.

- **Validación por revisión manual**: la validación de precisión/recall del sistema
  se hace por ahora mediante revisión manual del video comparado contra los eventos
  generados, no con una métrica automatizada — pendiente para una iteración futura
  si el tiempo lo permite.

- **Dwell records colgados**: si un `track_id` desaparece del video (se pierde el
  tracking) mientras una persona estaba dentro de una zona, su entrada queda "colgada"
  en el `DwellTracker` y nunca se cierra el registro. No hay lógica de expiración por
  ahora — no es crítico para la demo.

- **Posición de pies en píxeles**: las coordenadas de `PositionSample` son en píxeles
  del frame de cámara, no en metros reales del piso de la tienda. Convertir a
  coordenadas reales requeriría calibración de cámara por instalación, fuera de
  alcance de este MVP.

---

## 15. Flujo de trabajo completo — de cero a evaluación (Módulo 2)

Este flujo consolida en un solo lugar, en orden, todos los pasos necesarios para ir
de un video nuevo hasta la evaluación de precisión/recall. Es la secuencia que se
debe correr **por cada video nuevo que se quiera validar**: los pasos 2 y 5 son
específicos de cada video/zona, mientras que los pasos 1, 3, 4 y 6 se repiten igual
para cualquier video. No re-explica en detalle qué hace cada script (eso ya está en
las secciones 9, 10 y 13); es solo la "receta" rápida de referencia.

1. **Correr los tests** (siempre primero, para confirmar que el entorno está sano):

   ```bash
   uv run pytest tests/ -v
   ```

2. **Dibujar al menos una zona** sobre el video que se va a usar (repetir una vez por
   cada estante físico distinto, con `--zone-id` único cada vez; agregar
   `--auto-suggest` si se quiere partir de una sugerencia automática en vez de dibujar
   desde cero):

   ```bash
   uv run python -m scripts.draw_zone_helper --video "data/processed/<archivo>.mp4" --zone-id zone_1 --name "Estanteria Principal" --zone-type product
   ```

   Si se quiere marcar una zona de staff para la detección heurística de empleados:

   ```bash
   uv run python -m scripts.draw_zone_helper --video "data/processed/<archivo>.mp4" --zone-id staff_1 --name "Detras del mostrador" --zone-type staff
   ```

3. **Correr el pipeline visual de debug** sobre el mismo video (genera los eventos que
   se van a evaluar en el paso 5, y permite validar visualmente tracking, pose, zonas y
   estados):

   ```bash
   uv run python -m scripts.run_pipeline_debug --video "data/processed/<archivo>.mp4"
   ```

4. **Ubicar el archivo de eventos generado** (el nombre incluye un timestamp de sesión,
   no es fijo):

   ```bash
   dir data\events        
   ```

5. **Preparar un ground truth anotado a mano** viendo el mismo video (copiar el template
   y completar `timestamp,zone_id,track_id,action` por cada interacción real observada;
   `track_id` puede dejarse vacío, `action` puede dejarse vacío y cae a `"taken"` por
   defecto):

   ```bash
   copy data\eval\ground_truth_template.csv data\eval\mi_video_ground_truth.csv
   ```

6. **Evaluar precision/recall/F1** del sistema contra ese ground truth:

   ```bash
   uv run python -m scripts.evaluate_events --ground-truth data/eval/mi_video_ground_truth.csv --events "data/events/<archivo_generado_en_paso_4>.jsonl" --output-csv data/eval/reporte_auditoria.csv
   ```