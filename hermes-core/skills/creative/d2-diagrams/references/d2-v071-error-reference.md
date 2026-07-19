# D2 v0.7.1 Error Reference

Collected reproduction cases and error messages from real sessions.

## Note Syntax Failures

### Error: `missing value after colon`

**Trigger**: `note "multi\nline\ntext": { style: { fill: "red" } }` — colon after quoted string.

**File pattern** (before fix):
```
note "Key Facts:
• line 1
• line 2": {
  style: {
    fill: "#fff9c4"
    stroke: "#f57f17"
  }
}
```

**Fix**: Convert to `note: |md ... | { multi-line style }`

### Error: `unexpected text after double quoted string` + `maps must be terminated with }`

**Trigger**: Inline style after block string terminator on same line:
```
| { style.fill: "#fff9c4" style.stroke: "#f57f17" }
```

**Fix**: Multi-line style block:
```
| {
  style.fill: "#fff9c4"
  style.stroke: "#f57f17"
}
```

## Block String Pipe Conflicts

### Error: `unexpected text after md block string` + `block string must be terminated with |`

**Trigger**: Any `|` character inside `|md` block string content — even mid-line.

Examples that all fail:
```
|md
  List[str|Dict]          # pipe mid-line
|
```
```
|md
  "a"|"b"|"c"            # pipes as separators
|
```
```
|md
  grep foo | grep bar     # shell pipeline
|
```
```
|md
| Col1 | Col2 |           # markdown table
|------|------|
|
```
```
|md
  int | None              # type union
|
```

**Root cause**: D2 v0.7.1 parser treats every `|` character as a potential block string terminator. There is no escape mechanism.

**Fix**: Rephrase content to avoid pipe characters entirely. Use `/`, `or`, `—`, or plain text alternatives.

## Sequence Diagram Loop Crash

### Error: `TypeError: Cannot convert undefined or null to object` (dagre layout)

**Trigger**: `loop:` block inside `shape: sequence_diagram` followed by `*.` arrows referencing participants that were only introduced via other `*.` arrows inside the loop.

**Reproduction** (fails):
```d2
direction: down

diagram: "Test" {
  shape: sequence_diagram
  a: "A"
  b: "B"
  c: "C"
  a -> b: "msg"
  loop: {
    *.a -> *.b: "loop"
  }
  *.b -> *.c: "after"   # CRASH
}
```

**Minimal passing test** (no post-loop arrows):
```d2
direction: down
diagram: "Test" {
  shape: sequence_diagram
  a: "A"
  b: "B"
  c: "C"
  a -> b: "msg"
  loop: {
    *.a -> *.b: "loop"
  }
}
```

**Alternative error** (different dagre path): `Error: Not possible to find intersection inside of the rectangle at intersectRect`

This occurs with self-referencing arrows inside loops combined with post-loop arrows.

**Fix**: Remove the `loop:` block. Flatten all arrows to the top level.

## Style Attribute Name Errors

### Error: `fill must be style.fill` / `stroke must be style.stroke`

**Trigger**: Using bare `fill:` or `stroke:` on a shape defined via key-value:
```d2
external: {
  myshape: "Label"
  myshape.fill: "#fff3e0"   # ERROR
  myshape.stroke: "#e65100" # ERROR
}
```

**Fix**: Prefix with `style.`:
```d2
  myshape.style.fill: "#fff3e0"
  myshape.style.stroke: "#e65100"
```

Note: `shape: rectangle` and inline `style: { ... }` blocks still work fine — the bare `fill`/`stroke` error only applies to key-value attribute lines.

## Dollar Sign Substitution

### Error: `substitutions must begin on {`

**Trigger**: `$VARIABLE` in a double-quoted string:
```d2
  user_providers: "User Plugins\n($HERMES_HOME/plugins/)"
```

**Fix**: Use block string:
```d2
  user_providers: |md
    User Plugins ($HERMES_HOME/plugins/)
  |
```

## Markdown HTML Parsing

### Error: `malformed Markdown: element <name> closed by </p>`

**Trigger**: HTML-like tags inside `|md` block string:
```d2
  user_providers: |md
    User Plugins ($HERMES_HOME/plugins/<name>/)
  |
```

**Fix**: Remove angle brackets or wrap in backticks where the markdown parser won't interpret them as HTML.
