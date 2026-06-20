#!/usr/bin/env python3
"""
Voice proxy: wraps Hermes STT/TTS tools as HTTP endpoints.
Run with Hermes venv: /home/user/.hermes/hermes-agent/venv/bin/python3 voice_proxy.py

Endpoints:
  POST /stt  — raw audio bytes → {"transcript": "..."}
  POST /tts  — {"text": "..."} → WAV audio (16kHz mono PCM, ffmpeg-converted from OGG)
  GET /health — {"status": "ok"}

Key implementation notes:
  - transcribe_audio() returns dict with "transcript" key
  - text_to_speech_tool() returns JSON STRING (needs json.loads), with "file_path" key
  - Default TTS is Piper → OGG. Convert to WAV via ffmpeg for Android AudioTrack compatibility.
  - STT detects format from magic bytes: RIFF→WAV, ID3/0xfffb→MP3, Opus→opus, else OGG
"""

import base64, json, os, sys, tempfile, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8647
HERMES_HOME = os.path.expanduser("~/.hermes")
sys.path.insert(0, os.path.join(HERMES_HOME, "hermes-agent"))


class VoiceProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[VoiceProxy] {args[0]}", flush=True)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/stt":
            self._handle_stt()
        elif self.path == "/tts":
            self._handle_tts()
        else:
            self.send_error(404)

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_stt(self):
        """Accept raw audio bytes, return transcription."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_error(400, "Empty body")
                return
            raw = self.rfile.read(content_length)

            # Detect format from magic bytes
            suffix = ".ogg"
            if raw[:4] == b"RIFF":
                suffix = ".wav"
            elif raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
                suffix = ".mp3"
            elif raw[:4] == b"Opus":
                suffix = ".opus"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(raw)
                tmp_path = f.name

            try:
                from tools.transcription_tools import transcribe_audio
                result = transcribe_audio(tmp_path)
                transcript = result.get("transcript", "") if isinstance(result, dict) else str(result)
                self._json(200, {"transcript": transcript})
            finally:
                try: os.unlink(tmp_path)
                except: pass
        except Exception as e:
            self.send_error(500, str(e))

    def _handle_tts(self):
        """Accept JSON {text: ...}, return WAV audio."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(content_length))
            text = data.get("text", "")
            if not text:
                self.send_error(400, "Missing 'text'")
                return

            from tools.tts_tool import text_to_speech_tool
            result_raw = text_to_speech_tool(text=text)
            # text_to_speech_tool returns JSON string — parse it
            if isinstance(result_raw, str):
                result = json.loads(result_raw)
            else:
                result = result_raw

            audio_path = result.get("file_path", "") if isinstance(result, dict) else ""

            if audio_path and os.path.exists(audio_path):
                # Convert OGG→WAV via ffmpeg for guaranteed Android playback
                wav_path = audio_path.rsplit(".", 1)[0] + ".wav"
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000",
                         "-ac", "1", "-sample_fmt", "s16", wav_path],
                        capture_output=True, timeout=10
                    )
                    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                        audio_data = open(wav_path, "rb").read()
                        mime = "audio/wav"
                        os.unlink(wav_path)
                    else:
                        audio_data = open(audio_path, "rb").read()
                        mime = "audio/ogg"
                except Exception:
                    audio_data = open(audio_path, "rb").read()
                    mime = "audio/ogg"

                try: os.unlink(audio_path)
                except: pass

                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(audio_data)))
                self.end_headers()
                self.wfile.write(audio_data)
            else:
                self.send_error(500, f"No audio file produced. Keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_error(500, str(e))


if __name__ == "__main__":
    print(f"[VoiceProxy] Starting on 0.0.0.0:{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), VoiceProxyHandler).serve_forever()
