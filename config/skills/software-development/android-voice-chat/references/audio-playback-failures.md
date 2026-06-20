# Android Audio Playback — Failed Approaches (June 2026)

All tested on Honor device, API 36, connected via ADB reverse.

## ExoPlayer + OGG

**Result:** Silent playback. OGG file valid, but STATE_ENDED never fired, causing coroutine hang.

## AudioTrack + PCM WAV

**Result:** track.write() blocked forever regardless of play/write order, buffer size, or chunking.

## MediaPlayer + WAV from cache

**Result:** prepare/start/completion all work, but no audible output. File plays fine via file manager.

## Proxy TTS + MediaPlayer

**Result:** Edge TTS works but 10-30s latency. Piper via LocalAI works (0.4s) but medium quality.

## WHAT WORKS: Android TextToSpeech.speak()

Instant, reliable, audible, non-blocking via UtteranceProgressListener. No file I/O, no proxy.
