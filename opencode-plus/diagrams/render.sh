#!/usr/bin/env bash
#
# Render OpenCode+ logical + sequence diagrams to ./out/*.png
#
# Usage:
#   bash opencode+/diagrams/render.sh
#
# plantuml lookup order: $PLANTUML_JAR → /tmp/plantuml.jar → plantuml on PATH

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/out"
mkdir -p "$OUT"

DIAGRAMS=( "logical.puml" "sequence.puml" )

# Smetana = pure-Java layout, works without graphviz/dot.
LAYOUT_OPTS=( -Playout=smetana )
[[ "${LAYOUT:-smetana}" == "dot" ]] && LAYOUT_OPTS=()

run_plantuml() {
  local file="$1"
  if [[ -n "${PLANTUML_JAR:-}" && -f "${PLANTUML_JAR}" ]]; then
    java -jar "${PLANTUML_JAR}" -tpng "${LAYOUT_OPTS[@]}" -o "$OUT" "$file"
  elif [[ -f /tmp/plantuml.jar ]]; then
    java -jar /tmp/plantuml.jar -tpng "${LAYOUT_OPTS[@]}" -o "$OUT" "$file"
  elif command -v plantuml >/dev/null 2>&1; then
    plantuml -tpng "${LAYOUT_OPTS[@]}" -o "$OUT" "$file"
  else
    echo "ERROR: plantuml not found. Set PLANTUML_JAR or drop plantuml.jar into /tmp." >&2
    exit 1
  fi
}

cd "$HERE"
for f in "${DIAGRAMS[@]}"; do
  [[ -f "$f" ]] || { echo "skip (missing): $f"; continue; }
  echo "render: $f"
  run_plantuml "$f"
done

echo "done -> $OUT"
ls -la "$OUT"
