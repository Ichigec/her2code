# GUI Build Pipeline — Detailed Reference

> Дата: 2026-07-07
> Контекст: сборка Hermes Desktop GUI из локальных файлов, офлайн и онлайн, на ARM64 и x86_64.

## Pipeline сборки (что происходит внутри `npm run build`)

```
npm run build (apps/desktop/package.json):
  1. assert-root-install.cjs  → проверяет ../../node_modules/vite/package.json
     └─ Если нет: "Run from repo root: cd <root> && npm ci" → exit 1
  2. write-build-stamp.cjs    → apps/desktop/build/install-stamp.json
     └─ Читает GITHUB_SHA env var или git rev-parse HEAD
     └─ Без git и без GITHUB_SHA → ошибка (stamp обязателен для bootstrap)
     └─ Schema: {schemaVersion, commit, branch, builtAt, dirty, source}
  3. stage-native-deps.cjs    → копирует node-pty в build/native-deps/
     └─ Читает npm_config_arch (от electron-builder) или process.arch
     └─ Копирует только runtime-essential файлы (prebuilds + build/Release)
     └─ Без этого: PTY initialization fails at runtime
  4. tsc -b                   → TypeScript type-check (500+ файлов, ~30s ARM64)
  5. vite build               → frontend bundle в dist/ (22 MB JS, ~2s)
```

```
electron-builder --dir:
  6. beforePack → удаляет stale unpacked-директорию
  7. Упаковка в release/linux-<arch>-unpacked/Hermes (195 MB бинарник)
  8. afterPack → extraResources: install-stamp.json + native-deps/
```

## Архитектурные зависимости

| Файл | Архитектура | Размер | Что делать при смене arch |
|------|-------------|--------|--------------------------|
| `node_modules/node-pty/build/Release/pty.node` | linux-arm64 | 81 KB | `npm rebuild node-pty` (нужны python3 make g++) |
| `node_modules/node-pty/prebuilds/linux-arm64/` | **НЕ СУЩЕСТВУЕТ** | — | Linux требует компиляцию. Prebuilds есть только для darwin-arm64, win32-arm64 |
| `node_modules/electron/dist/electron` | linux-arm64 | 195 MB | Удалить + `npx electron install` (скачает нужную arch) |
| `~/.cache/electron/electron-v40.9.3-linux-arm64.zip` | linux-arm64 | 115 MB | Для x64: `electron-v40.9.3-linux-x64.zip` |
| `node_modules/electron/path.txt` | содержит `electron` | — | Не зависит от arch |

### node-pty: единственный native dep

- **Linux**: НЕТ prebuilds. Требует компиляцию через `npm rebuild node-pty` (нужны python3, make, g++).
- **macOS**: Prebuilds в `prebuilds/darwin-arm64/pty.node` — компиляция не нужна.
- **Windows**: Prebuilds в `prebuilds/win32-arm64/` — компиляция не нужна.

### Electron: кеширование

- Бинарник скачивается при `npm ci` / `npm install` в `node_modules/electron/dist/electron`.
- Кеш хранится в `~/.cache/electron/electron-v<version>-linux-<arch>.zip`.
- Для офлайн: скопировать кеш с донора той же архитектуры.
- Зеркало для РФ: `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`.

## Офлайн-перенос на новую машину (та же архитектура)

```bash
# === На доноре: упаковать ===

# 1. Зависимости монорепо (1.6 GB)
cd ~/hermes-agent
tar czf /tmp/hermes-gui-deps.tar.gz \
  node_modules/ \
  apps/desktop/package.json \
  apps/desktop/package-lock.json \
  apps/desktop/electron/ \
  apps/desktop/src/ \
  apps/desktop/scripts/ \
  apps/desktop/assets/ \
  apps/desktop/tsconfig.json \
  apps/desktop/tsconfig.*.json \
  apps/desktop/vite.config.ts \
  apps/desktop/index.html \
  ui-tui/ \
  web/ \
  package.json \
  package-lock.json

# 2. Electron cache (115 MB)
tar czf /tmp/hermes-electron-cache.tar.gz -C ~/.cache electron/

# 3. (Опционально) npm cache для будущих installs
tar czf /tmp/hermes-npm-cache.tar.gz -C ~/.npm _cacache/

# === На новой машине ===

# 4. Распаковать
mkdir -p ~/hermes-agent && cd ~/hermes-agent
tar xzf /tmp/hermes-gui-deps.tar.gz
mkdir -p ~/.cache && tar xzf /tmp/hermes-electron-cache.tar.gz -C ~/.cache

# 5. Системные зависимости для node-pty
sudo apt install -y python3 make g++   # Linux only

# 6. Собрать
build-gui.sh --skip-install --dir
```

## Смена архитектуры (ARM64 → x64)

```bash
# 1. Удалить arch-специфичные бинарники
rm -f node_modules/node-pty/build/Release/pty.node
rm -rf node_modules/electron/dist/

# 2. Пересобрать node-pty для новой arch
npm rebuild node-pty

# 3. Скачать Electron для новой arch
npx electron install   # скачает electron-v40.9.3-linux-x64.zip

# 4. Собрать
build-gui.sh --skip-install --dir --arch x64
```

## npm scripts — полная карта

| Script | Что делает | Время ARM64 |
|--------|-----------|-------------|
| `npm run build` | tsc + vite + stage-native-deps + write-build-stamp | ~30s |
| `npm run type-check` | только `tsc -b` | ~30s |
| `npm run lint` | ESLint на src/ и electron/ | ~10s |
| `npm run pack` | build + electron-builder --dir | ~45s |
| `npm run dist` | build + electron-builder (все targets текущей ОС) | ~5 мин |
| `npm run dist:linux` | build + electron-builder --linux AppImage deb rpm | ~5 мин |
| `npm run dist:mac` | build + electron-builder --mac | ~5 мин |
| `npm run dist:win` | build + electron-builder --win | ~5 мин |
| `npm run test:ui` | vitest run --environment jsdom (63 spec-файла) | ~60s |
| `npm run test:desktop:platforms` | node --test (8 electron test-файлов) | ~15s |
| `npm run test:desktop:existing` | build + validate + launch с существующим Hermes | ~2 мин |
| `npm run test:desktop:fresh` | build + validate + launch с temp userData | ~2 мин |
| `npm run test:desktop:all` | build + validate + print artifacts | ~2 мин |
| `npm start` | build + electron . (dev mode) | ~30s + GUI |
| `npm run dev` | concurrently vite dev server + electron | realtime |

## validateBundle() — что проверяет

1. **Бинарник Hermes существует** — `APP.binary` (release/linux-<arch>-unpacked/Hermes)
2. **Нет stale factory-payload** — `resources/hermes-agent/hermes_cli/main.py` НЕ должен существовать (thin-installer regression check)
3. **install-stamp.json валиден** — содержит commit (≥7 chars) + branch + builtAt + dirty
4. **node-pty native deps** — `resources/native-deps/node-pty/package.json` + `lib/index.js` + `prebuilds/<platform>-<arch>/` с .node файлами
5. **Renderer payload** — `dist/index.html` в unpacked или внутри app.asar

## Структура результатов сборки

```
apps/desktop/
├── dist/                              ← Frontend bundle (vite)
│   ├── index.html
│   ├── assets/
│   │   └── index-<hash>.js            ← 22 MB (main bundle)
│   └── ...
├── build/
│   ├── install-stamp.json             ← {commit, branch, builtAt, dirty}
│   └── native-deps/
│       └── node-pty/
│           ├── package.json
│           ├── lib/
│           │   └── index.js
│           └── build/Release/
│               └── pty.node           ← 81 KB (linux-arm64)
└── release/
    ├── builder-debug.yml
    ├── builder-effective-config.yaml
    └── linux-arm64-unpacked/          ← 335 MB
        ├── Hermes                     ← 195 MB (Electron app)
        ├── chrome-sandbox             ← SUID wrapper (chmod 4755)
        ├── chrome_crashpad_handler
        ├── icudtl.dat                 ← 10 MB
        ├── libEGL.so, libGLESv2.so, etc.
        ├── resources/
        │   ├── app.asar               ← упакованный код
        │   ├── install-stamp.json     ← из build/
        │   └── native-deps/           ← из build/native-deps/
        └── ...
```

## Hermes v0.16.0 — проверенные версии

| Компонент | Версия |
|-----------|--------|
| hermes-agent | v0.16.0 (2026.6.5) |
| Desktop app | 0.15.1 |
| Electron | 40.9.3 |
| electron-builder | 26.8.1 |
| node-pty | microsoft/node-pty 1.x (N-API based) |
| Vite | (из root package-lock) |
| TypeScript | (из root package-lock) |
| Node.js | 22.22.2 |
