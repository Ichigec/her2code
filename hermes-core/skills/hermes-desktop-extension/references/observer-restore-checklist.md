# Observer Restore Checklist

When `observerItem` is lost (e.g., after `git checkout`), restore ALL of these:

## Imports needed in desktop-controller.tsx

```tsx
import { Brain, Eye, EyeOff } from '@/lib/icons'
import { ObserverPanel } from './shell/observer-panel'
import { $observerConfig } from '../store/session'  // add to existing import
```

## Code blocks

```tsx
const observerConfig = useStore($observerConfig)
const observerItem = useMemo<StatusbarItem>(
  () => {
    const enabled = observerConfig.enabled
    return {
      className: enabled ? 'text-(--color-green-400)' : 'opacity-50',
      icon: enabled ? <Eye className="size-3" /> : <EyeOff className="size-3" />,
      id: 'observer-panel',
      label: enabled ? undefined : 'OFF',
      menuClassName: 'w-72',
      menuContent: <ObserverPanel sessionId={activeSessionId} requestGateway={requestGateway} />,
      title: enabled ? 'Observers ON' : 'Observers OFF',
      variant: 'menu'
    }
  },
  [activeSessionId, requestGateway, observerConfig.enabled]
)
```

## useStatusbarItems call

```tsx
useStatusbarItems({
  ...
  observerItem,       // ← add
  ...
})
```

## excludeSources

```tsx
excludeSources: ['cron', 'observer']  // was: ['cron']
```

## use-statusbar-items.tsx interface

```tsx
interface StatusbarItemsOptions {
  ...
  observerItem?: StatusbarItem   // ← add
  ...
}
```
