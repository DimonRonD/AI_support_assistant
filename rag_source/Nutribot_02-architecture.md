# Nutribot n8n - Architecture and Technologies

## Technical Architecture
The solution is a workflow-centric architecture:
- **Entry point:** `Telegram Trigger` node receives user messages.
- **Routing layer:** command parsing + branching (`Switch`, `Code` nodes).
- **State layer:** Google Sheets for user profile and process state.
- **Generation layer:** OpenAI and GigaChat nodes for AI-generated responses.
- **Delivery layer:** Telegram send-message nodes return responses to users.

## Workflow Design Characteristics
- Event-driven processing per incoming Telegram update.
- FSM-like questionnaire control implemented in `Code` nodes.
- Data normalization and validation in JavaScript.
- Context-aware response formatting before message delivery.

## Technologies Used
- `n8n` (workflow orchestration platform).
- Telegram Bot API (webhook-based bot interaction).
- Google Sheets API (structured storage without dedicated DB).
- OpenAI API (LLM output for nutrition/dialog).
- GigaChat API (alternative LLM path).
- JavaScript (embedded in n8n `Code` nodes).

## Data Model (Practical)
Typical stored attributes:
- `chat_id` (Telegram user/chat identifier).
- questionnaire fields (age, sex, weight, height, etc.).
- survey progression state (current step).
- optional plan generation context (depending on branch).

## External Dependencies
- Public HTTPS domain for Telegram webhook callbacks.
- DNS availability and SSL certificate validity.
- Availability and quotas of third-party APIs.

## Non-Functional Considerations
- Reliability depends on external APIs and network reachability.
- Maintainability depends on workflow versioning discipline.
- Security depends on proper credential handling in n8n.

## RAG Tags
`architecture`, `tech-stack`, `integrations`, `data-flow`, `dependencies`

## Q/A for Assistant
Q: Where is the business logic implemented?
A: In the n8n workflow nodes, especially embedded JavaScript inside Code nodes.

Q: Does the project use a traditional SQL database?
A: Not in the current form. User-related state is stored in Google Sheets.

Q: Why is HTTPS required?
A: Telegram webhooks require a publicly reachable HTTPS endpoint for callback delivery.
