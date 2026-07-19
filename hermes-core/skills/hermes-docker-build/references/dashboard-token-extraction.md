# Dashboard Token Extraction

When running Hermes dashboard (locally or in Docker), a session token is generated
on every start and injected into the HTML page served at `/`.

## How the token is generated

```python
# hermes_cli/web_server.py:183
_SESSION_TOKEN = os.environ.get("HERMES_DASHBOARD_SESSION_TOKEN") or secrets.token_urlsafe(32)
```

- If `HERMES_DASHBOARD_SESSION_TOKEN` env var is set → use that value
- If not → generate a random one (`secrets.token_urlsafe(32)`)
- Token dies when the process exits

## How the token is injected

```python
# hermes_cli/web_server.py:9078-9084
bootstrap_script = (
    f'<script>window.__HERMES_SESSION_TOKEN__="{_SESSION_TOKEN}";'
    f"window.__HERMES_DASHBOARD_EMBEDDED_CHAT__={chat_js};"
    f'window.__HERMES_BASE_PATH__="{prefix}";'
    f"window.__HERMES_AUTH_REQUIRED__={gated_js};"
    f"</script>"
)
```

The token is embedded in the HTML served at `GET /`.

## Extraction (3 methods)

### Method 1: grep from HTML (recommended)

```bash
TOKEN=$(curl -s http://127.0.0.1:<PORT>/ | \
  grep -oP '__HERMES_SESSION_TOKEN__="\K[^"]+')
echo "Token: $TOKEN"
```

Where `<PORT>` is the dashboard port (e.g. 9121, 9119, 19119).

### Method 2: Set env var at launch (most reliable)

```bash
# Generate a known token
MY_TOKEN=*** rand -hex 32)

# Pass it to dashboard
HERMES_HOME=/path/to/data \
  HERMES_DASHBOARD_SESSION_TOKEN=*** \
  hermes dashboard --port 9121 --host 127.0.0.1 --no-open --skip-build
```

Then use `$MY_TOKEN` directly — no extraction needed.

### Method 3: python3 extraction

```bash
python3 -c "
import re, urllib.request
html = urllib.request.urlopen('http://127.0.0.1:<PORT>/').read().decode()
m = re.search(r'__HERMES_SESSION_TOKEN__=\"([^\"]+)\"', html)
print(f'Token: {m.group(1)}' if m else 'Not found')
"
```

## IMPORTANT: always show the full token

When extracting a token for the user, output the **complete value**, not a truncated
preview. A truncated token like `chvbgr...IC-s` is useless for `connection.json`
or env vars. Always:

```bash
# BAD — truncated
echo "Token: ${TOKEN:0:6}..."

# GOOD — full value
echo "Token: $TOKEN"
```
