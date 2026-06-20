# Audio Debug Chronicle: Hermes Android GUI

Хронология отладки голосового чата (2026-06-12/13).

## Попытка 1: MediaRecorder + ExoPlayer (OGG)
- MediaRecorder OGG/Opus записывает ✅ (подтверждено логами ~41KB)
- STT через прокси работает ✅ (транскрипция верная)
- ExoPlayer играет (`AVPlayer: isPlaying`), но без звука ❌
- STATE_ENDED не срабатывает → корутина висит ❌

## Попытка 2: AAC/MP4 запись
- MediaRecorder AAC/MP4 записывает
- Прокси не определяет формат (нет детекции `ftyp`) → STT ломается ❌

## Попытка 3: ExoPlayer + таймаут
- Добавлен Handler.postDelayed как fallback
- Всё равно без звука и STATE_ENDED не срабатывает ❌

## Попытка 4: AudioTrack + WAV (рабочая)
- Прокси конвертит OGG→WAV через ffmpeg ✅
- AudioTrack.play() + write() + sleep() + stop() ✅
- **Питфол:** write() ДО play() вешает AudioTrack навсегда
- Правильный порядок: play() → write() → sleep(duration) → stop()

## Ключевые ошибки и решения

| Ошибка | Причина | Решение |
|--------|---------|---------|
| "Ошибка распознавания" | Прокси упал | Watchdog авто-перезапуск |
| "Connection error: null" | URL по умолчанию не тот | DEFAULT_API_URL = localhost:8643 |
| Кнопка микрофона не работает | long-press вместо tap | Переделано на toggle |
| Статус "Отвечаю..." висит | write() до play() | play() → write() → sleep() |
| Нет звука | ExoPlayer/MediaPlayer | AudioTrack + WAV PCM |
| Gradle кеш отдаёт старый код | Кеширование | --no-build-cache + rm -rf app/build |

## Стабильная конфигурация (на 2026-06-13)

- Запись: MediaRecorder, OGG/Opus, 16kHz, 32kbps
- STT: Voice Proxy (faster-whisper через Hermes venv)
- TTS: Voice Proxy (Piper TTS → ffmpeg WAV)
- Playback: AudioTrack, 16kHz 16-bit mono PCM
- Прокси: порт 8647, watchdog каждые 15 сек
- ADB: reverse tcp:8643 tcp:8642, reverse tcp:8647 tcp:8647
