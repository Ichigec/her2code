# Searchbox MCP — Full API Reference

Server: searchbox v1.27.1
Endpoint: `http://127.0.0.1:8024/mcp` (Streamable HTTP MCP)
Transport: SSE (`text/event-stream`)
Auth: none (internal Docker network)

## Architecture

```
Docker container: openwebui-searchbox:local
├── Port 8024 → :8090 (native MCP HTTP/SSE — OpenHands, Cursor, Hermes)
├── Port 8023 → :8001 (mcpo OpenAPI bridge — OpenWebUI)
└── Code: /home/user/cursor/first/docker/searchbox/
    ├── MCP-zero/server.py     — MCP server (3 transports: stdio/HTTP/SSE)
    ├── MCP-zero/multi.py      — fan-out logic (round-robin + dedup)
    ├── MCP-zero/reader.py     — content extractor (pdf, docx, xlsx, pptx)
    └── MCP-zero/engines/      — 16 search engine adapters
```

## Session Setup

```bash
# Initialize (returns session ID in HTTP header)
SESSION=$(curl -s -D - 'http://127.0.0.1:8024/mcp' -X POST \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hermes","version":"1.0"}}}' \
  | grep -i 'mcp-session-id:' | awk '{print $2}' | tr -d '\r')

# Call any tool
curl -s "http://127.0.0.1:8024/mcp" -X POST \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"<tool>","arguments":{...}}}'
```

## Python Client (requests)

```python
import requests, json

BASE = "http://127.0.0.1:8024/mcp"
headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

# Initialize
r = requests.post(BASE, headers=headers, json={
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
               "clientInfo": {"name": "hermes", "version": "1.0"}}
})
sid = r.headers.get("mcp-session-id")
headers["Mcp-Session-Id"] = sid

# Call tool
r2 = requests.post(BASE, headers=headers, json={
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "search", "arguments": {"query": "example", "max_results": 5}}
})

# Parse SSE response
for line in r2.text.strip().split('\n'):
    if line.startswith('data: '):
        data = json.loads(line[6:])
        if 'result' in data:
            text = data['result']['content'][0]['text']
            results = json.loads(text)  # Second JSON decode
```

## Response Format

The `search` tool returns:
```json
{
  "query": "original query string",
  "engines_used": ["searxng", "arxiv", ...],
  "errors": {},
  "results": [
    {"title": "...", "url": "...", "description": "...", "engine": "searxng"}
  ],
  "per_engine": {
    "searxng": [...],
    "arxiv": [...]
  }
}
```

Single-engine tools (e.g., `search_arxiv`) return a flat list of results.

## All 18 Tools

### Primary
| Tool | Description | API key needed |
|------|-------------|---------------|
| `search` | Smart multi-search: fan-out to ALL available engines, deduped round-robin merge | — |
| `list_engines` | List all engines with descriptions and readiness | — |
| `search_status` | Engine readiness (which env vars are needed) | — |

### General Web
| Tool | Engine | Notes |
|------|--------|-------|
| `search_searxng` | SearXNG (meta) | **Priority engine.** Searches google/bing/wiki/github/arxiv/stackoverflow. Default source. |
| `search_duckduckgo` | DuckDuckGo | Free, no API key |
| `search_brave` | Brave Search | Commercial, free tier ~2k req/month | BRAVE_API_KEY |
| `search_google` | Google CSE | Commercial, free tier ~100 req/day | GOOGLE_API_KEY + GOOGLE_CX |
| `search_tavily` | Tavily | LLM-tuned, free tier ~1k req/month | TAVILY_API_KEY |

### Knowledge
| Tool | Engine |
|------|--------|
| `search_wikipedia` | Wikipedia article search + Wikidata entities |
| `search_wikidata` | Wikidata entity search (wbsearchentities) |

### Academic
| Tool | Engine |
|------|--------|
| `search_arxiv` | arXiv.org scientific preprints (Atom feed) |
| `search_crossref` | Crossref.org works search (DOI/title/author) |
| `search_openalex` | OpenAlex open scholarly graph |

### Developer
| Tool | Engine | Notes |
|------|--------|-------|
| `search_github` | GitHub repo/code | Optional GITHUB_TOKEN for higher rate limits |
| `search_hackernews` | HN via Algolia API | Stories + comments |
| `search_stackexchange` | StackExchange | Default site: stackoverflow |
| `search_pypi` | PyPI packages | Exact name: resolves via pypi.org; substring: uses search |
| `search_npm` | npm registry | registry.npmjs.org search |

## Engine Reliability (Tested June 2026)

| Engine | Reliability | Best for | Weakness |
|--------|------------|----------|----------|
| **arxiv** | ★★★★★ | Academic papers, preprints | Only papers, no web content |
| **github** | ★★★★★ | Code, repos, implementations | Only GitHub content |
| **wikipedia** | ★★★★☆ | Definitions, overview articles | Limited depth |
| **duckduckgo** | ★★★★☆ | General web search | Similar to SearXNG |
| **searxng** | ★★★☆☆ | General web (meta-search) | **Noisy for niche academic terms** — returns unrelated retail/commercial results for paper titles |
| **hackernews** | ★★★☆☆ | Community discussions | Content limited to HN topics |
| **crossref** | ★★★☆☆ | DOI/title metadata | No full-text |
| **openalex** | ★★★☆☆ | Scholarly graph | Coverage varies by field |

### Key finding
For academic queries (paper titles, author names, method names like "DRPO", "FlowDPPO"), **SearXNG is unreliable** — frequently returns unrelated commercial content. Use `engines=["arxiv", "searxng"]` and treat arxiv as the primary signal, searxng as supplementary.

## Pitfalls

1. **SSE double-JSON-decode** — Results are wrapped: SSE event → JSON body → `result.content[0].text` is a JSON string → must be decoded again. This is two layers of JSON.

2. **Session persistence** — `$SESSION` variable from initialize persists only within a single shell process. In subagents using `terminal()`, each call is a fresh shell — either pass the session ID explicitly or re-initialize per call.

3. **Engine gating** — Brave/Google/Tavily are gated by env vars. In the Docker container, these may be unset → the engine is listed but returns errors. Use `search_status` to check readiness.

4. **Rate limiting** — No server-side rate limiting, but some engines (Google, Brave) have API-side quotas. SearxNG is unthrottled within the local Docker network.

5. **SearXNG local instance** — Uses the SearXNG container in the same Docker compose stack. If SearXNG is down, `search` degrades but other engines still work.
