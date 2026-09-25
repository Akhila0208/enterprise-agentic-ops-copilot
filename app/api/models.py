from pydantic import BaseModel, Field


class IncidentAnalysisRequest(BaseModel):
    employee_id: str = Field(
        default="E1001",
        description="Employee identifier associated with the incident.",
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