# Rendering D2 Architectural Diagrams to SVG/PNG/PDF/PPTX

When architecture-as-code artifacts exist as **D2 language** (`.d2`) files — the
declarative diagramming language from [d2lang.com](https://d2lang.com) — use this
reference to install the renderer, fix syntax, and produce output formats suitable
for documentation, presentation, or import into DrawIO / PlantUML.

## Quick Install (d2 CLI)

```bash
# Linux ARM64 — download latest release
curl -fsSL -o /tmp/d2.tar.gz \
  "https://github.com/terrastruct/d2/releases/download/v$(curl -sL https://api.github.com/repos/terrastruct/d2/releases/latest | grep tag_name | grep -oP '\d+\.\d+\.\d+')/d2-v$(curl -sL https://api.github.com/repos/terrastruct/d2/releases/latest | grep tag_name | grep -oP '\d+\.\d+\.\d+')-linux-arm64.tar.gz"
tar -xzf /tmp/d2.tar.gz -C /tmp/
cp /tmp/d2-v*/bin/d2 ~/.local/bin/d2

# Verify
d2 version
```

Other platforms: replace `linux-arm64` with `linux-amd64`, `macos-amd64`, or
`macos-arm64`. No sudo needed — extract anywhere in `$PATH`.

## Render to SVG (default layout)

```bash
d2 input.d2 output.svg
d2 --layout dagre input.d2 output.svg   # dagre layout for directed graphs
d2 --layout elk input.d2 output.svg      # ELK layout for layered diagrams
```

## Supported Output Formats

| Format | Command | Notes |
|--------|---------|-------|
| SVG | `d2 in.d2 out.svg` | Vector, editable, embeddable |
| PNG | `d2 in.d2 out.png --scale 2` | Raster, `--scale` for HiDPI |
| PDF | `d2 in.d2 out.pdf` | Print-ready |
| PPTX | `d2 in.d2 out.pptx` | Editable in PowerPoint/Google Slides |
| GIF | `d2 in.d2 out.gif` | Animated (sequence diagrams) |
| TXT | `d2 in.d2 out.txt` | ASCII-art fallback |

## Syntax Migration: `<style>{…}` → Modern D2 v0.7.x

Many architecture `.d2` files use an **old inline-style syntax** not supported
by d2 v0.7.x. Key transformations:

### 1. Shape Definitions

**Old syntax (broken in v0.7.1):**
```
person.cli_user "CLI User" <style>{
  shape: person
  fill: "#e8f5e9"
  stroke: "#2e7d32"
  font-size: 14
}
```

**Modern D2:**
```
person.cli_user: "CLI User" {
  shape: person
  style: {
    fill: "#e8f5e9"
    stroke: "#2e7d32"
    "font-size": 14
  }
}
```

**Rules:**
- Add `:` between key and label: `key: "Label"`
- Replace `<style>{` with `{`
- Move `shape: xxx` to top-level (not under `style:`)
- Put visual attributes (`fill`, `stroke`, `font-size`, `bold`, `italic`) under `style: {}`
- Remove the closing `}` that matched `<style>{` — the new `}` closes the shape block

### 2. Inline Shape Attribute Lines

**Old:**
```
hermes_agent.shape: rounded_box
filesystem.shape: cylinders
```

**Fix:** Replace with valid D2 shape names:
- `rounded_box` → `rectangle` (use `border-radius` style for rounded corners)
- `cylinders` → `cylinder`
- Valid shapes: `rectangle`, `square`, `circle`, `ellipse`, `hexagon`, `cloud`,
  `cylinder`, `person`, `diamond`, `triangle`, `bolt`, `pill`, `step`, `class`,
  `sql_table`, `image`, `text`

### 3. Arrows with Labels and Styles

**Old:**
```
*.user "User" -> *.aiagent "AIAgent\n(run_agent.py)" <style>{
  stroke: "#0d47a1"
}: "send_message / run_conversation()"
```

**Strategy:** Define participants first in the outer scope, then use simple arrows:

```
*.user: "User"
*.aiagent: "AIAgent"
*.aiagent: {
  shape: rounded_box
}

*.user -> *.aiagent: "send_message / run_conversation()" {
  style.stroke: "#0d47a1"
}
```

The `*.` prefix references participants from the parent scope — works in v0.7.1.

### 4. Multi-line Notes with Style

**Old:**
```
note "Key Facts:
• run.py: 20,272 lines
• 15+ platform adapters
• SCHEMA_VERSION = 15" <style>{
  fill: "#fff9c4"
  stroke: "#f57f17"
}
```

**Fix:** Use **block string** (`|md`) syntax — avoids multi-line quoted-string bugs:

```
note: |md
  Key Facts:
  • run.py: 20,272 lines
  • 15+ platform adapters
  • SCHEMA_VERSION = 15
| {
  style.fill: "#fff9c4"
  style.stroke: "#f57f17"
}
```

**IMPORTANT:** `|md` block strings cannot contain `|` characters anywhere — even
mid-line. If your text has pipes (e.g. `str | None`, `"user" | "project"`,
markdown tables), replace them with alternatives (e.g. `str or None`,
`"user" / "project"`, bullet lists instead of tables) or use a different note
format.

### 5. Sequence Diagrams with `loop:` Blocks

**Warning:** `loop:` blocks in D2 sequence diagrams can cause **dagre layout
crashes** when post-loop arrows reference participants from the parent scope.
Workaround: flatten the sequence by removing `loop:` blocks and labelling
repeated interactions explicitly.

```bash
# If dagre crashes on a sequence diagram, remove loop: blocks:
#   loop: { → (remove)
#   inner arrows...
#   } → (remove)
# Then add iteration labels: "→ repeat until done"
```

## Import into DrawIO / PlantUML

### DrawIO (File → Import → SVG)

The SVG output preserves visual styles (colors, shapes, positions). Direct import
into draw.io works well for C4 context, container, and component diagrams.

### PlantUML (manual conversion)

No automatic D2→PlantUML converter exists. Strategy for one-off conversions:

1. Render to SVG with d2
2. Import SVG into draw.io
3. Export from draw.io to PlantUML format

Or rewrite the diagram logic by hand — D2 and PlantUML have similar expressiveness
for C4 and flow diagrams.

## Verifying the Render

```bash
d2 --layout dagre file.d2 file.svg && echo "SUCCESS" || echo "FAILED"

# Check SVG size — healthy render is 10KB+ for non-trivial diagrams
wc -c file.svg
```

## Pitfalls Checklist

- [ ] `shape: rounded_box` → `shape: rectangle` (not a valid D2 shape name)
- [ ] `shape: cylinders` → `shape: cylinder`
- [ ] `"font-size"` needs quotes in style blocks (hyphenated attrs)
- [ ] Multi-line notes need `|md` block strings, not quoted multi-line strings
- [ ] No `|` characters inside `|md` block strings
- [ ] Arrow labels AFTER `:`, not as inline text on arrow parts
- [ ] `loop:` blocks may crash dagre — flatten as workaround
- [ ] C4 Level 4+ diagrams with `layers:` generate multiple SVG boards
