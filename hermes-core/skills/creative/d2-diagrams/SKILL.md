---
name: d2-diagrams
description: Author, debug, and render D2 language diagrams (v0.7.x) — sequence diagrams, container/block diagrams, layered boards, and C4 models. Covers syntax pitfalls, note conversion, block string restrictions, and dagre layout workarounds unique to D2 v0.7.1.
trigger: user asks to create/fix/render D2 diagrams, mentions .d2 files, d2 binary, or architectural diagrams
tags: [d2, diagram, architecture, sequence-diagram, svg, c4]
---

# D2 Diagrams (v0.7.x)

Author, debug, and render D2 language diagram files using the `d2` CLI.

## Setup

```bash
# Locate the d2 binary
which d2

# Check version (critical — syntax changes between minor versions)
d2 version
```

## D2 v0.7.1 Syntax Reference

### 1. Note syntax (most common failure)

**WRONG** (v0.6 syntax, fails in v0.7.x):
```d2
note "Multi\nline\ntext": {
  style: { fill: "#fff9c4" stroke: "#f57f17" }
}
```

**RIGHT** — use `|md` block string with multi-line style block:
```d2
note: |md
  Line 1
  Line 2
  Line 3
| {
  style.fill: "#fff9c4"
  style.stroke: "#f57f17"
}
```

**Alternative** — separate style assignments (also works):
```d2
note: |md
  Content
|
note.style.fill: "#fff9c4"
```

### 2. Block strings and pipe characters

**CRITICAL**: `|md` block strings in D2 v0.7.1 CANNOT contain `|` (pipe) characters ANYWHERE — not even mid-line. The parser treats every `|` as a potential block string terminator.

**WRONG** (pipes inside content):
```d2
x: |md
  List[str|Dict]
  "a"|"b"
|
```

**RIGHT** (replace or rephrase):
```d2
x: |md
  List[str or Dict]
  "a" / "b"
|
```

This means markdown tables with pipe syntax, type union operators, or shell pipelines in examples cannot use `|md` block strings directly — rephrase the content.

### 3. Style attribute naming

**WRONG**: `fill:` / `stroke:` as direct attributes
```d2
myshape: "Label"
myshape.fill: "#fff3e0"      # FAILS
myshape.stroke: "#e65100"    # FAILS
```

**RIGHT**: prefix with `style.`
```d2
myshape.style.fill: "#fff3e0"
myshape.style.stroke: "#e65100"
```

Or use inline style blocks:
```d2
myshape: "Label" {
  style.fill: "#fff3e0"
  style.stroke: "#e65100"
}
```

### 3a. `<style>{}` inline block — AI generation artifact (CRITICAL)

**This is the #1 error pattern when AI generates D2 diagrams.** The model produces HTML/CSS-like `<style>{}` blocks directly after quoted labels. **Every single instance produces `unexpected text after double quoted string`.**

**WRONG** (AI-generated, NEVER compiles in D2 v0.7.x):
```d2
agent_loop: "Agent Conversation Loop" <style>{
  fill: "#e3f2fd"
  stroke: "#1565c0"
}
```
→ `err: unexpected text after double quoted string` at the `<style>` position
→ `err: unexpected map termination character }` at the closing `}`

Same pattern on arrows — also broken:
```d2
*.user -> *.aiagent <style>{
  stroke: "#0d47a1"
}: "message"
```

**RIGHT** — use a plain `{ }` block with `style.` prefixed attributes inside:
```d2
agent_loop: "Agent Conversation Loop" {
  style.fill: "#e3f2fd"
  style.stroke: "#1565c0"
}
```

**Detection — batch-check all .d2 files at once:**
```bash
for f in **/*.d2; do
  if grep -q '<style>' "$f"; then
    echo "❌ $f uses <style>{} (will not compile)"
  fi
done
# Or compile-check each file:
for f in *.d2; do
  d2 "$f" /dev/null 2>&1 >/dev/null && echo "✅ $f" || echo "❌ $f"
done
```

**Fix pattern (sed one-liner to repair AI-generated diagrams):**
```bash
# Remove <style> and convert bare fill/stroke to style.fill/style.stroke
sed -i 's/<style>{//g; s/  fill:/  style.fill:/g; s/  stroke:/  style.stroke:/g' file.d2
```
After sed, manually verify the `{` and `}` braces still balance.

### 4. Sequence diagrams — loop blocks

**BUG in D2 v0.7.1**: `loop:` blocks inside `shape: sequence_diagram` cause dagre layout crashes (`TypeError: Cannot convert undefined or null to object`) when there are multiple `*.` after-loop arrows referencing participants not previously used in direct arrows before the loop.

**Workaround**: Flatten sequence diagrams — remove the `loop:` block and place all arrows at the top level. Use comments to visually indicate loop sections.

**Works** (no loop block):
```d2
diagram: "Title" {
  shape: sequence_diagram
  a: "A"
  b: "B"
  c: "C"
  a -> b: "msg"
  b -> c: "msg2"
  c -> a: "msg3"
}
```

**Avoid** (may crash with post-loop arrows):
```d2
diagram: "Title" {
  shape: sequence_diagram
  a: "A"
  b: "B"
  c: "C"
  a -> b: "msg"
  loop: {
    *.a -> *.b: "loop"
  }
  *.b -> *.c: "after"   # May crash dagre layout
}
```

### 5. Participant definitions in sequence diagrams

Define all participants at the top of the `shape: sequence_diagram` scope before any arrows:

```d2
diagram: "Title" {
  shape: sequence_diagram
  user: "User"
  aiagent: "AIAgent\n(multiline label)"
  tool_ex: "Tool Executor"
  
  user -> aiagent: "message"
  aiagent -> tool_ex: "execute"
}
```

Do NOT use the old `*.user "User" -> *.aiagent "AIAgent"` inline-label syntax — that fails with "unexpected text after map" in v0.7.x.

### 6. Layers / Boards — filename quirks

When a diagram uses `layers:`, D2 generates separate SVGs per layer. Output filenames include literal `"` characters derived from layer names:
```d2
layers: {
  agent_dir "agent/": { ... }
}
```
→ Creates file `agent_dir "agent/".svg` (with literal quote chars in filename).

**Always sanitize output filenames** when deploying: strip quotes, replace `_` spaces and `/` with underscores.

### 7. `$` substitution in strings

D2 interprets `$VARIABLE` inside quoted strings as substitution syntax. Use `|md` block strings when labels must contain `$`:
```d2
# WRONG — $HERMES_HOME triggers substitution
bad_label: "Path: $HERMES_HOME/config"

# RIGHT — block string bypasses substitution
good_label: |md
  Path: $HERMES_HOME/config
|
```

### 8. Rendering

```bash
# Single SVG
d2 --layout dagre input.d2 output.svg

# Layers/boards produce a directory:
d2 --layout dagre input.d2 output.svg
# → output.svg (index) + output/ directory with per-layer SVGs
```

## Verification

```bash
# Compile check (render to /dev/null or /dev/null equivalent)
d2 --layout dagre file.d2 /dev/null 2>&1 | grep "success" && echo "OK" || echo "FAIL"

# Batch check all diagrams
for f in *.d2; do
  echo -n "$f: "
  d2 --layout dagre "$f" /dev/null 2>&1 | grep -c "success" > /dev/null && echo "OK" || echo "FAIL"
done
```

## Pitfalls

- **`<style>{}` inline blocks (AI generation artifact)**: the #1 error when AI writes D2. `label: "text" <style>{ fill: "..." }` produces `unexpected text after double quoted string`. Must use plain `{ style.fill: "..." }`. See §3a for batch detection and sed fix.
- **Pipe characters in block strings**: any `|` in `|md` content breaks the block string.
- **Loop blocks + post-loop arrows**: known dagre crash. Flatten to avoid.
- **Colon after note string**: `note "text": { ... }` fails. Must use block string format.
- **Inline style after `|` terminator**: `| { style.fill: "x" }` on one line fails. Must use multi-line style block.
- **`fill:` without `style.` prefix**: silently accepted by parser but produces no visual effect.
- **HTML-like tags in `|md`**: `<name>`, `<path>` etc. trigger markdown HTML parsing errors. Wrap in backticks or rephrase.
- **d2 CLI argument order**: `d2 layout=dot file.d2 out.svg` does NOT work — `layout=` must be `--layout` flag: `d2 --layout dot file.d2 out.svg`. Passing `layout=dot` as positional arg gives `err: bad usage: too many arguments`.
