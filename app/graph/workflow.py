from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.observability.audit_logger import write_audit_event
from app.tools.employee_lookup import employee_lookup
from app.tools.incident_management import create_incident
from app.tools.remediation import execute_remediation
from app.tools.service_status import service_status


class AgentState(TypedDict, total=False):
    # Request
    user_request: str
    employee_id: str

    # Classification / investigation
    incident_type: str
    evidence: list[str]

    # Risk
    risk_level: str
    requires_approval: bool

    # Remediation
    remediation_action: str
    execution_status: str

    # Resilience
    attempt_count: int
    max_attempts: int
    last_error: str

    # Execution result
    operation_id: str
    remediation_result: dict

    # Escalation
    escalated: bool
    escalation_incident_id: str

    # Final verification
    verification_status: str
    final_response: str


# =========================================================
# 1. CLASSIFY REQUEST
# =========================================================

def classify_request(state: AgentState):
    request = state["user_request"].lower()

    if "vpn" in request:
        incident_type = "vpn_access"

    elif "password" in request or "login" in request:
        incident_type = "authentication"

    else:
        incident_type = "general_it"

    write_audit_event(
        "request_classified",
        {
            "employee_id": state.get("employee_id"),
            "user_request": state["user_request"],
            "incident_type": incident_type,
        },
    )

    return {
        "incident_type": incident_type
    }


# =========================================================
# 2. INVESTIGATE WITH ENTERPRISE TOOLS
# =========================================================

def investigate(state: AgentState):
    incident_type = state["incident_type"]
    employee_id = state.get("employee_id", "E1001")

    if incident_type == "vpn_access":
        service_result = service_status.invoke(
            {
                "service_name": "vpn"
            }
        )

    elif incident_type == "authentication":
        service_result = service_status.invoke(
            {
                "service_name": "authentication"
            }
        )

    else:
        service_result = {
            "service": "general_it",
            "status": "unknown",
        }

    employee_result = employee_lookup.invoke(
        {
            "employee_id": employee_id
        }
    )

    evidence = [
        f"Service checked: {service_result['service']}",
        f"Service status: {service_result['status']}",
        (
            "Employee account status: "
            f"{employee_result['account_status']}"
        ),
        (
            "Employee MFA status: "
            f"{employee_result.get('mfa_status', 'unknown')}"
        ),
    ]

    write_audit_event(
        "investigation_completed",
        {
            "employee_id": employee_id,
            "incident_type": incident_type,
            "service_result": service_result,
            "employee_result": employee_result,
            "evidence": evidence,
        },
    )

    return {
        "evidence": evidence
    }


# =========================================================
# 3. RISK ASSESSMENT
# =========================================================

def assess_risk(state: AgentState):
    evidence_text = " ".join(
        state["evidence"]
    ).lower()

    if "not_found" in evidence_text:
        risk_level = "high"
        requires_approval = True

    elif "device_changed" in evidence_text:
        risk_level = "medium"
        requires_approval = True

    else:
        risk_level = "low"
        requires_approval = False

    write_audit_event(
        "risk_assessed",
        {
            "employee_id": state.get("employee_id"),
            "incident_type": state["incident_type"],
            "risk_level": risk_level,
            "requires_approval": requires_approval,
        },
    )

    return {
        "risk_level": risk_level,
        "requires_approval": requires_approval,
        "attempt_count": 0,
        "max_attempts": 2,
    }


# =========================================================
# 4. ROUTE BASED ON RISK
# =========================================================

def route_by_risk(state: AgentState):
    if state["requires_approval"]:
        return "human_approval"

    return "auto_execute"


# =========================================================
# 5. HUMAN-IN-THE-LOOP APPROVAL
# =========================================================

def human_approval(state: AgentState):
    proposed_action = "MFA re-registration / reset"

    decision = interrupt(
        {
            "question": "Approve this remediation action?",
            "employee_id": state["employee_id"],
            "incident_type": state["incident_type"],
            "risk_level": state["risk_level"],
            "proposed_action": proposed_action,
            "evidence": state["evidence"],
        }
    )

    approved = bool(decision)

    write_audit_event(
        "human_decision",
        {
            "employee_id": state["employee_id"],
            "incident_type": state["incident_type"],
            "risk_level": state["risk_level"],
            "proposed_action": proposed_action,
            "approved": approved,
        },
    )

    if approved:
        return {
            "remediation_action": proposed_action,
            "execution_status": "approved",
        }

    return {
        "remediation_action": proposed_action,
        "execution_status": "rejected",
    }


# =========================================================
# 6. ROUTE AFTER HUMAN DECISION
# =========================================================

def route_after_approval(state: AgentState):
    if state["execution_status"] == "approved":
        return "execute"

    return "rejected"


# =========================================================
# 7. EXECUTE APPROVED REMEDIATION
# =========================================================

def execute_approved_remediation(state: AgentState):
    attempt_number = (
        state.get("attempt_count", 0) + 1
    )

    result = execute_remediation.invoke(
        {
            "employee_id": state["employee_id"],
            "action": state["remediation_action"],
            "attempt_number": attempt_number,
        }
    )

    status = result["status"]

    write_audit_event(
        "remediation_attempt",
        {
            "employee_id": state["employee_id"],
            "operation_id": result["operation_id"],
            "attempt_number": attempt_number,
            "status": status,
            "error": result.get("error"),
        },
    )

    return {
        "operation_id": result["operation_id"],
        "remediation_result": result,
        "execution_status": status,
        "attempt_count": attempt_number,
        "last_error": result.get(
            "error",
            "",
        ),
    }


# =========================================================
# 8. ROUTE AFTER EXECUTION
# =========================================================

def route_after_execution(state: AgentState):
    if state["execution_status"] == "success":
        return "verify"

    if (
        state["attempt_count"]
        < state["max_attempts"]
    ):
        return "retry"

    return "escalate"


# =========================================================
# 9. PREPARE RETRY
# =========================================================

def prepare_retry(state: AgentState):
    retries_used = max(
        state["attempt_count"],
        0,
    )

    write_audit_event(
        "retry_scheduled",
        {
            "employee_id": state["employee_id"],
            "attempt_count": state["attempt_count"],
            "retries_used": retries_used,
            "max_attempts": state["max_attempts"],
            "last_error": state.get(
                "last_error"
            ),
        },
    )

    return {}


# =========================================================
# 10. ESCALATE AFTER RETRY LIMIT
# =========================================================

def escalate_incident(state: AgentState):
    reason = (
        state.get("last_error")
        or "Remediation failed after maximum attempts"
    )

    result = create_incident.invoke(
        {
            "employee_id": state["employee_id"],
            "incident_type": state["incident_type"],
            "reason": reason,
        }
    )

    write_audit_event(
        "incident_escalated",
        {
            "employee_id": state["employee_id"],
            "incident_id": result["incident_id"],
            "reason": result["reason"],
            "attempt_count": state.get(
                "attempt_count",
                0,
            ),
        },
    )

    return {
        "escalated": True,
        "escalation_incident_id": (
            result["incident_id"]
        ),
        "execution_status": "escalated",
        "verification_status": (
            "manual_intervention_required"
        ),
    }


# =========================================================
# 11. LOW-RISK AUTO EXECUTION
# =========================================================

def auto_execute(state: AgentState):
    action = (
        "Run automated diagnostic remediation"
    )

    write_audit_event(
        "automatic_execution",
        {
            "employee_id": state.get(
                "employee_id"
            ),
            "incident_type": state[
                "incident_type"
            ],
            "action": action,
        },
    )

    return {
        "remediation_action": action,
        "execution_status": (
            "executed_automatically"
        ),
        "attempt_count": 1,
    }


# =========================================================
# 12. VERIFY RESULT
# =========================================================

def verify_result(state: AgentState):
    execution_status = state[
        "execution_status"
    ]

    if execution_status == "rejected":
        verification_status = (
            "remediation_cancelled"
        )

    elif (
        execution_status
        == "executed_automatically"
    ):
        verification_status = (
            "remediation_verified"
        )

    else:
        remediation_result = state.get(
            "remediation_result",
            {},
        )

        if (
            remediation_result.get(
                "status"
            )
            == "success"
            and remediation_result.get(
                "new_mfa_status"
            )
            == "re_registration_required"
        ):
            verification_status = (
                "remediation_verified"
            )

        else:
            verification_status = (
                "verification_failed"
            )

    write_audit_event(
        "verification_completed",
        {
            "employee_id": state.get(
                "employee_id"
            ),
            "operation_id": state.get(
                "operation_id"
            ),
            "execution_status": (
                execution_status
            ),
            "verification_status": (
                verification_status
            ),
        },
    )

    return {
        "verification_status": (
            verification_status
        )
    }


# =========================================================
# 13. FINAL RESPONSE
# =========================================================

def create_final_response(state: AgentState):
    operation_id = state.get(
        "operation_id",
        "N/A",
    )

    escalation_id = state.get(
        "escalation_incident_id",
        "N/A",
    )

    attempt_count = state.get(
        "attempt_count",
        0,
    )

    retries_used = max(
        attempt_count - 1,
        0,
    )

    response = (
        f"Incident Type: "
        f"{state['incident_type']}\n"
        f"Risk Level: "
        f"{state['risk_level']}\n\n"
        "Evidence:\n- "
        + "\n- ".join(state["evidence"])
        + "\n\n"
        f"Remediation Action: "
        f"{state.get('remediation_action', 'N/A')}\n"
        f"Execution Status: "
        f"{state['execution_status']}\n"
        f"Attempts: "
        f"{attempt_count}\n"
        f"Retries Used: "
        f"{retries_used}\n"
        f"Operation ID: "
        f"{operation_id}\n"
        f"Escalation Incident ID: "
        f"{escalation_id}\n"
        f"Verification Status: "
        f"{state['verification_status']}"
    )

    write_audit_event(
        "workflow_completed",
        {
            "employee_id": state.get(
                "employee_id"
            ),
            "incident_type": state[
                "incident_type"
            ],
            "risk_level": state[
                "risk_level"
            ],
            "execution_status": state[
                "execution_status"
            ],
            "attempt_count": attempt_count,
            "retries_used": retries_used,
            "operation_id": operation_id,
            "escalation_incident_id": (
                escalation_id
            ),
            "verification_status": state[
                "verification_status"
            ],
        },
    )

    return {
        "final_response": response
    }


# =========================================================
# 14. BUILD LANGGRAPH WORKFLOW
# =========================================================

def build_workflow():
    workflow = StateGraph(
        AgentState
    )

    # Nodes
    workflow.add_node(
        "classify_request",
        classify_request,
    )

    workflow.add_node(
        "investigate",
        investigate,
    )

    workflow.add_node(
        "assess_risk",
        assess_risk,
    )

    workflow.add_node(
        "human_approval",
        human_approval,
    )

    workflow.add_node(
        "execute_approved_remediation",
        execute_approved_remediation,
    )

    workflow.add_node(
        "prepare_retry",
        prepare_retry,
    )

    workflow.add_node(
        "escalate_incident",
        escalate_incident,
    )

    workflow.add_node(
        "auto_execute",
        auto_execute,
    )

    workflow.add_node(
        "verify_result",
        verify_result,
    )

    workflow.add_node(
        "create_final_response",
        create_final_response,
    )

    # Start
    workflow.add_edge(
        START,
        "classify_request",
    )

    workflow.add_edge(
        "classify_request",
        "investigate",
    )

    workflow.add_edge(
        "investigate",
        "assess_risk",
    )

    # Risk routing
    workflow.add_conditional_edges(
        "assess_risk",
        route_by_risk,
        {
            "human_approval":
                "human_approval",
            "auto_execute":
                "auto_execute",
        },
    )

    # Human decision routing
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute":
                "execute_approved_remediation",
            "rejected":
                "verify_result",
        },
    )

    # Remediation result routing
    workflow.add_conditional_edges(
        "execute_approved_remediation",
        route_after_execution,
        {
            "verify":
                "verify_result",
            "retry":
                "prepare_retry",
            "escalate":
                "escalate_incident",
        },
    )

    # Retry loops back into remediation
    workflow.add_edge(
        "prepare_retry",
        "execute_approved_remediation",
    )

    # Low-risk path
    workflow.add_edge(
        "auto_execute",
        "verify_result",
    )

    # Escalation finishes workflow
    workflow.add_edge(
        "escalate_incident",
        "create_final_response",
    )

    # Verified / rejected flow
    workflow.add_edge(
        "verify_result",
        "create_final_response",
    )

    # End
    workflow.add_edge(
        "create_final_response",
        END,
    )

    checkpointer = InMemorySaver()

    return workflow.compile(
        checkpointer=checkpointer
    )