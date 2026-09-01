"""
Publicador de eventos de interacción.

Define el punto de extensión para enviar eventos al exterior (Team 3).
Por ahora soporta salida local a consola (stdout) y escritura en archivo local (.jsonl).
"""
from abc import ABC, abstractmethod
import json
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel
from app.utils.config import EVENT_PUBLISHER_MODE, EVENTS_LOCAL_LOG_PATH

class EventPublisher(ABC):
    """Interfaz base para el publicador de eventos."""

    @abstractmethod
    def publish(self, event: BaseModel) -> None:
        """Publica un evento serializable a Pydantic."""
        pass


class LocalEventPublisher(EventPublisher):
    """
    Publicador local que escribe los eventos en consola o archivo según la configuración.
    
    Para extender el pipeline e integrar la comunicación con Team 3 en el futuro,
    se debe crear otra subclase (ej. WebSocketEventPublisher) implementando 'publish',
    sin alterar el resto de la lógica de detección.
    """

    def __init__(self, mode: str = EVENT_PUBLISHER_MODE, log_dir: str = EVENTS_LOCAL_LOG_PATH):
        self.mode = mode
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre único para la sesión actual
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"events_session_{timestamp_str}.jsonl"

    def publish(self, event: BaseModel) -> None:
        """Publica el evento serializado a stdout o archivo local jsonl."""
        event_data = event.model_dump()
        # Asegurarse de que el event_id sea un string y no falte
        event_str = json.dumps(event_data)

        if self.mode == "stdout":
            print(f"[EVENT] {event_str}")
        elif self.mode == "file":
            # Escribir una nueva línea en el archivo de sesión
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(event_str + "\n")
        else:
            # Modo desconocido o placeholder (por ejemplo, websocket no implementado aún)
            print(f"[EVENT - {self.mode}] {event_str}")
