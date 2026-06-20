# Testing Methodology for Hermes Android App

## Core Rule: Autonomous Testing

**НИКОГДА не просить пользователя «проверь сам». Тестировать самостоятельно.**

User explicitly requires autonomous verification before declaring success.

## How to Test

### Phone connected via USB
```bash
ADB=/home/user/Android/Sdk/platform-tools/adb

# Health check
$ADB shell "/system/bin/curl -s -m 5 http://<YOUR_VPS_IP>:8643/health"

# Full chat test through VPS
$ADB shell "/system/bin/curl -s -m 60 -H 'Authorization: Bearer KEY' \
  -H 'Content-Type: application/json' \
  -d '{\"model\":\"qwen3.6-35b-heretic\",\"messages\":[{\"role\":\"user\",\"content\":\"Say test\"}],\"stream\":false}' \
  http://<YOUR_VPS_IP>:8643/v1/chat/completions"
```

### Check infrastructure BEFORE claiming "works"
```bash
# 1. Proxy alive?
ss -tlnp | grep 8643

# 2. Hermes gateway alive?
ss -tlnp | grep 8648

# 3. SSH tunnel alive?
ssh root@<YOUR_VPS_IP> "ss -tlnp | grep 8643"

# 4. VPS health check
curl -s http://<YOUR_VPS_IP>:8643/health

# 5. LiteLLM alive?
curl -s -H "Authorization: Bearer sk-local" http://localhost:4000/health

# 6. OpenCode+ alive?
curl -s http://localhost:8646/health
```

### When user reports error — diagnostic sequence
1. Check `/tmp/proxy.log` for routing errors
2. Check `adb logcat --pid=$(pidof app)` for app-level errors
3. Test the exact API call from the phone
4. If infrastructure is alive but app reports error → check Android SharedPreferences, model mismatch, URL config
5. Don't guess — trace the full request path

### Pattern: phone test script
```python
import urllib.request, json
req = urllib.request.Request('http://<YOUR_VPS_IP>:8643/v1/chat/completions',
    data=json.dumps({'model':'qwen3.6-35b-heretic','messages':[{'role':'user','content':'Say test'}]}).encode(),
    headers={'Authorization':'Bearer KEY','Content-Type':'application/json'})
resp = urllib.request.urlopen(req, timeout=60)
print(json.loads(resp.read())['choices'][0]['message']['content'])
```

## Behavioral Guidelines

- **Deep analysis before action.** Plan before implementing.
- **Root cause analysis, not band-aids.** When a fix doesn't work, figure out WHY, don't try another random fix.
- **One fix at a time.** Don't change 5 things simultaneously — can't tell which fixed it.
- **Test after each fix.** Don't accumulate changes untested.
- **Be honest about what's working and what's not.** Don't sugarcoat.
- **When stuck, launch the auditor.** Full analysis beats guessing.
