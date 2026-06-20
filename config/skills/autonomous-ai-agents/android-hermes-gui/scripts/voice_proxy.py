#!/usr/bin/env python3
"""Voice proxy: wraps Hermes STT/TTS tools as simple HTTP endpoints for Android app.
Run: python3 voice_proxy.py (from Hermes venv)
Exposes:
  POST /stt  — raw audio bytes → JSON {transcript: "..."}
  POST /tts  — JSON {text: "..."} → audio/ogg binary
  GET /health — status check
"""

import base64
import io
import json
import os
import sys
import tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8647
HERMES_HOME = os.path.expanduser("~/.hermes")
sys.path.insert(0, os.path.join(HERMES_HOME, "hermes-agent"))


class VoiceProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[VoiceProxy] {args[0]}", flush=True)

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/stt":
            self._handle_stt()
        elif self.path == "/tts":
            self._handle_tts()
        else:
            self.send_error(404)

    def _handle_stt(self):
        """Accept raw audio bytes, return transcription."""
        try:
            content_type = self.headers.get("Content-Type", "")
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_error(400, "Empty body")
                return

            raw = self.rfile.read(content_length)

            # Try multipart parsing
            if "multipart" in content_type:
                boundary = None
                for part in content_type.split(";"):
                    if "boundary=" in part:
                        boundary = part.split("boundary=")[1].strip().strip('"')
                if boundary:
                    parts = raw.split(f"--{boundary}".encode())
                    for part in parts:
                        if b"Content-Type:" in part and (b"filename=" in part or b"audio" in part.lower()):
                            header_end = part.find(b"\r\n\r\n")
                            if header_end > 0:
                                audio_data = part[header_end + 4:]
                                audio_data = audio_data.rstrip(b"\r\n").rstrip(b"--").rstrip(b"\r\n")
                                if len(audio_data) > 100:
                                    raw = audio_data
                                    break

            # Detect format and save
            suffix = ".ogg"
            if raw[:4] == b"RIFF": suffix = ".wav"
            elif raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb": suffix = ".mp3"
            elif raw[:4] == b"Opus": suffix = ".opus"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(raw)
                tmp_path = f.name

            try:
                from tools.transcription_tools import transcribe_audio
                result = transcribe_audio(tmp_path)
                transcript = result.get("transcript", "") if isinstance(result, dict) else str(result)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"transcript": transcript}).encode())
            finally:
                try: os.unlink(tmp_path)
                except: pass

        except Exception as e:
            print(f"[VoiceProxy] STT error: {e}", flush=True)
            self.send_error(500, str(e))

    def _handle_tts(self):
        """Accept JSON {text: ...}, return audio/ogg binary."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(content_length)
            data = json.loads(raw)
            text = data.get("text", data.get("input", ""))
            if not text:
                self.send_error(400, "Missing 'text' field")
                return

            from tools.tts_tool import text_to_speech_tool
            result_raw = text_to_speech_tool(text=text)

            # text_to_speech_tool may return a JSON string or a dict
            if isinstance(result_raw, str):
                result = json.loads(result_raw)
            else:
                result = result_raw

            # Find audio file path
            audio_path = None
            if isinstance(result, dict):
                audio_path = result.get("file_path", "")
            if not audio_path and isinstance(result, dict):
                media_tag = result.get("media_tag", "")
                if "MEDIA:" in media_tag:
                    audio_path = media_tag.split("MEDIA:")[1].strip()

            if audio_path and os.path.exists(audio_path):
                with open(audio_path, "rb") as f:
                    audio_data = f.read()

                if audio_path.endswith(".ogg") or audio_path.endswith(".opus"):
                    mime = "audio/ogg"
                elif audio_path.endswith(".wav"):
                    mime = "audio/wav"
                else:
                    mime = "audio/mpeg"

                try: os.unlink(audio_path)
                except: pass

                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(audio_data)))
                self.end_headers()
                self.wfile.write(audio_data)
            else:
                self.send_error(500, f"TTS produced no file. Keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_error(500, str(e))


if __name__ == "__main__":
    print(f"[VoiceProxy] Starting on 0.0.0.0:{PORT}", flush=True)
    server = HTTPServer(("0.0.0.0", PORT), VoiceProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[VoiceProxy] Stopped", flush=True)
