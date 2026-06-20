# ExoPlayer/AudioTrack Playback Issues on Android

## ExoPlayer
- **Symptom**: `STATE_ENDED` never fires, `suspendCancellableCoroutine` hangs forever
- **Evidence**: `AVPlayer(0): isPlaying` logged continuously, no STATE_ENDED
- **Verdict**: NOT suitable for OGG/WAV playback in suspend coroutine pattern

## AudioTrack
- **Symptom 1**: `track.write()` blocks forever when buffer too small
- **Symptom 2**: Playback silent — audio routed to wrong output
- **Root cause**: Buffer size = `getMinBufferSize()` insufficient for some devices
- **Verdict**: NOT suitable — unreliable, silent playback on some devices

## MediaPlayer with internal cache files
- **Symptom**: Plays silently, no error
- **Root cause**: Probably audio routing issue with internal app cache URI
- **Verdict**: Works for some devices, silent on others

## Working Solution: Android TextToSpeech
- `TextToSpeech.speak()` — built-in, always works
- `UtteranceProgressListener.onDone()` reliably fires
- No file I/O, no audio routing issues
- Neural voices via Google TTS (`com.google.android.tts`)
