# Enterprise Agentic Ops Copilot

Enterprise-style **Agentic AI operations copilot** built with Amazon Bedrock, Amazon Nova Pro, LangGraph, Python, and structured enterprise tools.

The system analyzes IT support incidents, reasons about the affected service, gathers evidence using tools, assesses operational risk, requests human approval when required, performs remediation, retries transient failures, escalates unresolved incidents, and records an audit trail.

---

## Project Highlights

- Amazon Nova Pro reasoning through Amazon Bedrock
- LangGraph-based agent orchestration
- Structured incident classification with Pydantic validation
- AI-generated investigation planning
- Bedrock-guided enterprise tool selection
- Human-in-the-loop approval for sensitive remediation
- Tool-based employee and service investigation
- Automated remediation execution
- Retry handling for transient failures
- Incident escalation after retry exhaustion
- Result verification after remediation
- Structured JSONL audit logging
- Automated multi-scenario agent evaluation

---

## Architecture

```text
User Request
     |
     v
Amazon Nova Pro
via Amazon Bedrock
     |
     v
Structured Incident Analysis
     |
     +--> Incident Type
     +--> Affected Service
     +--> Confidence Score
     +--> Investigation Plan
     |
     v
LangGraph Agent Workflow
     |
     v
Enterprise Tool Execution
     |
     +--> Service Status Tool
     +--> Employee Lookup Tool
     |
     v
Observed Evidence
     |
     v
Risk Assessment
     |
     +---------------------------+
     |                           |
     v                           v
Low Risk                    Medium / High Risk
     |                           |
     v                           v
Auto Execution              Human Approval
     |                           |
     +-------------+-------------+
                   |
                   v
           Remediation Tool
                   |
                   v
           Retry / Escalation
                   |
                   v
              Verification
                   |
                   v
             Final Response
                   |
                   v
              Audit Log