import json
import os

import boto3

from app.schemas.incident_analysis import IncidentAnalysis


AWS_REGION = os.getenv(
    "AWS_REGION",
    "us-east-2",
)

BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.amazon.nova-pro-v1:0",
)


def classify_incident_with_bedrock(
    user_request: str,
) -> IncidentAnalysis:
    """
    Classify an enterprise IT request using Amazon Bedrock.
    """

    client = boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
    )

    system_prompt = """
You are an enterprise IT operations reasoning agent.

Analyze the user's issue and return ONLY valid JSON.

Required JSON structure:

{
  "incident_type": "vpn_access | authentication | general_it",
  "affected_service": "vpn | authentication | general_it",
  "confidence": 0.0,
  "recommended_investigation": [
    "step 1",
    "step 2"
  ]
}

Rules:

1. Use vpn_access for VPN or remote connectivity issues.
2. Use authentication for password, login, MFA, or authentication issues.
3. Use general_it when neither category clearly applies.
4. confidence must be between 0 and 1.
5. recommended_investigation should contain concise operational steps.
6. Return JSON only.
7. Do not use markdown or code fences.
"""

    response = client.converse(
        modelId=BEDROCK_MODEL_ID,
        system=[
            {
                "text": system_prompt
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": user_request
                    }
                ],
            }
        ],
        inferenceConfig={
            "maxTokens": 400,
            "temperature": 0,
        },
    )

    content = response[
        "output"
    ][
        "message"
    ][
        "content"
    ]

    model_text = next(
        item["text"]
        for item in content
        if "text" in item
    )

    model_text = (
        model_text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    start = model_text.find("{")
    end = model_text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "Bedrock did not return valid JSON."
        )

    json_text = model_text[
        start:end + 1
    ]

    parsed = json.loads(
        json_text
    )

    return IncidentAnalysis.model_validate(
        parsed
    )