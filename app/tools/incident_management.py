from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.tools import tool


@tool
def create_incident(
    employee_id: str,
    incident_type: str,
    reason: str,
) -> dict:
    """Create a simulated enterprise incident for manual escalation."""

    incident_id = f"INC-{uuid4().hex[:8].upper()}"

    return {
        "incident_id": incident_id,
        "employee_id": employee_id,
        "incident_type": incident_type,
        "reason": reason,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }