from fastapi import FastAPI, HTTPException

from app.api.models import (
    HealthResponse,
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
)
from app.services.bedrock_classifier import (
    classify_incident_with_bedrock,
)


app = FastAPI(
    title="Enterprise Agentic Ops Copilot API",
    description=(
        "REST API for enterprise IT incident reasoning "
        "using Amazon Bedrock and Amazon Nova Pro."
    ),
    version="1.0.0",
)


@app.get(
    "/health",
    response_model=HealthResponse,
)
def health_check():
    return {
        "status": "healthy",
        "service": "enterprise-agentic-ops-copilot",
    }


@app.post(
    "/incidents/analyze",
    response_model=IncidentAnalysisResponse,
)
def analyze_incident(
    payload: IncidentAnalysisRequest,
):
    try:
        analysis = classify_incident_with_bedrock(
            payload.request
        )

        return IncidentAnalysisResponse(
            employee_id=payload.employee_id,
            incident_type=analysis.incident_type,
            affected_service=analysis.affected_service,
            confidence=analysis.confidence,
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