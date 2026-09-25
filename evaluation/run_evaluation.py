import json
import sys
from pathlib import Path
from statistics import mean


# ---------------------------------------------------------
# Make project root importable
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.services.bedrock_classifier import (  # noqa: E402
    classify_incident_with_bedrock,
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

SCENARIOS_FILE = (
    PROJECT_ROOT
    / "evaluation"
    / "scenarios"
    / "incidents.json"
)


# ---------------------------------------------------------
# Load scenarios
# ---------------------------------------------------------

def load_scenarios() -> list[dict]:
    with SCENARIOS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ---------------------------------------------------------
# Evaluate one scenario
# ---------------------------------------------------------

def evaluate_scenario(
    scenario: dict,
) -> dict:
    scenario_id = scenario["id"]
    request = scenario["request"]

    expected_incident = scenario[
        "expected_incident_type"
    ]

    expected_service = scenario[
        "expected_service"
    ]

    try:
        analysis = classify_incident_with_bedrock(
            request
        )

        incident_correct = (
            analysis.incident_type
            == expected_incident
        )

        service_correct = (
            analysis.affected_service
            == expected_service
        )

        return {
            "id": scenario_id,
            "request": request,
            "expected_incident_type": (
                expected_incident
            ),
            "actual_incident_type": (
                analysis.incident_type
            ),
            "incident_correct": (
                incident_correct
            ),
            "expected_service": (
                expected_service
            ),
            "actual_service": (
                analysis.affected_service
            ),
            "service_correct": (
                service_correct
            ),
            "confidence": (
                analysis.confidence
            ),
            "investigation_plan": (
                analysis.recommended_investigation
            ),
            "error": None,
        }

    except Exception as exc:
        return {
            "id": scenario_id,
            "request": request,
            "expected_incident_type": (
                expected_incident
            ),
            "actual_incident_type": None,
            "incident_correct": False,
            "expected_service": (
                expected_service
            ),
            "actual_service": None,
            "service_correct": False,
            "confidence": 0.0,
            "investigation_plan": [],
            "error": str(exc),
        }


# ---------------------------------------------------------
# Print individual result
# ---------------------------------------------------------

def print_result(
    result: dict,
) -> None:
    print()
    print("=" * 70)
    print(
        f"Scenario: {result['id']}"
    )
    print("=" * 70)

    print(
        f"Request: "
        f"{result['request']}"
    )

    if result["error"]:
        print(
            f"ERROR: {result['error']}"
        )
        return

    incident_symbol = (
        "PASS"
        if result["incident_correct"]
        else "FAIL"
    )

    service_symbol = (
        "PASS"
        if result["service_correct"]
        else "FAIL"
    )

    print()
    print(
        "Incident Classification:"
    )

    print(
        f"  Expected: "
        f"{result['expected_incident_type']}"
    )

    print(
        f"  Actual:   "
        f"{result['actual_incident_type']}"
    )

    print(
        f"  Result:   {incident_symbol}"
    )

    print()
    print(
        "Service Routing:"
    )

    print(
        f"  Expected: "
        f"{result['expected_service']}"
    )

    print(
        f"  Actual:   "
        f"{result['actual_service']}"
    )

    print(
        f"  Result:   {service_symbol}"
    )

    print()
    print(
        f"Bedrock Confidence: "
        f"{result['confidence']:.2f}"
    )

    print()
    print(
        "Investigation Plan:"
    )

    for step in result[
        "investigation_plan"
    ]:
        print(
            f"  - {step}"
        )


# ---------------------------------------------------------
# Run evaluation
# ---------------------------------------------------------

def main():
    scenarios = load_scenarios()

    print()
    print(
        "=== ENTERPRISE AGENTIC OPS "
        "EVALUATION ==="
    )

    print(
        f"Scenarios: {len(scenarios)}"
    )

    results = []

    for scenario in scenarios:
        result = evaluate_scenario(
            scenario
        )

        results.append(
            result
        )

        print_result(
            result
        )

    total = len(results)

    incident_passes = sum(
        1
        for result in results
        if result["incident_correct"]
    )

    service_passes = sum(
        1
        for result in results
        if result["service_correct"]
    )

    successful_results = [
        result
        for result in results
        if result["error"] is None
    ]

    confidences = [
        result["confidence"]
        for result in successful_results
    ]

    average_confidence = (
        mean(confidences)
        if confidences
        else 0.0
    )

    incident_accuracy = (
        incident_passes / total * 100
        if total
        else 0.0
    )

    service_accuracy = (
        service_passes / total * 100
        if total
        else 0.0
    )

    failures = [
        result
        for result in results
        if result["error"]
    ]

    print()
    print("=" * 70)
    print(
        "EVALUATION SUMMARY"
    )
    print("=" * 70)

    print(
        "Classification Accuracy: "
        f"{incident_passes}/{total} "
        f"({incident_accuracy:.1f}%)"
    )

    print(
        "Service Routing Accuracy: "
        f"{service_passes}/{total} "
        f"({service_accuracy:.1f}%)"
    )

    print(
        "Average Bedrock Confidence: "
        f"{average_confidence:.2f}"
    )

    print(
        "Execution Errors: "
        f"{len(failures)}"
    )

    print()

    if (
        incident_passes == total
        and service_passes == total
        and not failures
    ):
        print(
            "OVERALL RESULT: PASS"
        )
    else:
        print(
            "OVERALL RESULT: REVIEW REQUIRED"
        )


if __name__ == "__main__":
    main()