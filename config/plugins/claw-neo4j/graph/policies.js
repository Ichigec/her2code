/** Editorial compaction axes + knowledge merge — seeded once into Neo4j. */
export const COMPACTION_POLICIES = [
  {
    axis: "knowledge_merge",
    description:
      "Append-only dedupe in knowledge/*.json: same tool id increments confirmations and unions evidence; nodes are never deleted.",
  },
  {
    axis: "merge",
    description: "Two skills overlap on triggers and share procedure steps → merged draft under .compactor/drafts/.",
  },
  {
    axis: "prune",
    description: "Unreferenced skill or MCP → status pruned in graph; node retained for audit.",
  },
  {
    axis: "collapse",
    description: "Thin linux_layer tier with single inhabitant → collapse into parent layer.",
  },
  {
    axis: "rebudget",
    description: "Skill body > 8KB → split routing frontmatter from heavy body.",
  },
  {
    axis: "mcp-dedupe",
    description: "Duplicate MCP tool signatures → DUPLICATE_OF relationship between Tool nodes.",
  },
]
