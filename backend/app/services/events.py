from datetime import datetime


class EventBus:
    version: int = 0
    last_event: str = "boot"
    updated_at: str = datetime.utcnow().isoformat()

    @classmethod
    def bump(cls, event: str) -> None:
        cls.version += 1
        cls.last_event = event
        cls.updated_at = datetime.utcnow().isoformat()
