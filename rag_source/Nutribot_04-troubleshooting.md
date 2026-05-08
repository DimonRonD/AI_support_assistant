# Nutribot n8n - Troubleshooting Guide

## Common Failure: Telegram webhook host resolution
### Symptom
`Bad request - please check your parameters`  
`Telegram Trigger: Bad Request: bad webhook: Failed to resolve host`

### Root Cause
Telegram cannot resolve or reach the host used in webhook URL.

### Fix
1. Confirm domain resolves publicly (DNS A/AAAA records).
2. Confirm HTTPS is valid and endpoint is reachable from internet.
3. Set correct n8n base URL (`WEBHOOK_URL`) to public HTTPS host.
4. Delete and recreate webhook:
   - `deleteWebhook?drop_pending_updates=true`
   - reactivate workflow trigger or call `setWebhook`.

## Common Failure: Telegram API returns 404 Not Found
### Symptom
`Invoke-RestMethod : {"ok":false,"error_code":404,"description":"Not Found"}`

### Root Cause
Invalid bot token in request URL (empty, partial, malformed, copied with masking).

### Fix
1. Reassign full token in shell variable.
2. Validate via `getMe`.
3. Retry `getWebhookInfo`.

## Common Failure: PowerShell command parsing errors
### Symptom
Errors mentioning `Get-Process` when running Telegram API commands.

### Root Cause
Prompt text (`PS C:\...>`) or output lines were pasted as commands.

### Fix
- Execute only clean command lines, without prompt prefixes or previous output.

## Common Failure: Workflow active but bot does not respond
### Checks
- Workflow is activated in n8n.
- Telegram webhook URL points to current environment.
- Credential bindings are valid after import.
- n8n execution logs show incoming updates.
- No blocking errors in Code nodes.

## Security Incident: Token exposure
### Symptom
Bot token appears in chat logs, terminal history, screenshots, or repo.

### Action
1. Revoke token via BotFather.
2. Issue a new token.
3. Update n8n credentials.
4. Remove exposed token from history/files when possible.

## Diagnostic Commands (PowerShell)
```powershell
$TOKEN = 'FULL_BOT_TOKEN'
Invoke-RestMethod -Uri ("https://api.telegram.org/bot{0}/getMe" -f $TOKEN)
Invoke-RestMethod -Uri ("https://api.telegram.org/bot{0}/getWebhookInfo" -f $TOKEN)
Invoke-RestMethod -Method Post -Uri ("https://api.telegram.org/bot{0}/deleteWebhook?drop_pending_updates=true" -f $TOKEN)
```

## RAG Tags
`troubleshooting`, `telegram-webhook`, `dns`, `powershell`, `incident-response`

## Q/A for Assistant
Q: What does "Failed to resolve host" mean in Telegram Trigger?
A: Telegram cannot resolve the webhook domain in DNS or cannot reach it reliably.

Q: Why do I get 404 from Telegram API endpoints?
A: The bot token used in the request URL is usually invalid or incomplete.
