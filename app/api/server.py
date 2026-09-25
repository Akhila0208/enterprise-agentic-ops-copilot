from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langgraph.types import Command

from app.api.models import (
    HealthResponse,
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    WorkflowDecisionRequest,
    WorkflowStartRequest,
    WorkflowStatusResponse,
)
from app.graph.workflow import build_workflow
from app.services.bedrock_classifier import (
    classify_incident_with_bedrock,
)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Enterprise Agentic Ops Copilot API",
    description=(
        "Enterprise Agentic AI API using Amazon Bedrock, "
        "Amazon Nova Pro, LangGraph, enterprise tools, "
        "human approval, remediation, retry, and verification."
    ),
    version="2.0.0",
)


# =========================================================
# LANGGRAPH WORKFLOW
# =========================================================

agent = build_workflow()

known_workflows: set[str] = set()


def workflow_config(
    workflow_id: str,
) -> dict:
    return {
        "configurable": {
            "thread_id": workflow_id
        }
    }


# =========================================================
# INTERRUPT EXTRACTION
# =========================================================

def get_interrupt_payload(
    workflow_id: str,
):
    config = workflow_config(
        workflow_id
    )

    snapshot = agent.get_state(
        config
    )

    for task in getattr(
        snapshot,
        "tasks",
        (),
    ):
        interrupts = getattr(
            task,
            "interrupts",
            (),
        )

        if interrupts:
            return interrupts[0].value

    return None


# =========================================================
# BUILD API STATUS RESPONSE
# =========================================================

def build_workflow_response(
    workflow_id: str,
) -> WorkflowStatusResponse:

    if workflow_id not in known_workflows:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found.",
        )

    config = workflow_config(
        workflow_id
    )

    snapshot = agent.get_state(
        config
    )

    state = snapshot.values or {}

    interrupt_payload = (
        get_interrupt_payload(
            workflow_id
        )
    )

    if interrupt_payload is not None:
        status = "awaiting_approval"

    elif state.get("final_response"):
        status = "completed"

    else:
        status = "running"

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        status=status,

        employee_id=state.get(
            "employee_id"
        ),

        incident_type=state.get(
            "incident_type"
        ),

        affected_service=state.get(
            "affected_service"
        ),

        classification_confidence=state.get(
            "classification_confidence"
        ),

        risk_level=state.get(
            "risk_level"
        ),

        approval_required=(
            interrupt_payload is not None
        ),

        approval_context=(
            interrupt_payload
            if isinstance(
                interrupt_payload,
                dict,
            )
            else None
        ),

        remediation_action=state.get(
            "remediation_action"
        ),

        execution_status=state.get(
            "execution_status"
        ),

        verification_status=state.get(
            "verification_status"
        ),

        operation_id=state.get(
            "operation_id"
        ),

        escalation_incident_id=state.get(
            "escalation_incident_id"
        ),

        final_response=state.get(
            "final_response"
        ),
    )


# =========================================================
# HEALTH
# =========================================================

@app.get(
    "/health",
    response_model=HealthResponse,
)
def health_check():
    return {
        "status": "healthy",
        "service": (
            "enterprise-agentic-ops-copilot"
        ),
    }


# =========================================================
# BEDROCK-ONLY ANALYSIS
# =========================================================

@app.post(
    "/incidents/analyze",
    response_model=IncidentAnalysisResponse,
)
def analyze_incident(
    payload: IncidentAnalysisRequest,
):
    try:
        analysis = (
            classify_incident_with_bedrock(
                payload.request
            )
        )

        return IncidentAnalysisResponse(
            employee_id=payload.employee_id,

            incident_type=(
                analysis.incident_type
            ),

            affected_service=(
                analysis.affected_service
            ),

            confidence=(
                analysis.confidence
            ),

            recommended_investigation=(
                analysis.recommended_investigation
            ),

            model="amazon-nova-pro",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Incident analysis failed. "
                f"{type(exc).__name__}"
            ),
        ) from exc


# =========================================================
# START FULL LANGGRAPH WORKFLOW
# =========================================================

@app.post(
    "/workflows/start",
    response_model=WorkflowStatusResponse,
)
def start_workflow(
    payload: WorkflowStartRequest,
):
    workflow_id = str(
        uuid4()
    )

    known_workflows.add(
        workflow_id
    )

    config = workflow_config(
        workflow_id
    )

    initial_state = {
        "user_request": payload.request,
        "employee_id": payload.employee_id,
        "evidence": [],
    }

    try:
        agent.invoke(
            initial_state,
            config=config,
        )

        return build_workflow_response(
            workflow_id
        )

    except Exception as exc:
        known_workflows.discard(
            workflow_id
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Workflow execution failed. "
                f"{type(exc).__name__}"
            ),
        ) from exc


# =========================================================
# WORKFLOW STATUS
# =========================================================

@app.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowStatusResponse,
)
def workflow_status(
    workflow_id: str,
):
    return build_workflow_response(
        workflow_id
    )


# =========================================================
# HUMAN APPROVAL / REJECTION
# =========================================================

@app.post(
    "/workflows/{workflow_id}/decision",
    response_model=WorkflowStatusResponse,
)
def workflow_decision(
    workflow_id: str,
    payload: WorkflowDecisionRequest,
):
    if workflow_id not in known_workflows:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found.",
        )

    interrupt_payload = (
        get_interrupt_payload(
            workflow_id
        )
    )

    if interrupt_payload is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Workflow is not currently "
                "waiting for human approval."
            ),
        )

    config = workflow_config(
        workflow_id
    )

    try:
        agent.invoke(
            Command(
                resume=payload.approved
            ),
            config=config,
        )

        return build_workflow_response(
            workflow_id
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Workflow resume failed. "
                f"{type(exc).__name__}"
            ),
        ) from exc