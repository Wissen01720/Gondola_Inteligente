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

from app.core.detection.schemas import InteractionEvent, PositionSample, DwellRecord
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
                event_id     TEXT PRIMARY KEY,
                track_id     INTEGER NOT NULL,
                zone_id      TEXT    NOT NULL,
                action       TEXT    NOT NULL,
                timestamp    REAL    NOT NULL,
                is_employee  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS position_samples (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id     INTEGER NOT NULL,
                frame_index  INTEGER NOT NULL,
                timestamp    REAL    NOT NULL,
                foot_x       REAL    NOT NULL,
                foot_y       REAL    NOT NULL,
                camera_id    TEXT    NOT NULL,
                is_employee  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS dwell_records (
                event_id         TEXT PRIMARY KEY,
                track_id         INTEGER NOT NULL,
                zone_id          TEXT    NOT NULL,
                entry_timestamp  REAL    NOT NULL,
                exit_timestamp   REAL    NOT NULL,
                duration_sec     REAL    NOT NULL,
                is_employee      INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self._conn.commit()

    # ----------------------------------------------------------- inserción --
    def insert_event(self, event: InteractionEvent) -> None:
        """Guarda un evento de interacción."""
        self._conn.execute(
            "INSERT OR REPLACE INTO events (event_id, track_id, zone_id, action, timestamp, is_employee) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event.event_id, event.track_id, event.zone_id, event.action, event.timestamp, int(event.is_employee)),
        )
        self._conn.commit()

    def insert_position_sample(self, sample: PositionSample) -> None:
        """Guarda una muestra de posición."""
        foot_x, foot_y = sample.foot_position
        self._conn.execute(
            "INSERT INTO position_samples (track_id, frame_index, timestamp, foot_x, foot_y, camera_id, is_employee) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sample.track_id, sample.frame_index, sample.original_timestamp_sec,
             foot_x, foot_y, sample.camera_id, int(sample.is_employee)),
        )
        self._conn.commit()

    def insert_dwell_record(self, record: DwellRecord) -> None:
        """Guarda un registro de tiempo de permanencia (dwell time) en una zona de producto."""
        self._conn.execute(
            "INSERT OR REPLACE INTO dwell_records "
            "(event_id, track_id, zone_id, entry_timestamp, exit_timestamp, duration_sec, is_employee) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.event_id, record.track_id, record.zone_id, record.entry_timestamp,
             record.exit_timestamp, record.duration_sec, int(record.is_employee)),
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
        elif "duration_sec" in payload:
            self.insert_dwell_record(DwellRecord(**payload))
        elif "action" in payload and "event_id" in payload:
            self.insert_event(InteractionEvent(**payload))
        else:
            # TODO(Team 3): loguear payloads desconocidos en vez de ignorarlos.
            pass

    def count_events(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def count_position_samples(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM position_samples").fetchone()[0]

    def count_dwell_records(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM dwell_records").fetchone()[0]

    # ------------------------------------------------- consultas agregadas --
    # Usadas por el dashboard (app/ui/dashboard_tab.py). Todas devuelven
    # tipos nativos de Python (dict/list), listos para pintar en la UI sin
    # que el widget tenga que saber nada de SQL.

    def get_summary(self) -> dict:
        """Totales generales de la sesión: base de los KPIs del dashboard."""
        taken = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE action = 'taken'"
        ).fetchone()[0]
        returned = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE action = 'returned'"
        ).fetchone()[0]
        total_events = self.count_events()
        employee_events = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE is_employee = 1"
        ).fetchone()[0]
        avg_dwell = self._conn.execute(
            "SELECT AVG(duration_sec) FROM dwell_records"
        ).fetchone()[0]
        active_zones = self._conn.execute(
            "SELECT COUNT(DISTINCT zone_id) FROM events"
        ).fetchone()[0]

        return {
            "total_events": total_events,
            "taken": taken,
            "returned": returned,
            "take_rate": round(taken / total_events, 4) if total_events else 0.0,
            "avg_dwell_sec": round(avg_dwell, 2) if avg_dwell is not None else 0.0,
            "employee_events": employee_events,
            "employee_share": round(employee_events / total_events, 4) if total_events else 0.0,
            "active_zones": active_zones,
        }

    def get_zone_breakdown(self) -> list[dict]:
        """Conteo de `taken`/`returned` y dwell promedio, agrupado por zona."""
        rows = self._conn.execute(
            """
            SELECT
                zone_id,
                SUM(CASE WHEN action = 'taken' THEN 1 ELSE 0 END)    AS taken,
                SUM(CASE WHEN action = 'returned' THEN 1 ELSE 0 END) AS returned
            FROM events
            GROUP BY zone_id
            """
        ).fetchall()
        dwell_by_zone = {
            r["zone_id"]: r["avg_dwell"]
            for r in self._conn.execute(
                "SELECT zone_id, AVG(duration_sec) AS avg_dwell FROM dwell_records GROUP BY zone_id"
            ).fetchall()
        }
        return [
            {
                "zone_id": r["zone_id"],
                "taken": r["taken"],
                "returned": r["returned"],
                "avg_dwell_sec": round(dwell_by_zone.get(r["zone_id"], 0.0) or 0.0, 2),
            }
            for r in rows
        ]

    def get_timeline(self, bucket_sec: float = 30.0) -> list[dict]:
        """
        Serie temporal de `taken`/`returned`, agrupada en buckets de
        `bucket_sec` segundos desde el primer evento de la sesión.
        """
        rows = self._conn.execute("SELECT action, timestamp FROM events ORDER BY timestamp").fetchall()
        if not rows:
            return []

        t0 = rows[0]["timestamp"]
        buckets: dict[int, dict] = {}
        for r in rows:
            idx = int((r["timestamp"] - t0) // bucket_sec)
            bucket = buckets.setdefault(idx, {"taken": 0, "returned": 0})
            if r["action"] in ("taken", "returned"):
                bucket[r["action"]] += 1

        return [
            {
                "bucket_start_sec": t0 + idx * bucket_sec,
                "taken": buckets[idx]["taken"],
                "returned": buckets[idx]["returned"],
            }
            for idx in range(max(buckets) + 1)
        ]

    def get_recent_events(self, limit: int = 15) -> list[dict]:
        """Últimos eventos registrados, más recientes primero (para el feed en vivo)."""
        rows = self._conn.execute(
            "SELECT event_id, track_id, zone_id, action, timestamp, is_employee "
            "FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_position_samples(self, limit: int = 6000, exclude_employees: bool = True) -> list[PositionSample]:
        """
        Muestras de posición (pie de cada persona por frame), reconstruidas
        como `PositionSample` — es el insumo de `build_density_grid`
        (`app/core/backend/heatmap.py`) para el mapa de calor del dashboard.

        `exclude_employees=True` (default) descarta las muestras marcadas
        `is_employee` — el heatmap busca mostrar circulación e interés de
        **clientes**; un empleado parado horas en el mismo punto (caja,
        mostrador, reponiendo una góndola) generaría ahí una mancha de
        calor artificial que no refleja tráfico de cliente. La zona de
        personal (ROI de `StaffZoneTracker`) ya se dibuja aparte sobre el
        heatmap para dar contexto — no debería, además, sumar densidad
        como si fuera una zona más de circulación.

        `limit` acota cuántas muestras recientes se traen: una sesión larga
        puede acumular decenas de miles de filas y el heatmap no necesita
        más que unos miles de puntos para verse denso.
        """
        where = "WHERE is_employee = 0" if exclude_employees else ""
        rows = self._conn.execute(
            f"SELECT track_id, frame_index, timestamp, foot_x, foot_y, camera_id, is_employee "
            f"FROM position_samples {where} ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            PositionSample(
                track_id=r["track_id"],
                frame_index=r["frame_index"],
                original_timestamp_sec=r["timestamp"],
                foot_position=(r["foot_x"], r["foot_y"]),
                camera_id=r["camera_id"],
                is_employee=bool(r["is_employee"]),
            )
            for r in rows
        ]

    # TODO(Team 3): filtro por rango de tiempo/zona en get_position_samples;
    # stats por sesión/video_id cuando `events` gane esa columna.

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
