# Nutribot n8n - FAQ for Assistant

## Product and Scope
### Q: What is included in this project repository?
A: At this stage, the repository contains an exported n8n workflow JSON implementing Telegram bot automation logic.

### Q: Is Nutribot production-ready as-is?
A: It is a workable integration flow, but production readiness depends on environment hardening, versioning discipline, and monitoring setup.

## Technical Questions
### Q: Where are credentials stored?
A: Credentials are managed in n8n credential storage and referenced by nodes in the workflow export.

### Q: Does the workflow include custom code?
A: Yes. JavaScript in n8n Code nodes implements validation, routing, and message preparation logic.

### Q: Can this be migrated to another channel besides Telegram?
A: Yes. Core logic can be adapted by replacing trigger/delivery nodes and preserving processing branches.

## Deployment and Operations
### Q: What is mandatory for Telegram integration?
A: Public HTTPS n8n endpoint, valid DNS, configured bot token, and active Telegram Trigger node.

### Q: How do we safely update the workflow?
A: Export the new version, version-control JSON, test on staging bot, then deploy and smoke-test critical commands.

### Q: What are the top operational risks?
A: Webhook/DNS failures, third-party API limits, credential drift, and spreadsheet schema changes.

## Business and Economics
### Q: Where does cost reduction come from?
A: From automating repetitive interactions (intake questions, baseline recommendations, routine replies).

### Q: What is the scaling advantage?
A: One workflow handles many parallel conversations without linear increase in staff workload.

### Q: How does it improve retention?
A: Faster responses and personalized guidance in Telegram improve user engagement continuity.

## Governance Recommendations
### Q: What should be added next to improve maintainability?
A: Add README, architecture notes, release checklist, and changelog with versioned workflow exports.

### Q: Should raw workflow JSON be publicly shared?
A: Prefer sanitized exports because raw files may expose sensitive infrastructure metadata.

## Short Answers (for retrieval)
- Nutribot = n8n-based Telegram automation for nutrition/training support.
- Main commands = `/survey`, `/nutrition`, `/exercise`, `/giga`.
- Main data store = Google Sheets.
- Main AI providers = OpenAI and GigaChat.
- Main deployment requirement = stable public HTTPS webhook URL.

## RAG Tags
`faq`, `assistant-answers`, `operations`, `economics`, `best-practices`
