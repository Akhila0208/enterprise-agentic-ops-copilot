from pydantic import BaseModel, Field


class EmployeeLookupInput(BaseModel):
    employee_id: str = Field(
        description=(
            "Unique employee identifier used to "
            "retrieve account information."
        )
    )


class ServiceStatusInput(BaseModel):
    service_name: str = Field(
        description=(
            "Enterprise service to check, "
            "such as vpn or authentication."
        )
    )


class RemediationInput(BaseModel):
    employee_id: str = Field(
        description="Employee receiving the remediation."
    )

    action: str = Field(
        description="Approved remediation action to execute."
    )

    attempt_number: int = Field(
        default=1,
        ge=1,
        description="Current execution attempt number.",
    )