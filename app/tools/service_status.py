from langchain_core.tools import tool

from app.schemas.tool_schemas import ServiceStatusInput


@tool(args_schema=ServiceStatusInput)
def service_status(service_name: str) -> dict:
    """Check the operational status of an enterprise service."""

    services = {
        "vpn": {
            "service": "vpn",
            "status": "operational",
            "latency_ms": 42,
        },
        "authentication": {
            "service": "authentication",
            "status": "operational",
            "latency_ms": 31,
        },
    }

    return services.get(
        service_name.lower(),
        {
            "service": service_name,
            "status": "unknown",
        },
    )