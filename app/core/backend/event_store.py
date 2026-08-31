"""
Almacén local de eventos (Team 3) — STUB.

Suscribe al bus in-process (InProcessPublisher, task 5) y persiste tanto
`InteractionEvent` como `PositionSample` en una base SQLite local.

Contrato mínimo implementado para el MVP:
- tablas `events` y `position_samples`
- inserción desde el bus (payload como dict) o directa con los modelos
- TODO(Team 3): consultas agregadas, particionado por sesión/cámara,
  índices para rangos de tiempo, limpieza de datos antiguos, etc.
"""
from pathlib import Path
from typing import Optional
import sqlite3

from app.core.detection.schemas import InteractionEvent, PositionSample
from app.core.detection.event_publisher import InProcessPublisher
from app.utils.config import EVENT_STORE_DB_PATH


class EventStore:
    """Persistencia local SQLite de eventos y muestras de posición."""

    def __init__(self, db_path: str = EVENT_STORE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Crea las tablas si no existen."""
        # TODO(Team 3): añadir índices sobre (timestamp, zone_id / track_id)
        # cuando las consultas del dashboard los requieran.
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id   TEXT PRIMARY KEY,
                track_id   INTEGER NOT NULL,
                zone_id    TEXT    NOT NULL,
                action     TEXT    NOT NULL,
                timestamp  REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS position_samples (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id    INTEGER NOT NULL,
                frame_index INTEGER NOT NULL,
                timestamp   REAL    NOT NULL,
                foot_x      REAL    NOT NULL,
                foot_y      REAL    NOT NULL,
                camera_id   TEXT    NOT NULL
            );
            """
        )
        self._conn.commit()

    # ----------------------------------------------------------- inserción --
    def insert_event(self, event: InteractionEvent) -> None:
        """Guarda un evento de interacción."""
        self._conn.execute(
            "INSERT OR REPLACE INTO events (event_id, track_id, zone_id, action, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (event.event_id, event.track_id, event.zone_id, event.action, event.timestamp),
        )
        self._conn.commit()

    def insert_position_sample(self, sample: PositionSample) -> None:
        """Guarda una muestra de posición."""
        foot_x, foot_y = sample.foot_position
        self._conn.execute(
            "INSERT INTO position_samples (track_id, frame_index, timestamp, foot_x, foot_y, camera_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sample.track_id, sample.frame_index, sample.original_timestamp_sec,
             foot_x, foot_y, sample.camera_id),
        )
        self._conn.commit()

    # ---------------------------------------------------------- bus sink ----
    def on_bus_message(self, payload: dict) -> None:
        """
        Sink del bus in-process: despacha el dict recibido al tipo correcto.

        TODO(Team 3): si el volumen de PositionSample lo amerita, conviene
        agrupar inserciones en lotes (executemany) en vez de commit por mensaje.
        """
        if "foot_position" in payload:
            self.insert_position_sample(PositionSample(**payload))
        elif "action" in payload and "event_id" in payload:
            self.insert_event(InteractionEvent(**payload))
        else:
            # TODO(Team 3): loguear payloads desconocidos en vez de ignorarlos.
            pass

    def count_events(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def count_position_samples(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM position_samples").fetchone()[0]

    # TODO(Team 3): query_position_samples(rango_tiempo, zone/camera filter),
    # query_events(zone_id, action), stats por sesión.

    def close(self) -> None:
        self._conn.close()

    def __del__(self):
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001 - conexión ya cerrada o en teardown
            pass


def connect_store_to_publisher(store: EventStore, publisher: InProcessPublisher) -> None:
    """
    Suscribe el almacén al bus in-process (task 5).

    Al conectar el signal de Qt, todo lo que publique el pipeline
    (InteractionEvent + PositionSample) se persiste automáticamente,
    sin transporte de red.
    """
    publisher.event_emitted.connect(store.on_bus_message)
