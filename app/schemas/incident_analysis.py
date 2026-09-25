from typing import Literal

from pydantic import BaseModel, Field


class IncidentAnalysis(BaseModel):
    incident_type: Literal[
        "vpn_access",
        "authentication",
        "general_it",
    ]

    affected_service: Literal[
        "vpn",
        "authentication",
        "general_it",
    ]

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    recommended_investigation: list[str]