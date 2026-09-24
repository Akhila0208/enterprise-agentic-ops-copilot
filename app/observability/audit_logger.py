import json
from datetime import datetime, timezone
from pathlib import Path


LOG_FILE = Path("logs/audit_log.jsonl")


def write_audit_event(
    event_type: str,
    details: dict,
) -> None:
    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    event = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "event_type": event_type,
        "details": details,
    }

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(event)
            + "\n"
        )