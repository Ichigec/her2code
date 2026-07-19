# System Topology Graph — Neo4j Infrastructure Mapping

Produced 2026-06-20 during orchestrator transformation cycle (PID `orchestrator-transformation_20260620_213116`).

## Purpose

Model the physical/network infrastructure as a Neo4j graph:
services, hosts, ports, containers, tunnels — connected to code files.
Enables impact analysis: "if I restart voice-proxy, what breaks?"

## Script

`~/.hermes/scripts/topology_ingest.py` (741 lines, Python 3.12, stdlib-only)

Collects:
- `docker ps` → Container nodes (31 containers on jetson)
- `ss -tlnp` → Port nodes (LISTEN ports)
- systemd services → Service nodes
- hostname/ip → Host nodes
- Manually defined services for non-docker processes (Hermes gateway, voice proxy, socat forward)

Run: `python3 ~/.hermes/scripts/topology_ingest.py`

## Node Labels

| Label | Properties | Count (2026-06-20) |
|-------|-----------|---------------------|
| `Service` | name, port?, host, status, health_endpoint?, repo?, language? | 39 |
| `Host` | name, ip, type (physical/vps/phone), os, arch, gpu? | 3 (jetson, vps, phone) |
| `Container` | name, image, ports[], status | 31 |
| `Port` | number, protocol, exposed, description? | 0 (ARM64 ss parsing bug) |
| `Tunnel` | id, type (ssh_reverse/cloudflared/ngrok), local_port, remote_port, target_host | 1 |

## Relationships

- `(s:Service)-[:DEPLOYED_ON]->(h:Host)` — where the service runs
- `(s:Service)-[:RUNS_IN]->(c:Container)` — Docker container mapping
- `(s:Service)-[:EXPOSES_PORT]->(p:Port)` — port binding
- `(s1:Service)-[:CONNECTS_TO {port, protocol}]->(s2:Service)` — inter-service communication
- `(s1:Service)-[:DEPENDS_ON {required:true}]->(s2:Service)` — health dependency
- `(h1:Host)-[:TUNNELS_TO {type, local_port, remote_port}]->(h2:Host)` — network tunnels
- `(cf:CodeFile)-[:PART_OF]->(s:Service)` — code ownership (manual mapping)

## Known Services (jetson)

| Service | Port | Note |
|---------|------|------|
| hermes-gateway | 8642 | Core agent gateway |
| hermes-api-socat | 8643→8642 | socat TCP forward |
| voice-proxy | 8647 | STT/TTS HTTP proxy |
| opencode-litellm | 4000 | LiteLLM Docker |
| opencode-webui | 3400 | OpenCode+ Web UI |
| llama-cpp | 8092 | Local LLM inference |
| neo4j | 7474, 7687 | Graph database |
| searchbox | 8024 | MCP search |
| localai | 8180 | Local AI Docker |
| voice-relay | 8089 | OpenAI-compatible voice relay |

## Known Hosts

| Host | IP | Type | Details |
|------|-----|------|---------|
| jetson (<YOUR_HOSTNAME>) | 192.168.0.48 | physical | aarch64, NVIDIA GB10, CUDA 13.0, Ubuntu 24.04 |
| vps | <YOUR_VPS_IP> | vps | Debian, sing-box VPN on :443 |
| phone | 10.4.213.x | phone | Honor, Android 16, USB-attached via ADB |

## Known Tunnels

| ID | Type | From | To | Ports |
|----|------|------|-----|-------|
| tun-ssh-reverse | ssh_reverse | vps | jetson | 8643→8642 |

## Pitfall: ARM64 ss -tlnp parsing

`ss -tlnp` on ARM64 Jetson produces different column alignment than x86_64.
The parser in `topology_ingest.py` may return 0 ports. Fix: architecture-specific
parsing or fallback to `netstat -tlnp`.

## Verification

```bash
python3 ~/.hermes/scripts/topology_ingest.py

curl -s -u neo4j:<YOUR_NEO4J_PASSWORD> -H 'Content-Type: application/json' \
  -d '{"statements":[{"statement":"MATCH (s:Service)-[:DEPLOYED_ON]->(h) RETURN s.name, h.name, s.status LIMIT 10"}]}' \
  http://localhost:7474/db/neo4j/tx/commit | python3 -m json.tool
```
