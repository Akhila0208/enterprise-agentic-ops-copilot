import pytest
from fastapi.testclient import TestClient

from app.api import server as server_module
from app.graph import workflow as workflow_module
from app.schemas.incident_analysis import IncidentAnalysis


client = TestClient(server_module.app)


def fake_bedrock_classifier(
    user_request: str,
) -> IncidentAnalysis:
    """
    Deterministic Bedrock replacement for automated tests.

    Prevents tests from calling live AWS services.
    """

    return IncidentAnalysis(
        incident_type="vpn_access",
        affected_service="vpn",
        confidence=0.95,
        recommended_investigation=[
            "Check VPN service availability.",
            "Verify employee MFA device state.",
        ],
    )


@pytest.fixture(autouse=True)
def prepare_test_environment(
    monkeypatch,
):
    """
    Reset API state and replace live Bedrock calls
    with deterministic local behavior.
    """

    server_module.known_workflows.clear()

    monkeypatch.delenv(
        "REMEDIATION_FAIL_FIRST_ATTEMPT",
        raising=False,
    )

    # Mock Bedrock for /incidents/analyze
    monkeypatch.setattr(
        server_module,
        "classify_incident_with_bedrock",
        fake_bedrock_classifier,
    )

    # Mock Bedrock inside the actual LangGraph workflow
    monkeypatch.setattr(
        workflow_module,
        "classify_incident_with_bedrock",
        fake_bedrock_classifier,
    )

    # Prevent unit tests from writing audit logs
    monkeypatch.setattr(
        workflow_module,
        "write_audit_event",
        lambda *args, **kwargs: None,
    )

    yield

    server_module.known_workflows.clear()


# =========================================================
# HEALTH ENDPOINT
# =========================================================

def test_health_endpoint():
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"

    assert (
        body["service"]
        == "enterprise-agentic-ops-copilot"
    )


# =========================================================
# REQUEST VALIDATION
# =========================================================

def test_incident_validation_rejects_short_request():
    response = client.post(
        "/incidents/analyze",
        json={
            "employee_id": "E1001",
            "request": "VPN",
        },
    )

    assert response.status_code == 422


# =========================================================
# BEDROCK ANALYSIS ENDPOINT
# =========================================================

def test_incident_analysis_endpoint():
    response = client.post(
        "/incidents/analyze",
        json={
            "employee_id": "E1001",
            "request": (
                "Employee cannot connect "
                "to the corporate VPN."
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["employee_id"] == "E1001"

    assert (
        body["incident_type"]
        == "vpn_access"
    )

    assert (
        body["affected_service"]
        == "vpn"
    )

    assert body["confidence"] == 0.95

    assert (
        body["model"]
        == "amazon-nova-pro"
    )

    assert len(
        body["recommended_investigation"]
    ) == 2


# =========================================================
# UNKNOWN WORKFLOW
# =========================================================

def test_unknown_workflow_returns_404():
    response = client.get(
        "/workflows/not-a-real-workflow"
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "Workflow not found."
    )


# =========================================================
# FULL HUMAN-IN-THE-LOOP WORKFLOW
# =========================================================

def test_workflow_pause_and_resume():
    # -----------------------------------------------------
    # Start workflow
    # -----------------------------------------------------

    start_response = client.post(
        "/workflows/start",
        json={
            "employee_id": "E1001",
            "request": (
                "An employee cannot connect "
                "to the corporate VPN after "
                "changing their phone."
            ),
        },
    )

    assert start_response.status_code == 200

    start_body = start_response.json()

    workflow_id = start_body[
        "workflow_id"
    ]

    assert workflow_id

    assert (
        start_body["status"]
        == "awaiting_approval"
    )

    assert (
        start_body["approval_required"]
        is True
    )

    assert (
        start_body["incident_type"]
        == "vpn_access"
    )

    assert (
        start_body["affected_service"]
        == "vpn"
    )

    assert (
        start_body["risk_level"]
        == "medium"
    )

    assert (
        start_body["execution_status"]
        is None
    )

    # -----------------------------------------------------
    # Verify paused workflow can be retrieved
    # -----------------------------------------------------

    status_response = client.get(
        f"/workflows/{workflow_id}"
    )

    assert status_response.status_code == 200

    status_body = status_response.json()

    assert (
        status_body["status"]
        == "awaiting_approval"
    )

    assert (
        status_body["approval_required"]
        is True
    )

    # -----------------------------------------------------
    # Human approves remediation
    # -----------------------------------------------------

    decision_response = client.post(
        (
            f"/workflows/"
            f"{workflow_id}"
            f"/decision"
        ),
        json={
            "approved": True
        },
    )

    assert decision_response.status_code == 200

    completed = (
        decision_response.json()
    )

    # -----------------------------------------------------
    # Verify same workflow resumed and completed
    # -----------------------------------------------------

    assert (
        completed["workflow_id"]
        == workflow_id
    )

    assert (
        completed["status"]
        == "completed"
    )

    assert (
        completed["approval_required"]
        is False
    )

    assert (
        completed["execution_status"]
        == "success"
    )

    assert (
        completed["verification_status"]
        == "remediation_verified"
    )

    assert completed["operation_id"]

    assert completed["final_response"]

    assert (
        "vpn_access"
        in completed["final_response"]
    )