from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.tools import tool

from app.schemas.tool_schemas import RemediationInput


@tool(args_schema=RemediationInput)
def execute_remediation(
    employee_id: str,
    action: str,
) -> dict:
    """
    Execute an approved remediation action.

    This project uses a safe simulated enterprise action
    rather than modifying a real production account.
    """

    operation_id = f"REM-{uuid4().hex[:8].upper()}"

    return {
        "operation_id": operation_id,
        "employee_id": employee_id,
        "action": action,
        "status": "success",
        "new_mfa_status": "re_registration_required",
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }