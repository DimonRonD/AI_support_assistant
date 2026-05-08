# Nutribot n8n - Overview

## Project Purpose
`Nutribot` is a Telegram bot automation built in `n8n` for nutrition and training support scenarios.

Business goal:
- reduce manual consultant workload;
- deliver 24/7 baseline recommendations;
- increase user engagement through fast personalized responses.

## What This Project Is
- Single exported `n8n` workflow file: `Health_TG_bot (1).json`.
- No standalone backend service in this repository.
- Main logic is implemented via `n8n` nodes plus embedded JavaScript in `Code` nodes.

## Primary User Flows
- `/survey`: progressive profile questionnaire (age, sex, weight, height, etc.) with validation.
- `/nutrition`: nutrition recommendation generation.
- `/exercise`: workout plan preparation from tabular data.
- `/giga`: alternate AI response path using GigaChat integration.

## Core Integrations
- Telegram Bot API (trigger + message delivery).
- Google Sheets (state/data storage).
- OpenAI API (LLM generation).
- GigaChat API (alternate LLM path).

## Business Benefits (Summary)
- Lower cost per user interaction by automating repetitive communication.
- Higher throughput without linear team growth.
- Faster time-to-market for new conversational scenarios.
- Better retention via instant responses in a familiar channel (Telegram).

## RAG Tags
`overview`, `business-goals`, `value-proposition`, `telegram-bot`, `n8n-workflow`

## Q/A for Assistant
Q: What is Nutribot in this project?
A: Nutribot is a Telegram automation workflow implemented in n8n that handles survey, nutrition, and exercise assistance flows.

Q: Is this a classic backend app repository?
A: No. The repository currently contains an exported n8n workflow JSON, not a full backend codebase.

Q: What business problem does Nutribot solve?
A: It reduces manual support effort, scales client interaction, and improves response speed and personalization.
