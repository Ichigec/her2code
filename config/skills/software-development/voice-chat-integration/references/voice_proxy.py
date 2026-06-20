#!/usr/bin/env python3
"""Voice proxy: wraps Hermes STT/TTS tools as HTTP endpoints for Android app."""
import base64, json, os, sys, tempfile, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8647
HERMES_HOME = os.path.expanduser("~/.hermes")
sys.path.insert(0, os.path.join(HERMES_HOME, "hermes-agent"))

# Cached whisper model
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    return _whisper_model

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
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_error(400, "Empty body")
                return
            raw = self.rfile.read(content_length)

            suffix = ".ogg"
            if raw[:4] == b"RIFF": suffix = ".wav"
            elif raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb": suffix = ".mp3"
            elif raw[:4] == b"Opus": suffix = ".opus"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(raw)
                tmp_path = f.name

            try:
                model = get_whisper_model()
                segments, _ = model.transcribe(tmp_path, language="ru")
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
            if isinstance(result_raw, str):
                result = json.loads(result_raw)
            else:
                result = result_raw

            audio_path = None
            if isinstance(result, dict):
                audio_path = result.get("file_path", "")
            if not audio_path and isinstance(result, dict):
                media_tag = result.get("media_tag", "")
                if "MEDIA:" in media_tag:
                    audio_path = media_tag.split("MEDIA:")[1].strip()

            if audio_path and os.path.exists(audio_path):
                # Convert to WAV for Android compatibility
                wav_path = audio_path.rsplit('.', 1)[0] + '.wav'
                try:
                    subprocess.run(
                        ['ffmpeg', '-y', '-i', audio_path, '-ar', '16000', '-ac', '1',
                         '-sample_fmt', 's16', wav_path],
                        capture_output=True, timeout=15
                    )
                    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 100:
                        audio_data = open(wav_path, 'rb').read()
                        mime = "audio/wav"
                        os.unlink(wav_path)
                    else:
                        audio_data = open(audio_path, 'rb').read()
                        mime = "audio/ogg" if audio_path.endswith('.ogg') else "audio/mpeg"
                except Exception:
                    audio_data = open(audio_path, 'rb').read()
                    mime = "audio/ogg" if audio_path.endswith('.ogg') else "audio/mpeg"

                try: os.unlink(audio_path)
                except: pass

                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(audio_data)))
                self.end_headers()
                self.wfile.write(audio_data)
            else:
                self.send_error(500, "TTS produced no audio")
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_error(500, str(e))

if __name__ == "__main__":
    print(f"[VoiceProxy] Starting on 0.0.0.0:{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), VoiceProxyHandler).serve_forever()
