# Nutribot n8n - Process and Deployment Runbook

## Runtime Process (How It Works)
1. User sends a message/command to the Telegram bot.
2. `Telegram Trigger` receives the event in n8n.
3. Workflow identifies user intent (`/survey`, `/nutrition`, `/exercise`, `/giga`).
4. For survey flow, state is read/written to Google Sheets.
5. For generation flows, request is sent to OpenAI or GigaChat.
6. Formatted response is returned to user via Telegram.

## Deployment Prerequisites
- Running n8n instance (cloud or self-hosted).
- Public domain with valid DNS and SSL.
- Correct base webhook URL configured in n8n (`WEBHOOK_URL`).
- Configured credentials in n8n for:
  - Telegram bot token;
  - Google Sheets access;
  - OpenAI API;
  - GigaChat API.

## Deployment Steps
1. Import `Health_TG_bot (1).json` into n8n.
2. Bind all required credentials in corresponding nodes.
3. Verify Google Sheets document/sheet references.
4. Ensure n8n base URL is public and HTTPS.
5. Activate workflow.
6. Verify Telegram webhook registration.
7. Run smoke tests for major commands.

## Post-Deploy Smoke Test Checklist
- `/survey` starts and validates input correctly.
- `/nutrition` returns generated plan text.
- `/exercise` returns workout data in readable format.
- `/giga` returns response via GigaChat branch.
- Unknown command returns fallback/help guidance.

## Operating Procedure
- Monitor n8n execution logs for failed runs.
- Track API errors (rate limits, auth issues, bad requests).
- Keep worksheet schema stable across updates.
- Re-test critical flows after each workflow edit.

## Change Management
- Export workflow after approved changes.
- Store workflow JSON in version control.
- Keep release notes: what changed, why, impact, rollback hint.

## Rollback
If a deployment introduces regression:
1. Deactivate current workflow.
2. Re-import previous stable JSON version.
3. Rebind credentials if needed.
4. Reactivate and rerun smoke tests.

## RAG Tags
`runbook`, `deployment`, `operations`, `smoke-test`, `rollback`

## Q/A for Assistant
Q: What are the minimum steps to deploy Nutribot?
A: Import workflow, configure credentials, ensure public HTTPS webhook URL, activate workflow, and run command smoke tests.

Q: What should be monitored in production?
A: n8n execution failures, Telegram webhook health, third-party API errors, and data consistency in Google Sheets.
