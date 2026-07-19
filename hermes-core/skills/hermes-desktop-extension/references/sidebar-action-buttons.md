# Sidebar Action Buttons (Add/Delete) — Reusable Patterns

Adding action buttons (ADD header button, DELETE per-row) to an existing sidebar
section. Extracted from the agent-presets add/delete implementation.

## Prerequisites

The section must already exist (render an expandable `<SidebarGroup>` with a
header and mapped rows). This reference covers adding buttons; see the main
SKILL.md for creating a new section from scratch.

## Pattern 1: ADD (+) Button in Section Header

Insert a `+` button inside the header `<div>`, after the disclosure toggle button.
Uses `justify-between` on the parent so the button sits on the right.

```tsx
<div className="group/section flex shrink-0 items-center justify-between pb-1 pt-1.5">
  <button onClick={...} className="...">
    <SidebarPanelLabel>{'Section Title'}</SidebarPanelLabel>
    <span className="...">{String(count)}</span>
    <DisclosureCaret open={open} />
  </button>

  {/* ← ADD THIS BLOCK */}
  <Tip label="New item">
    <button
      aria-label="Create a new item"
      className="rounded p-0.5 text-(--ui-text-tertiary) hover:bg-(--ui-control-active-background) hover:text-foreground"
      onClick={onCreateItem}
      type="button"
    >
      <Codicon name="add" size="0.75rem" />
    </button>
  </Tip>
</div>
```

## Pattern 2: DELETE Button Per Row with Confirmation

Each row gets a two-stage delete: trash icon → "Delete" text → confirm.
Protected/built-in items hide the delete button entirely.

### State (add inside component body)

```ts
const [pendingDelete, setPendingDelete] = useState<string | null>(null)
const [deletingId, setDeletingId] = useState<string | null>(null)
```

### Protected IDs (file-level constant)

```ts
const PROTECTED_IDS = new Set(['id1', 'id2', ...])
```

### Handler (useCallback)

```ts
const handleDelete = useCallback(
  async (id: string) => {
    setDeletingId(id)
    try {
      await onDeleteItem?.(id)
    } finally {
      setDeletingId(null)
      setPendingDelete(null)
    }
  },
  [onDeleteItem]
)
```

### Row JSX (inside `.map()`)

```tsx
{presetList.map(item => {
  const protected = PROTECTED_IDS.has(item.id)
  const confirming = pendingDelete === item.id

  return (
    <div key={item.id} className="group/item flex items-center gap-1 rounded-md pr-1 hover:bg-(--ui-control-hover-background)">
      {/* ... main row button ... */}

      {/* Configure gear (optional) */}
      <Tip label={`Configure ${item.label}`}>
        <button
          className="shrink-0 rounded p-0.5 text-(--ui-text-tertiary) opacity-0 hover:bg-(--ui-control-active-background) hover:text-foreground group-hover/item:opacity-100"
          onClick={() => onConfigure?.(item.id)}
          type="button"
        >
          <Codicon name="gear" size="0.625rem" />
        </button>
      </Tip>

      {/* DELETE — only for non-protected items */}
      {!protected &&
        (confirming ? (
          <button
            aria-label={`Confirm delete ${item.label}`}
            className="shrink-0 rounded px-1 py-0.5 text-[0.6rem] font-semibold text-destructive hover:bg-destructive/10"
            disabled={deletingId === item.id}
            onClick={() => void handleDelete(item.id)}
            type="button"
          >
            {deletingId === item.id ? '…' : 'Delete'}
          </button>
        ) : (
          <Tip label={`Delete ${item.label}`}>
            <button
              aria-label={`Delete ${item.label}`}
              className="shrink-0 rounded p-0.5 text-(--ui-text-tertiary) opacity-0 hover:bg-destructive/10 hover:text-destructive group-hover/item:opacity-100"
              onClick={() => setPendingDelete(item.id)}
              type="button"
            >
              <Codicon name="trash" size="0.625rem" />
            </button>
          </Tip>
        ))}
    </div>
  )
})}
```

## Props Interface (ChatSidebarProps or equivalent)

```ts
interface SectionProps {
  // ... existing props ...
  onCreateItem?: () => void
  onDeleteItem?: (id: string) => Promise<void>
}
```

## Wiring in desktop-controller.tsx

Pass the callbacks that already exist (e.g. `createAgentPreset`, `deleteAgentPreset`):

```tsx
<ChatSidebar
  // ... existing props ...
  onCreateAgent={createAgentPreset}
  onDeleteAgent={deleteAgentPreset}
/>
```

## Key Styling Tokens

| Element | Classes |
|---------|---------|
| ADD button base | `rounded p-0.5 text-(--ui-text-tertiary)` |
| ADD button hover | `hover:bg-(--ui-control-active-background) hover:text-foreground` |
| Row action (hidden) | `shrink-0 rounded p-0.5 opacity-0` |
| Row action (visible) | `group-hover/<name>:opacity-100` |
| Trash icon | `hover:bg-destructive/10 hover:text-destructive` |
| Confirm "Delete" | `text-[0.6rem] font-semibold text-destructive hover:bg-destructive/10` |
| Disabled during delete | `disabled={deletingId === id}` → shows `…` |
