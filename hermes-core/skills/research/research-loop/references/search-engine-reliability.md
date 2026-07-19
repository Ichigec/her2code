# Search Engine Reliability — Lessons Learned (2026-06-24)

## SearxNG: DO NOT USE for technical/academic queries

SearxNG is a meta-search engine that tokenizes queries and distributes across multiple backends. For technical queries containing common English words, it returns completely irrelevant results:

| Query | Expected | Actual result |
|-------|----------|---------------|
| "active listening requirements elicitation" | Academic papers, techniques | Premier League standings |
| "facilitation techniques business analyst" | Workshop methods | Electric vehicle database |
| "agent persona for interviewing" | AI research | Mail.ru Agent, CS:GO skins |
| "SPIN questioning framework" | Sales methodology | Kubernetes vs Nomad comparison |
| "5 whys root cause analysis" | Problem-solving technique | Russian TV channel, school #5 |

### What works instead

| Source type | Use | API/Endpoint |
|-------------|-----|-------------|
| Academic papers | crossref, openalex | MCP searchbox `search` tool with `engines: ["crossref", "openalex"]` |
| Code/implementations | GitHub | MCP `search_github` |
| Paper preprints | arxiv | Direct API: `https://export.arxiv.org/api/query?...` |
| Community | HackerNews | MCP `search_hackernews` |
| Russian sources | habr.com | Direct curl: `curl -sL "https://habr.com/ru/search/?q=..."` |
| Wikipedia | Wikipedia | MCP `search_wikipedia` — works for exact topic names |

### Rule

**NEVER use SearxNG for multi-word technical queries.** It is only usable for single-entity lookups (company names, product names). For everything else, use the source-specific APIs listed above.

## Multi-Language Paraphrasing (v3.0)

Always generate 4-6 search queries per RQ:
- 2-3 paraphrases in the original language
- 1-2 translations + paraphrases in English
- 1-2 translations + paraphrases in Russian

This prevents SearxNG noise and catches results that monolingual search misses.
