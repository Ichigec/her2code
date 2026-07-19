#!/usr/bin/env python3
"""
System Topology Ingestion Script
--------------------------------
Collects current system topology (Host, Service, Port, Container, Tunnel nodes)
and ingests into Neo4j via HTTP API.

Usage:
    python3 topology_ingest.py           # Full ingestion (idempotent — MERGE)
    python3 topology_ingest.py --check   # Verify graph is non-empty

Requirements:
    - Python 3.12+ (stdlib only: json, subprocess, os, sys)
    - Neo4j running on localhost:7474 (neo4j:<YOUR_NEO4J_PASSWORD>)
    - curl available on PATH
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

NEO4J_URL = "http://localhost:7474/db/neo4j/tx/commit"
NEO4J_AUTH = "neo4j:<YOUR_NEO4J_PASSWORD>"

# Known hosts (manually curated)
HOSTS = {
    "jetson": {
        "name": "<YOUR_HOSTNAME>",
        "type": "physical",
        "os": "Linux (Ubuntu 24.04)",
        "arch": "aarch64",
        "gpu": "NVIDIA GB10, CUDA 13.0",
        "local_ips": ["192.168.0.48"],
    },
    "vps": {
        "name": "vps",
        "type": "vps",
        "ip": "<YOUR_VPS_IP>",
        "os": "Debian",
        "arch": "x86_64",
        "local_ips": ["<YOUR_VPS_IP>"],
    },
    "phone": {
        "name": "phone",
        "type": "phone",
        "ip": "10.4.213.x",
        "os": "Android 16 (Honor)",
        "arch": "aarch64",
        "local_ips": ["10.4.213.x"],
    },
}

# Known services (manually curated — not all visible via docker/ss)
KNOWN_SERVICES = [
    {"name": "hermes-gateway",        "host": "jetson", "port": 8642, "health_endpoint": "http://localhost:8642/health"},
    {"name": "hermes-api-socat",      "host": "jetson", "port": 8643, "description": "socat forwarding 8643→8642"},
    {"name": "voice-proxy",           "host": "jetson", "port": 8647, "process_name": "voice_proxy.py", "repo": "~/dev/Opencode/"},
    {"name": "opencode-litellm",      "host": "jetson", "port": 4000, "repo": "~/cursor/opencode+/"},
    {"name": "opencode-webui",        "host": "jetson", "port": 3400, "process_name": "opencode"},
    {"name": "llama-cpp",             "host": "jetson", "port": 8092, "process_name": "llama-server"},
    {"name": "neo4j",                 "host": "jetson", "port": 7474, "health_endpoint": "http://localhost:7474"},
    {"name": "neo4j-bolt",            "host": "jetson", "port": 7687},
    {"name": "searchbox",             "host": "jetson", "port": 8024},
    {"name": "localai",               "host": "jetson", "port": 8180},
    {"name": "voice-relay",           "host": "jetson", "port": 8089},
    {"name": "sing-box-vpn",          "host": "vps",   "port": 443},
]

# Known tunnels
KNOWN_TUNNELS = [
    {
        "id": "tun-ssh-reverse",
        "type": "ssh_reverse",
        "source_host": "vps",
        "target_host": "jetson",
        "local_port": 8643,
        "remote_port": 8642,
    },
]

# Extra services derived from docker containers
# Map well-known image names → service names
DOCKER_SERVICE_MAP = {
    "litellm": "opencode-litellm",
    "localai": "localai",
    "neo4j": "neo4j",
    "searchbox": "searchbox",
    "open-webui": "open-webui",
    "searxng": "searxng",
    "hermes-test": "hermes-test",
}


# ── Data Collection ───────────────────────────────────────────────────────────

def run(cmd: list[str], timeout: int = 15) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def curl_neo4j(payload: dict) -> dict:
    """Execute Cypher via Neo4j HTTP API using curl."""
    body = json.dumps(payload)
    result = subprocess.run(
        [
            "curl", "-s", "-u", NEO4J_AUTH,
            "-H", "Content-Type: application/json",
            "-d", body,
            NEO4J_URL,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr}")
    data = json.loads(result.stdout)
    if data.get("errors"):
        raise RuntimeError(f"Neo4j errors: {data['errors']}")
    return data


def neo4j_exec(statement: str, params: dict = None) -> dict:
    """Execute a single Cypher statement."""
    return curl_neo4j({
        "statements": [{"statement": statement, "parameters": params or {}}]
    })


def neo4j_multi(statements: list[dict]) -> dict:
    """Execute multiple Cypher statements in one transaction."""
    return curl_neo4j({"statements": statements})


def collect_host_info() -> dict:
    """Collect host information for the current (jetson) host."""
    info = dict(HOSTS["jetson"])

    # Detect all local IPs
    out = run(["ip", "addr", "show"])
    ips = []
    for line in out.split("\n"):
        m = re.search(r"inet\s+([\d.]+)/", line)
        if m and not m.group(1).startswith("127."):
            ips.append(m.group(1))
    if ips:
        info["local_ips"] = ips
    else:
        # Fallback
        info["local_ips"] = ["192.168.0.48"]

    info["ip"] = info["local_ips"][0]
    return info


def collect_docker_containers() -> list[dict]:
    """Collect running Docker containers."""
    out = run(["docker", "ps", "--format", "{{.Names}}\\t{{.Image}}\\t{{.Ports}}\\t{{.Status}}"])
    containers = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, image, ports, status = parts[0], parts[1], parts[2], parts[3]
        containers.append({
            "name": name,
            "image": image,
            "ports": ports if ports else "",
            "status": status,
        })
    return containers


def collect_listen_ports() -> list[dict]:
    """Collect LISTEN ports from ss -tlnp."""
    out = run(["ss", "-tlnp"])
    ports = []
    for line in out.split("\n"):
        # Parse lines like: LISTEN 0 512 127.0.0.1:3400 0.0.0.0:* users:(("opencode",pid=12583,fd=21))
        if not line.startswith("LISTEN"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        addr_port = parts[4]  # e.g. 127.0.0.1:3400 or [::]:4000
        # Handle IPv6
        if addr_port.startswith("["):
            # [::]:4000
            m = re.search(r"\]:(\d+)$", addr_port)
        else:
            m = re.search(r":(\d+)$", addr_port)
        if not m:
            continue
        port_num = int(m.group(1))

        # Determine protocol
        if ":" in addr_port and addr_port.count(":") > 1:
            protocol = "tcp6"
        else:
            protocol = "tcp"

        # Check if exposed (not 127.0.0.1)
        exposed = not addr_port.startswith("127.") and not addr_port.startswith("[")

        # Try to extract process name
        proc_match = re.search(r'users:\(\("([^"]+)"', line)
        process = proc_match.group(1) if proc_match else None

        ports.append({
            "number": port_num,
            "protocol": protocol,
            "exposed": exposed,
            "process": process,
        })
    return ports


def collect_systemd_services() -> list[dict]:
    """Collect running user systemd services."""
    out = run(["systemctl", "--user", "list-units", "--type=service",
               "--state=running", "--no-legend", "--no-pager"])
    services = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 1:
            unit_name = parts[0]
            if unit_name.endswith(".service"):
                services.append({
                    "name": unit_name.replace(".service", ""),
                    "unit": unit_name,
                    "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                })
    return services


def collect_container_to_ports(containers: list[dict], ports: list[dict]) -> list[dict]:
    """Map docker containers to ports using port strings."""
    mappings = []
    for c in containers:
        port_str = c["ports"]
        if not port_str:
            continue
        # Parse port strings like:
        # "0.0.0.0:4000->4000/tcp, [::]:4000->4000/tcp"
        # "127.0.0.1:8024->8090/tcp"
        found = set()
        for part in port_str.split(","):
            part = part.strip()
            # Extract host port
            m = re.search(r"([\d.]+):(\d+)->\d+", part)
            if m:
                host_ip = m.group(1)
                host_port = int(m.group(2))
                if host_port not in found:
                    found.add(host_port)
                    mappings.append({
                        "container": c["name"],
                        "image": c["image"],
                        "port": host_port,
                        "bind_ip": host_ip,
                    })
    return mappings


# ── Neo4j Schema Setup ────────────────────────────────────────────────────────

SCHEMA_SETUP = [
    # Constraints
    """CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE""",
    """CREATE CONSTRAINT host_name IF NOT EXISTS FOR (h:Host) REQUIRE h.name IS UNIQUE""",
    """CREATE CONSTRAINT port_id IF NOT EXISTS FOR (p:Port) REQUIRE (p.number, p.protocol) IS NODE KEY""",
    """CREATE CONSTRAINT container_name IF NOT EXISTS FOR (c:Container) REQUIRE c.name IS UNIQUE""",
    """CREATE CONSTRAINT tunnel_id IF NOT EXISTS FOR (t:Tunnel) REQUIRE t.id IS UNIQUE""",
    # Indexes for performance
    """CREATE INDEX service_host IF NOT EXISTS FOR (s:Service) ON (s.host)""",
    """CREATE INDEX port_exposed IF NOT EXISTS FOR (p:Port) ON (p.exposed)""",
    """CREATE INDEX container_image IF NOT EXISTS FOR (c:Container) ON (c.image)""",
]


def setup_schema():
    """Ensure Neo4j constraints and indexes exist."""
    for stmt in SCHEMA_SETUP:
        try:
            neo4j_exec(stmt)
        except RuntimeError as e:
            # Constraint may already exist — that's fine
            err_str = str(e)
            if "already exists" in err_str or "existing" in err_str.lower():
                continue
            print(f"  [WARN] Schema statement failed: {e}", file=sys.stderr)


# ── Ingestion Functions ───────────────────────────────────────────────────────

def ingest_hosts():
    """Ingest Host nodes."""
    host_info = collect_host_info()
    local_ips = json.dumps(host_info.get("local_ips", []))

    # Current host (jetson)
    neo4j_exec("""
        MERGE (h:Host {name: $name})
        SET h.ip = $ip,
            h.type = $type,
            h.os = $os,
            h.arch = $arch,
            h.gpu = $gpu,
            h.local_ips = $local_ips,
            h.updated_at = timestamp()
    """, {
        "name": host_info["name"],
        "ip": host_info["ip"],
        "type": host_info["type"],
        "os": host_info["os"],
        "arch": host_info["arch"],
        "gpu": host_info.get("gpu", ""),
        "local_ips": local_ips,
    })

    # VPS host
    vps = HOSTS["vps"]
    neo4j_exec("""
        MERGE (h:Host {name: $name})
        SET h.ip = $ip,
            h.type = $type,
            h.os = $os,
            h.arch = $arch,
            h.updated_at = timestamp()
    """, {
        "name": vps["name"],
        "ip": vps["ip"],
        "type": vps["type"],
        "os": vps["os"],
        "arch": vps["arch"],
    })

    # Phone host
    phone = HOSTS["phone"]
    neo4j_exec("""
        MERGE (h:Host {name: $name})
        SET h.ip = $ip,
            h.type = $type,
            h.os = $os,
            h.arch = $arch,
            h.updated_at = timestamp()
    """, {
        "name": phone["name"],
        "ip": phone["ip"],
        "type": phone["type"],
        "os": phone["os"],
        "arch": phone["arch"],
    })

    return host_info


def ingest_containers():
    """Ingest Container nodes from docker ps."""
    containers = collect_docker_containers()
    for c in containers:
        neo4j_exec("""
            MERGE (c:Container {name: $name})
            SET c.image = $image,
                c.ports = $ports,
                c.status = $status,
                c.updated_at = timestamp()
        """, {
            "name": c["name"],
            "image": c["image"],
            "ports": c["ports"],
            "status": c["status"],
        })
    return containers


def ingest_ports():
    """Ingest Port nodes from ss -tlnp."""
    ports = collect_listen_ports()
    seen = set()
    for p in ports:
        key = (p["number"], p["protocol"])
        if key in seen:
            continue
        seen.add(key)

        desc = None
        if p.get("process"):
            desc = f"Process: {p['process']}"

        neo4j_exec("""
            MERGE (p:Port {number: $number, protocol: $protocol})
            SET p.exposed = $exposed,
                p.description = $description,
                p.updated_at = timestamp()
        """, {
            "number": p["number"],
            "protocol": p["protocol"],
            "exposed": p["exposed"],
            "description": desc,
        })
    return ports


def ingest_services(host_info: dict, containers: list[dict], ports: list[dict]):
    """Ingest Service nodes (known + docker-derived) and their relationships."""
    # Map docker containers to service names
    docker_to_service = {}
    for c in containers:
        svc_name = DOCKER_SERVICE_MAP.get(c["name"])
        if not svc_name:
            # Check image name
            for img_prefix, mapped_name in DOCKER_SERVICE_MAP.items():
                if img_prefix in c["image"]:
                    svc_name = mapped_name
                    break
        if not svc_name:
            svc_name = c["name"]  # Use container name as service name
        docker_to_service[c["name"]] = svc_name

    # Find container-to-port mappings
    container_ports = collect_container_to_ports(containers, ports)
    container_ports_map = {}
    for m in container_ports:
        container_ports_map.setdefault(m["container"], []).append(m["port"])

    # Build a set of service names from KNOWN_SERVICES
    known_names = {s["name"] for s in KNOWN_SERVICES}
    # Add docker-derived services
    for c in containers:
        svc_name = docker_to_service.get(c["name"], c["name"])
        known_names.add(svc_name)

    # Build service details dict
    svc_details = {}
    for s in KNOWN_SERVICES:
        svc_details[s["name"]] = s

    # Add docker-derived services that aren't in KNOWN_SERVICES
    for c in containers:
        svc_name = docker_to_service.get(c["name"], c["name"])
        if svc_name not in svc_details:
            svc_details[svc_name] = {
                "name": svc_name,
                "host": "jetson",
                "port": None,
            }

    # Ingest each service
    host_name = host_info["name"]
    for svc_name, svc in svc_details.items():
        port = svc.get("port")
        host = svc.get("host", "jetson")
        target_host = host_name if host == "jetson" else host

        neo4j_exec("""
            MERGE (s:Service {name: $name})
            SET s.host = $host,
                s.port = $port,
                s.status = $status,
                s.health_endpoint = $health_endpoint,
                s.repo = $repo,
                s.language = $language,
                s.process_name = $process_name,
                s.description = $description,
                s.updated_at = timestamp()
        """, {
            "name": svc_name,
            "host": target_host,
            "port": port,
            "status": "running",
            "health_endpoint": svc.get("health_endpoint"),
            "repo": svc.get("repo"),
            "language": svc.get("language"),
            "process_name": svc.get("process_name"),
            "description": svc.get("description"),
        })

        # DEPLOYED_ON relationship
        neo4j_exec("""
            MATCH (s:Service {name: $svc_name})
            MERGE (h:Host {name: $host_name})
            MERGE (s)-[:DEPLOYED_ON]->(h)
        """, {
            "svc_name": svc_name,
            "host_name": target_host,
        })

        # If service has a port, create EXPOSES_PORT relationship
        if port:
            neo4j_exec("""
                MATCH (s:Service {name: $svc_name})
                MERGE (p:Port {number: $port_num, protocol: 'tcp'})
                MERGE (s)-[:EXPOSES_PORT]->(p)
            """, {
                "svc_name": svc_name,
                "port_num": port,
            })

        # If service runs in a container, create RUNS_IN relationship
        for c in containers:
            mapped_name = docker_to_service.get(c["name"], c["name"])
            if mapped_name == svc_name:
                neo4j_exec("""
                    MATCH (s:Service {name: $svc_name})
                    MERGE (c:Container {name: $container_name})
                    MERGE (s)-[:RUNS_IN]->(c)
                """, {
                    "svc_name": svc_name,
                    "container_name": c["name"],
                })

    # Add docker-derived services that aren't in the known list
    for c in containers:
        svc_name = docker_to_service.get(c["name"], c["name"])

        # Create Port nodes and EXPOSES_PORT for container ports
        if c["name"] in container_ports_map:
            for port_num in container_ports_map[c["name"]]:
                neo4j_exec("""
                    MATCH (s:Service {name: $svc_name})
                    MERGE (p:Port {number: $port_num, protocol: 'tcp'})
                    MERGE (s)-[:EXPOSES_PORT]->(p)
                """, {
                    "svc_name": svc_name,
                    "port_num": port_num,
                })

    return svc_details


def ingest_dependencies():
    """Ingest known service-to-service dependencies."""
    deps = [
        # Hermes gateway depends on service mesh
        ("hermes-api-socat", "hermes-gateway", 8642, "tcp"),
        ("voice-proxy", "hermes-gateway", 8642, "tcp"),
        # OpenCode+ services
        ("opencode-webui", "opencode-litellm", 4000, "tcp"),
        ("opencode-litellm", "llama-cpp", 8092, "tcp"),
        # Voice pipeline
        ("voice-proxy", "voice-relay", 8089, "tcp"),
        # Search
        ("searchbox", "neo4j", 7687, "tcp"),
    ]

    for source, target, port, protocol in deps:
        neo4j_exec("""
            MATCH (s1:Service {name: $source})
            MERGE (s2:Service {name: $target})
            MERGE (s1)-[:CONNECTS_TO {port: $port, protocol: $protocol}]->(s2)
            MERGE (s1)-[:DEPENDS_ON {required: true}]->(s2)
        """, {
            "source": source,
            "target": target,
            "port": port,
            "protocol": protocol,
        })


def ingest_tunnels():
    """Ingest Tunnel nodes and TUNNELS_TO relationships."""
    for t in KNOWN_TUNNELS:
        neo4j_exec("""
            MERGE (tun:Tunnel {id: $id})
            SET tun.type = $type,
                tun.local_port = $local_port,
                tun.remote_port = $remote_port,
                tun.target_host = $target_host,
                tun.updated_at = timestamp()
        """, {
            "id": t["id"],
            "type": t["type"],
            "local_port": t["local_port"],
            "remote_port": t["remote_port"],
            "target_host": t["target_host"],
        })

        # TUNNELS_TO relationship
        neo4j_exec("""
            MATCH (tun:Tunnel {id: $id})
            MERGE (h1:Host {name: $source_host})
            MERGE (h2:Host {name: $target_host})
            MERGE (h1)-[:TUNNELS_TO {type: $tun_type, local_port: $local_port, remote_port: $remote_port}]->(h2)
        """, {
            "id": t["id"],
            "source_host": t["source_host"],
            "target_host": t["target_host"],
            "tun_type": t["type"],
            "local_port": t["local_port"],
            "remote_port": t["remote_port"],
        })


def ingest_all():
    """Run all ingestion steps."""
    print("[topology_ingest] Setting up Neo4j schema...", flush=True)
    setup_schema()

    print("[topology_ingest] Ingesting Hosts...", flush=True)
    host_info = ingest_hosts()
    print(f"  → Host: {host_info['name']} ({host_info['ip']})", flush=True)

    print("[topology_ingest] Ingesting Docker Containers...", flush=True)
    containers = ingest_containers()
    print(f"  → {len(containers)} containers found", flush=True)

    print("[topology_ingest] Ingesting Ports...", flush=True)
    ports = ingest_ports()
    print(f"  → {len(ports)} ports found", flush=True)

    print("[topology_ingest] Ingesting Services & Relationships...", flush=True)
    svc_details = ingest_services(host_info, containers, ports)
    print(f"  → {len(svc_details)} services ingested", flush=True)

    print("[topology_ingest] Ingesting Dependencies...", flush=True)
    ingest_dependencies()
    print("  → Dependencies created", flush=True)

    print("[topology_ingest] Ingesting Tunnels...", flush=True)
    ingest_tunnels()
    print("  → Tunnels created", flush=True)

    print("[topology_ingest] Done.", flush=True)


# ── Check Mode ────────────────────────────────────────────────────────────────

def check_graph():
    """Verify the graph has topology data (non-empty)."""
    errors = []

    try:
        result = neo4j_exec("MATCH (h:Host) RETURN count(h) AS cnt")
        host_count = result["results"][0]["data"][0]["row"][0]
        print(f"  Host nodes: {host_count}", flush=True)
        if host_count == 0:
            errors.append("No Host nodes found — run full ingestion first")
    except Exception as e:
        errors.append(f"Cannot query Host nodes: {e}")
        host_count = 0

    try:
        result = neo4j_exec("MATCH (s:Service) RETURN count(s) AS cnt")
        svc_count = result["results"][0]["data"][0]["row"][0]
        print(f"  Service nodes: {svc_count}", flush=True)
        if svc_count == 0:
            errors.append("No Service nodes found — run full ingestion first")
    except Exception as e:
        errors.append(f"Cannot query Service nodes: {e}")
        svc_count = 0

    try:
        result = neo4j_exec("MATCH (p:Port) RETURN count(p) AS cnt")
        port_count = result["results"][0]["data"][0]["row"][0]
        print(f"  Port nodes: {port_count}", flush=True)
    except Exception as e:
        errors.append(f"Cannot query Port nodes: {e}")
        port_count = 0

    try:
        result = neo4j_exec("MATCH (c:Container) RETURN count(c) AS cnt")
        cont_count = result["results"][0]["data"][0]["row"][0]
        print(f"  Container nodes: {cont_count}", flush=True)
    except Exception as e:
        errors.append(f"Cannot query Container nodes: {e}")
        cont_count = 0

    try:
        result = neo4j_exec("MATCH (t:Tunnel) RETURN count(t) AS cnt")
        tun_count = result["results"][0]["data"][0]["row"][0]
        print(f"  Tunnel nodes: {tun_count}", flush=True)
    except Exception as e:
        errors.append(f"Cannot query Tunnel nodes: {e}")
        tun_count = 0

    # Relationship checks
    try:
        result = neo4j_exec("MATCH ()-[r:DEPLOYED_ON]->() RETURN count(r) AS cnt")
        rel_count = result["results"][0]["data"][0]["row"][0]
        print(f"  DEPLOYED_ON rels: {rel_count}", flush=True)
    except Exception as e:
        errors.append(f"Cannot query DEPLOYED_ON: {e}")

    try:
        result = neo4j_exec("MATCH ()-[r:EXPOSES_PORT]->() RETURN count(r) AS cnt")
        rel_count = result["results"][0]["data"][0]["row"][0]
        print(f"  EXPOSES_PORT rels: {rel_count}", flush=True)
    except Exception as e:
        errors.append(f"Cannot query EXPOSES_PORT: {e}")

    if errors:
        print("\n[FAIL] Topology graph check failed:", flush=True)
        for e in errors:
            print(f"  ✗ {e}", flush=True)
        return 1
    else:
        total = host_count + svc_count + port_count + cont_count + tun_count
        print(f"\n[OK] Topology graph healthy — {total} total nodes", flush=True)
        return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if "--check" in sys.argv:
        print("[topology_ingest] --check: verifying topology graph...", flush=True)
        return check_graph()

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0

    try:
        ingest_all()
        return 0
    except RuntimeError as e:
        print(f"[topology_ingest] ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[topology_ingest] FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
