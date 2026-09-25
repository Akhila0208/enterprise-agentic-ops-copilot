from typing import Any, Literal

from pydantic import BaseModel, Field


# =========================================================
# BASIC BEDROCK ANALYSIS API
# =========================================================

class IncidentAnalysisRequest(BaseModel):
    employee_id: str = Field(
        default="E1001",
        description="Employee associated with the incident.",
    )

    request: str = Field(
        min_length=5,
        description="Natural-language IT incident description.",
    )


class IncidentAnalysisResponse(BaseModel):
    employee_id: str
    incident_type: str
    affected_service: str
    confidence: float
    recommended_investigation: list[str]
    model: str


class HealthResponse(BaseModel):
    status: str
    service: str


# =========================================================
# FULL AGENT WORKFLOW API
# =========================================================

class WorkflowStartRequest(BaseModel):
    employee_id: str = Field(
        default="E1001",
        description="Employee associated with the incident.",
    )

    request: str = Field(
        min_length=5,
        description="Incident to process through the agent workflow.",
    )


class WorkflowDecisionRequest(BaseModel):
    approved: bool = Field(
        description=(
            "Human approval decision for the proposed remediation."
        )
    )


class WorkflowStatusResponse(BaseModel):
    workflow_id: str

    status: Literal[
        "running",
        "awaiting_approval",
        "completed",
    ]

    employee_id: str | None = None

    incident_type: str | None = None
    affected_service: str | None = None
    classification_confidence: float | None = None

    risk_level: str | None = None

    approval_required: bool = False
    approval_context: dict[str, Any] | None = None

    remediation_action: str | None = None

    execution_status: str | None = None
    verification_status: str | None = None

    operation_id: str | None = None
    escalation_incident_id: str | None = None

    final_response: str | None = None