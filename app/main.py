from langgraph.types import Command

from app.graph.workflow import build_workflow


def main():
    agent = build_workflow()

    request = (
        "An employee cannot connect to the corporate VPN "
        "after changing their phone."
    )

    config = {
        "configurable": {
            "thread_id": "incident-E1001-001"
        }
    }

    initial_state = {
        "user_request": request,
        "employee_id": "E1001",
        "evidence": [],
    }

    result = agent.invoke(
        initial_state,
        config=config,
    )

    print(
        "\n=== ENTERPRISE AGENTIC OPS COPILOT ==="
    )

    print(
        f"\nUser Request:\n{request}"
    )

    if "__interrupt__" in result:
        print(
            "\n=== HUMAN APPROVAL REQUIRED ==="
        )

        interrupt_info = (
            result["__interrupt__"][0].value
        )

        print(
            f"Incident Type: "
            f"{interrupt_info['incident_type']}"
        )

        print(
            f"Risk Level: "
            f"{interrupt_info['risk_level']}"
        )

        print(
            f"Proposed Action: "
            f"{interrupt_info['proposed_action']}"
        )

        print("\nEvidence:")

        for item in interrupt_info["evidence"]:
            print(f"- {item}")

        approval = input(
            "\nApprove remediation? (yes/no): "
        ).strip().lower()

        approved = approval in {
            "yes",
            "y",
        }

        result = agent.invoke(
            Command(
                resume=approved
            ),
            config=config,
        )

    print(
        "\n=== FINAL AGENT RESULT ==="
    )

    print(
        result["final_response"]
    )


if __name__ == "__main__":
    main()