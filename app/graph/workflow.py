from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.observability.audit_logger import write_audit_event
from app.tools.employee_lookup import employee_lookup
from app.tools.remediation import execute_remediation
from app.tools.service_status import service_status


class AgentState(TypedDict, total=False):
    user_request: str
    employee_id: str

    incident_type: str
    evidence: list[str]

    risk_level: str
    requires_approval: bool

    remediation_action: str
    execution_status: str
    operation_id: str
    remediation_result: dict

    verification_status: str
    final_response: str


# ---------------------------------------------------------
# 1. CLASSIFY REQUEST
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# 2. INVESTIGATE USING TOOLS
# ---------------------------------------------------------

def investigate(state: AgentState):
    incident_type = state["incident_type"]
    employee_id = state.get("employee_id", "E1001")

    if incident_type == "vpn_access":
        service_result = service_status.invoke(
            {"service_name": "vpn"}
        )

    elif incident_type == "authentication":
        service_result = service_status.invoke(
            {"service_name": "authentication"}
        )

    else:
        service_result = {
            "service": "general_it",
            "status": "unknown",
        }

    employee_result = employee_lookup.invoke(
        {"employee_id": employee_id}
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


# ---------------------------------------------------------
# 3. RISK ASSESSMENT
# ---------------------------------------------------------

def assess_risk(state: AgentState):
    evidence_text = " ".join(state["evidence"]).lower()

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
    }


# ---------------------------------------------------------
# 4. RISK ROUTING
# ---------------------------------------------------------

def route_by_risk(state: AgentState):
    if state["requires_approval"]:
        return "human_approval"

    return "auto_execute"


# ---------------------------------------------------------
# 5A. HUMAN APPROVAL
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# 5B. ROUTE AFTER HUMAN DECISION
# ---------------------------------------------------------

def route_after_approval(state: AgentState):
    if state["execution_status"] == "approved":
        return "execute"

    return "rejected"


# ---------------------------------------------------------
# 6A. EXECUTE APPROVED REMEDIATION
# ---------------------------------------------------------

def execute_approved_remediation(state: AgentState):
    result = execute_remediation.invoke(
        {
            "employee_id": state["employee_id"],
            "action": state["remediation_action"],
        }
    )

    write_audit_event(
        "remediation_executed",
        {
            "employee_id": state["employee_id"],
            "operation_id": result["operation_id"],
            "action": result["action"],
            "status": result["status"],
            "new_mfa_status": result["new_mfa_status"],
        },
    )

    return {
        "operation_id": result["operation_id"],
        "remediation_result": result,
        "execution_status": result["status"],
    }


# ---------------------------------------------------------
# 6B. LOW-RISK AUTOMATIC EXECUTION
# ---------------------------------------------------------

def auto_execute(state: AgentState):
    action = "Run automated diagnostic remediation"

    write_audit_event(
        "automatic_execution",
        {
            "employee_id": state.get("employee_id"),
            "incident_type": state["incident_type"],
            "action": action,
        },
    )

    return {
        "remediation_action": action,
        "execution_status": "executed_automatically",
    }


# ---------------------------------------------------------
# 7. VERIFY RESULT
# ---------------------------------------------------------

def verify_result(state: AgentState):
    execution_status = state["execution_status"]

    if execution_status == "rejected":
        verification_status = "remediation_cancelled"

    elif execution_status == "executed_automatically":
        verification_status = "remediation_verified"

    else:
        remediation_result = state.get(
            "remediation_result",
            {}
        )

        if (
            remediation_result.get("status") == "success"
            and remediation_result.get("new_mfa_status")
            == "re_registration_required"
        ):
            verification_status = "remediation_verified"

        else:
            verification_status = "verification_failed"

    write_audit_event(
        "verification_completed",
        {
            "employee_id": state.get("employee_id"),
            "operation_id": state.get("operation_id"),
            "execution_status": execution_status,
            "verification_status": verification_status,
        },
    )

    return {
        "verification_status": verification_status
    }


# ---------------------------------------------------------
# 8. FINAL RESPONSE
# ---------------------------------------------------------

def create_final_response(state: AgentState):
    operation_id = state.get(
        "operation_id",
        "N/A"
    )

    response = (
        f"Incident Type: {state['incident_type']}\n"
        f"Risk Level: {state['risk_level']}\n\n"
        "Evidence:\n- "
        + "\n- ".join(state["evidence"])
        + "\n\n"
        f"Remediation Action: "
        f"{state['remediation_action']}\n"
        f"Execution Status: "
        f"{state['execution_status']}\n"
        f"Operation ID: "
        f"{operation_id}\n"
        f"Verification Status: "
        f"{state['verification_status']}"
    )

    write_audit_event(
        "workflow_completed",
        {
            "employee_id": state.get("employee_id"),
            "incident_type": state["incident_type"],
            "risk_level": state["risk_level"],
            "operation_id": operation_id,
            "execution_status": state["execution_status"],
            "verification_status": state["verification_status"],
        },
    )

    return {
        "final_response": response
    }


# ---------------------------------------------------------
# 9. BUILD LANGGRAPH WORKFLOW
# ---------------------------------------------------------

def build_workflow():
    workflow = StateGraph(AgentState)

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

    workflow.add_conditional_edges(
        "assess_risk",
        route_by_risk,
        {
            "human_approval": "human_approval",
            "auto_execute": "auto_execute",
        },
    )

    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute": "execute_approved_remediation",
            "rejected": "verify_result",
        },
    )

    workflow.add_edge(
        "execute_approved_remediation",
        "verify_result",
    )

    workflow.add_edge(
        "auto_execute",
        "verify_result",
    )

    workflow.add_edge(
        "verify_result",
        "create_final_response",
    )

    workflow.add_edge(
        "create_final_response",
        END,
    )

    checkpointer = InMemorySaver()

    return workflow.compile(
        checkpointer=checkpointer
    )