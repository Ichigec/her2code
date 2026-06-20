# Hermes GUI — Android Client

Android-приложение для полноценного взаимодействия с AI-агентом **Hermes** (и **OpenCode+**) через OpenAI-совместимый API.

## Возможности

| Функция | Описание |
|---------|----------|
| 💬 **Чат со стримингом** | Потоковый вывод ответов AI в реальном времени (SSE) |
| 🔄 **Переключение моделей** | Выбор из 10+ моделей (DeepSeek, GPT-4o, Claude, Gemini, и др.) |
| 🎭 **Переключение агентов** | 15+ персонажей: Технический, Креативный, Учитель, Нуар, Пират, Neko-chan... |
| 💾 **Сохранение диалогов** | Локальная БД (Room/SQLite) с поиском и удалением |
| ⚙️ **Настройки** | API URL, ключ, тема, стриминг, промпт |
| 🔧 **Инструменты (Tools)** | Просмотр и включение/отключение tools с Hermes API |
| 🖥️ **Исполнение кода** | Выполнение команд на хосте через terminal tool (с подтверждением) |
| 🌓 **Тёмная тема** | Material 3, светлая/тёмная/системная тема |

## Технологии

- **Kotlin 1.9** + **Jetpack Compose** + **Material 3**
- **MVVM** + **Clean Architecture**
- **Hilt** DI • **Room** DB • **Retrofit** + **OkHttp**
- **Moshi** JSON • **DataStore** Preferences
- **EncryptedSharedPreferences** для хранения API-ключа

## Быстрый старт

1. Открой проект в **Android Studio** (Hedgehog+)
2. Синхронизируй Gradle
3. Запусти на устройстве или эмуляторе (API 26+)
4. В Настройках укажи URL Hermes API-сервера и API-ключ
5. Начни диалог на вкладке Чат

```bash
# Или из командной строки
cd /home/user/dev/Opencode
./gradlew installDebug
```

## Hermes API Server

Приложение подключается к Hermes Agent API Server (OpenAI-совместимый):

| Эндпоинт | Метод | Назначение |
|----------|-------|------------|
| `/health` | GET | Проверка здоровья |
| `/v1/models` | GET | Список моделей |
| `/v1/chat/completions` | POST | Чат (включая SSE streaming) |
| `/v1/toolsets` | GET | Список инструментов |
| `/v1/capabilities` | GET | Возможности сервера |
| `/api/sessions` | GET/POST | Управление сессиями |

## Структура проекта

```
com.hermes.gui/
├── data/
│   ├── remote/     # HermesApi (Retrofit), SseClient, DTOs
│   ├── local/      # Room DB, DAOs, Entities
│   ├── settings/   # Encrypted preferences
│   └── repository/ # Chat, Dialog, Settings, Tool repos
├── domain/
│   └── model/      # Message, Conversation, Toolset
├── ui/
│   ├── chat/       # ChatScreen, ChatViewModel, MessageBubble
│   ├── dialogs/    # DialogListScreen, DialogItem
│   ├── settings/   # SettingsScreen, API/Tools/Appearance sections
│   ├── navigation/ # NavGraph, Screen routes
│   └── theme/      # Material 3 colors, typography
├── di/             # Hilt modules
└── util/           # MarkdownRenderer, Constants
```

## Документация

| Документ | Описание |
|----------|----------|
| [Requirements](docs/requirements/hermes-android-gui.md) | Требования и use cases |
| [Research](docs/research/hermes-android-gui.md) | Глубокий анализ Hermes API |
| [Architecture](docs/architecture/hermes-android-gui.md) | Архитектура и ADR |
| [Plan](docs/plans/2026-06-12-hermes-android-gui.md) | План реализации |
| [Deployment](docs/deployment/hermes-android-gui.md) | Сборка и деплой |
| [Retrospective](docs/retrospectives/2026-06-12-hermes-android-gui.md) | Ретроспектива |

## Требования

- **Android 8.0+** (API 26)
- **Hermes Agent** с включенным API-сервером (`API_SERVER_ENABLED=true`)
- API-ключ (`API_SERVER_KEY`) из `.env` Hermes

## Лицензия

MIT
