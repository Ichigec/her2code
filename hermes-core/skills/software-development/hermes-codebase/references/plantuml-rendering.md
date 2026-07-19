# PlantUML Diagram Rendering (No Graphviz on Host)

When the host lacks Graphviz (`dot` binary) and there's no sudo access,
render PlantUML diagrams via Docker with a JDK image + apt-installed Graphviz.

## Render Command

```bash
# 1. Download plantuml.jar (one-time, ~26MB)
curl -fsSL -o /tmp/plantuml.jar \
  "https://github.com/plantuml/plantuml/releases/download/v1.2026.0/plantuml-1.2026.0.jar"

# 2. Copy jar into the working directory so Docker can volume-mount it
cp /tmp/plantuml.jar /home/user/dev/codemes/plantuml.jar

# 3. Render all diagrams from a multi-diagram .puml file
docker run --rm \
  -v /home/user/dev/codemes:/work \
  -w /work \
  eclipse-temurin:17-jdk \
  sh -c "apt-get update -qq > /dev/null 2>&1 && \
         apt-get install -y -qq graphviz > /dev/null 2>&1 && \
         java -jar plantuml.jar -tpng -o /work hermes-architecture.puml"

# 4. Clean up the jar from the working dir
rm /home/user/dev/codemes/plantuml.jar
```

Each `@startuml ... @enduml` block in the .puml file produces a separate PNG
named after the title in the `@startuml` directive.

## Why Docker Is Required

PlantUML component/package/use-case/object diagrams delegate layout to
Graphviz (`dot`). Without `dot` on PATH, PlantUML throws:
`java.io.IOException: Cannot run program "/opt/local/bin/dot"`.

Activity and state diagrams use PlantUML's built-in layout (smetana/ditaa)
and do NOT require Graphviz — but component diagrams do.

The `-Pplantuml.layout=smetana` flag forces the built-in layout engine, but
it produces broken/error images for complex component diagrams. Use Docker
with real Graphviz instead.

## PlantUML Syntax Pitfalls

### `agent` keyword cannot have a body block

```plantuml
# INVALID — PlantUML treats `agent` as a node type, not a container
agent "Parent Agent" as PARENT {
  ...
}

# VALID — use `rectangle` for labeled containers
rectangle "Parent Agent" as PARENT #E3F2FD
```

### `database` with nested `table` blocks is not supported

```plantuml
# INVALID — `database` is a single node, cannot contain `table` children
database "state.db" as DB {
  table "sessions" {
    + id (TEXT PK)
    --
    title (TEXT)
  }
}

# VALID — use `package` with `component` elements inside
package "state.db\nSQLite + WAL + FTS5" as DB #ECEFF1 {
  component "sessions\n(id, title, source)" as T_sessions
  component "messages (FTS5)\n(session_id, role, content)" as T_messages
}
```

### Multi-diagram files

A single `.puml` file can contain multiple `@startuml ... @enduml` blocks.
Each produces a separate output file named from the `@startuml` title:
`@startuml Hermes_Agent_Full_Architecture` → `Hermes_Agent_Full_Architecture.png`.

## Existing Architecture Diagrams

A comprehensive 10-diagram PlantUML file lives at:
`/home/user/dev/codemes/hermes-architecture.puml`

Diagrams included:
1. **Full Architecture** — top-level component view (Frontend → Gateway → Core → Tools → Providers → Persistence)
2. **Conversation Loop** — activity diagram of the main while-loop
3. **Tools Ecosystem** — 60+ tools grouped by category
4. **Provider Stack** — model config → adapters → credential pool → 20+ providers
5. **Gateway Platforms** — 30+ messaging platform adapters
6. **Delegation Depth** — subagent hierarchy with leaf/orchestrator roles
7. **Persistence State** — SQLite tables + file artifacts
8. **Plugins System** — 18 built-in plugins + hook registry
9. **Terminal Backends** — 7 execution environments
10. **Skill Lifecycle** — state diagram of skill discovery/usage/archival

These were verified against the actual codebase at `~/.hermes/hermes-agent/`
in July 2026. File sizes and counts shift over time — re-verify before
citing exact numbers.
