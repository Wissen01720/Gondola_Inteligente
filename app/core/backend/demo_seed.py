"""
Sembrado de datos de demostración para el dashboard (Team 3/4).

El pipeline de detección (tabs 3/4, aún no integradas a la UI) es la fuente
real de eventos: mientras no corre, `EventStore` está vacío y el dashboard
no tiene nada que graficar. Esta función llena esa sesión vacía con
telemetría sintética pero *estructuralmente idéntica* a la real (mismos
modelos Pydantic, mismas reglas del `state_machine`: taken/returned
alternan por track dentro de cada zona) para que el dashboard sea
demostrable de inmediato — y deje de usarse en cuanto haya eventos reales.
"""
import random

from app.core.backend.event_store import EventStore
from app.core.detection.schemas import DwellRecord, InteractionEvent, Zone


def has_data(store: EventStore) -> bool:
    """True si la sesión ya tiene al menos un evento real registrado."""
    return store.count_events() > 0


def seed_demo_session(store: EventStore, zones: list[Zone], seed: int = 7) -> int:
    """
    Genera eventos `taken`/`returned` + `DwellRecord` para las zonas de tipo
    'product' de `zones`, respetando la alternancia taken->returned->taken
    por track (la misma regla que aplica `state_machine.py`).

    Devuelve la cantidad de InteractionEvent insertados.
    """
    rng = random.Random(seed)
    product_zones = [z for z in zones if z.zone_type == "product"]
    if not product_zones:
        return 0

    next_track_id = 100
    inserted = 0
    t = 4.0

    for zone in product_zones:
        visits = rng.randint(6, 11)
        for _ in range(visits):
            track_id = next_track_id
            next_track_id += 1
            is_employee = rng.random() < 0.08

            entry = t
            dwell = round(rng.uniform(2.0, 9.0), 1)
            exit_ts = entry + dwell

            store.insert_event(InteractionEvent(
                track_id=track_id, zone_id=zone.zone_id, action="taken",
                timestamp=round(exit_ts, 2), is_employee=is_employee,
            ))
            store.insert_dwell_record(DwellRecord(
                track_id=track_id, zone_id=zone.zone_id,
                entry_timestamp=round(entry, 2), exit_timestamp=round(exit_ts, 2),
                duration_sec=dwell, is_employee=is_employee,
            ))
            inserted += 1

            # ~30% de las visitas devuelven el producto poco después (misma
            # persona, mismo track, alternando la acción).
            if rng.random() < 0.3:
                return_ts = exit_ts + round(rng.uniform(1.0, 4.0), 1)
                store.insert_event(InteractionEvent(
                    track_id=track_id, zone_id=zone.zone_id, action="returned",
                    timestamp=round(return_ts, 2), is_employee=is_employee,
                ))
                inserted += 1
                t = return_ts
            else:
                t = exit_ts

            t += rng.uniform(1.5, 6.0)

    return inserted
