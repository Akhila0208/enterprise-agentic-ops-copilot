import os
from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.tools import tool

from app.schemas.tool_schemas import RemediationInput


@tool(args_schema=RemediationInput)
def execute_remediation(
    employee_id: str,
    action: str,
    attempt_number: int = 1,
) -> dict:
    """
    Execute an approved remediation action.

    Supports controlled fault injection so retry behavior
    can be tested without calling a real production system.
    """

    operation_id = f"REM-{uuid4().hex[:8].upper()}"

    fail_first_attempt = (
        os.getenv(
            "REMEDIATION_FAIL_FIRST_ATTEMPT",
            "false",
        ).lower()
        == "true"
    )

    if fail_first_attempt and attempt_number == 1:
        return {
            "operation_id": operation_id,
            "employee_id": employee_id,
            "action": action,
            "status": "failed",
            "error": "Simulated transient remediation API failure",
            "attempt_number": attempt_number,
            "executed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    return {
        "operation_id": operation_id,
        "employee_id": employee_id,
        "action": action,
        "status": "success",
        "new_mfa_status": "re_registration_required",
        "attempt_number": attempt_number,
        "executed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }