#!/usr/bin/env python3
"""Voice proxy: wraps Hermes STT/TTS tools as simple HTTP endpoints for Android app.
Uses local faster-whisper for STT (NOT Hermes API — LocalAI model loading unreliable).
Uses Hermes text_to_speech_tool for TTS + ffmpeg OGG→WAV conversion.
"""

import base64, json, os, sys, tempfile, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8647

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
        """Raw audio bytes → local faster-whisper → transcript."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_error(400, "Empty body")
                return
            raw = self.rfile.read(content_length)

            suffix = ".ogg"
            if raw[:4] == b"RIFF": suffix = ".wav"
            elif raw[:3] == b"ID3": suffix = ".mp3"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(raw)
                tmp_path = f.name

            try:
                from faster_whisper import WhisperModel
                _model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = _model.transcribe(tmp_path, language="ru")
                transcript = " ".join(seg.text for seg in segments).strip()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"transcript": transcript}).encode())
            finally:
                try: os.unlink(tmp_path)
                except: pass
        except Exception as e:
            self.send_error(500, str(e))

    def _handle_tts(self):
        """JSON {text: ...} → Hermes TTS → ffmpeg OGG→WAV → audio/wav."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(content_length))
            text = data.get("text", "")
            if not text:
                self.send_error(400, "Missing 'text'")
                return

            sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent"))
            from tools.tts_tool import text_to_speech_tool
            result_raw = text_to_speech_tool(text=text)
            result = json.loads(result_raw) if isinstance(result_raw, str) else result_raw

            audio_path = result.get("file_path", "") if isinstance(result, dict) else ""
            if not audio_path and isinstance(result, dict):
                mt = result.get("media_tag", "")
                if "MEDIA:" in mt: audio_path = mt.split("MEDIA:")[1].strip()

            if audio_path and os.path.exists(audio_path):
                wav_path = audio_path.replace(".ogg", ".wav").replace(".opus", ".wav")
                try:
                    subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ar", "16000",
                        "-ac", "1", "-sample_fmt", "s16", wav_path],
                        capture_output=True, timeout=10)
                    audio_data = open(wav_path, "rb").read() if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100 else open(audio_path, "rb").read()
                    mime = "audio/wav" if wav_path in str(audio_data) else "audio/ogg"
                    try: os.unlink(wav_path)
                    except: pass
                except:
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
                data_url = result.get("data_url", "") if isinstance(result, dict) else ""
                if data_url and "base64," in data_url:
                    audio_data = base64.b64decode(data_url.split("base64,")[1])
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Content-Length", str(len(audio_data)))
                    self.end_headers()
                    self.wfile.write(audio_data)
                else:
                    self.send_error(500, f"TTS failed: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_error(500, str(e))

if __name__ == "__main__":
    print(f"[VoiceProxy] Starting on 0.0.0.0:{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), VoiceProxyHandler).serve_forever()
