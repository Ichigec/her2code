#!/usr/bin/env bash
#
# Render PlantUML diagrams for the claw + composter + claw-compactor design.
# Outputs PNG files into ./out/ next to this script.
#
# Usage:
#   bash opencode+/opencode_claw/diagrams/render.sh
#
# Looks for plantuml in this order:
#   1. $PLANTUML_JAR (env override)
#   2. /tmp/plantuml.jar
#   3. plantuml on PATH

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/out"
mkdir -p "$OUT"

DIAGRAMS=(
  "logical.puml"
  "data-schemas.puml"
  "data-flow.puml"
  "sequence-claw.puml"
  "sequence-composter.puml"
  "sequence-full.puml"
  "sequence-compaction.puml"
)

# Use Smetana (pure-Java layout) by default so the script works without
# graphviz/dot installed. Override with LAYOUT="" to use the system dot.
LAYOUT_OPTS=( -Playout=smetana )
if [[ -n "${LAYOUT:-x}" && "${LAYOUT:-smetana}" == "dot" ]]; then
  LAYOUT_OPTS=()
fi

run_plantuml() {
  local file="$1"
  if [[ -n "${PLANTUML_JAR:-}" && -f "${PLANTUML_JAR}" ]]; then
    java -jar "${PLANTUML_JAR}" -tpng "${LAYOUT_OPTS[@]}" -o "$OUT" "$file"
  elif [[ -f /tmp/plantuml.jar ]]; then
    java -jar /tmp/plantuml.jar -tpng "${LAYOUT_OPTS[@]}" -o "$OUT" "$file"
  elif command -v plantuml >/dev/null 2>&1; then
    plantuml -tpng "${LAYOUT_OPTS[@]}" -o "$OUT" "$file"
  else
    echo "ERROR: plantuml not found. Set PLANTUML_JAR, drop plantuml.jar into /tmp, or install plantuml." >&2
    exit 1
  fi
}

cd "$HERE"
for f in "${DIAGRAMS[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "skip (missing): $f"
    continue
  fi
  echo "render: $f"
  run_plantuml "$f"
done

echo "done -> $OUT"
ls -la "$OUT"
