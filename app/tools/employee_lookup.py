from langchain_core.tools import tool

from app.schemas.tool_schemas import EmployeeLookupInput


@tool(args_schema=EmployeeLookupInput)
def employee_lookup(employee_id: str) -> dict:
    """Retrieve enterprise employee account and MFA information."""

    employees = {
        "E1001": {
            "employee_id": "E1001",
            "name": "Demo Employee",
            "account_status": "active",
            "department": "Operations",
            "mfa_status": "device_changed",
        }
    }

    return employees.get(
        employee_id,
        {
            "employee_id": employee_id,
            "account_status": "not_found",
        },
    )