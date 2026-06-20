# `.compactor/` — audit trail of skill/MCP compaction

This directory is the **shared on-disk state** between two opencode agents:

- [`claw`](../../../.opencode/agent/claw.md) — stateless writer. Each session
  performs `discover → classify → detect → draft → log → exit`. Writes
  here, never reads from here.
- [`composter`](../../../.opencode/agent/composter.md) — stateful reader.
  Explains history to the user. Reads everything here, writes nothing.

The split (stateless writer + stateful reader) is the core invariant of
the design — it prevents the writer from reflecting on its own past
mistakes and entrenching them. See
[`AGENTS.md`](../AGENTS.md) §1 (Operating envelope) and §7 (Constraints).

## Layout

| Path | Producer | Consumer | Committed? |
|------|----------|----------|------------|
| `log.jsonl` | `claw` (append-only) | `composter` only | **no** — local journal, gitignored |
| `registry/integrations.<ts>.json` | `claw` discovery scanners | `claw` (next session, fresh discovery), `composter` | **no** — gitignored, may contain redacted env keys |
| `summaries/YYYY-MM-DD.md` | `claw` (append per session) | `composter`, humans, PR reviewers | **yes** |
| `drafts/<op-id>/SKILL.md` (and friends) | `claw` | humans (review), skills-manager (publish) | **yes** |

## Why two directories `summaries/` and `drafts/` are committed but not `log.jsonl`

- `log.jsonl` and `registry/*.json` are **machine state** for `composter`
  and for drift detection. They are large, frequently rewritten, and may
  contain redacted-but-still-noisy env-key inventories. Keep them local.
- `summaries/*.md` and `drafts/**` are **human artifacts** — daily digests
  and proposed skill content. These belong in PR review and in git history.

## How to read the journal as a human

Don't. Use `composter`:

```text
/agents composter
> explain compaction over the last 7 days
> what was action act_xxxxxx and why
> propose rollback for act_xxxxxx
```

If you really need to grep the raw journal locally:

```bash
jq -c 'select(.op == "merge")' opencode+/opencode_claw/.compactor/log.jsonl
```

## Schema validation

Every entry in `log.jsonl` must validate against
[`../schemas/compaction-action.schema.json`](../schemas/compaction-action.schema.json).

Every record in a `registry/*.json` snapshot must validate against
[`../schemas/integration-record.schema.json`](../schemas/integration-record.schema.json).

## See also

- [`../AGENTS.md`](../AGENTS.md) — runbook with full pipeline and constraints
- [`../PLAN.md`](../PLAN.md) — phase plan; this directory is part of Phase 0–1 infrastructure
- [`../opinion1.md`](../opinion1.md) — feasibility note motivating the human gate
