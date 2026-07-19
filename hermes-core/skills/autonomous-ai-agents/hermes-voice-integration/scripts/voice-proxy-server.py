#!/usr/bin/env python3
"""Voice proxy: wraps faster-whisper STT + Hermes TTS as HTTP endpoints.
Drop-in server for Android Hermes voice pipeline.
Run: python3 voice_proxy.py
Port: 8647
"""
import base64, json, os, sys, tempfile
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8647
HERMES_HOME = os.path.expanduser("~/.hermes")
sys.path.insert(0, os.path.join(HERMES_HOME, "hermes-agent"))

# Cached model — DO NOT reload on every request
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
    return _whisper_model

class VoiceProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, f, *a):
        print(f"[VoiceProxy] {a[0]}", flush=True)

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
            self._stt()
        elif self.path == "/tts":
            self._tts()
        else:
            self.send_error(404)

    def _stt(self):
        """POST /stt — raw audio body → {"transcript": "..."}"""
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl == 0: return self.send_error(400, "Empty body")
            raw = self.rfile.read(cl)
            suffix = ".ogg"
            if raw[:4] == b"RIFF": suffix = ".wav"
            elif raw[:4] == b"Opus": suffix = ".opus"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(raw); tmp = f.name
            try:
                model = get_whisper_model()
                segments, _ = model.transcribe(tmp, language="ru")
                text = " ".join(s.text for s in segments).strip()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"transcript": text}).encode())
            finally:
                try: os.unlink(tmp)
                except: pass
        except Exception as e:
            self.send_error(500, str(e))

    def _tts(self):
        """POST /tts — {"text":"..."} → WAV audio"""
        try:
            cl = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(cl))
            text = data.get("text", "")
            if not text: return self.send_error(400)
            sys.path.insert(0, os.path.join(HERMES_HOME, "hermes-agent"))
            from tools.tts_tool import text_to_speech_tool
            r = text_to_speech_tool(text=text)
            if isinstance(r, str): r = json.loads(r)
            # Find audio file
            audio_path = r.get("file_path", "") if isinstance(r, dict) else ""
            if not audio_path and isinstance(r, dict):
                mt = r.get("media_tag", "")
                if "MEDIA:" in mt: audio_path = mt.split("MEDIA:")[1].strip()
            if not audio_path or not os.path.exists(audio_path):
                self.send_error(500, "TTS produced no file")
                return
            # Convert OGG→WAV for Android compatibility
            import subprocess
            wav = audio_path.replace(".ogg", ".wav")
            subprocess.run(["ffmpeg","-y","-i",audio_path,"-ar","16000","-ac","1",
                           "-sample_fmt","s16",wav], capture_output=True, timeout=10)
            if os.path.exists(wav) and os.path.getsize(wav) > 100:
                audio_data = open(wav, "rb").read()
                mime = "audio/wav"
                os.unlink(wav)
            else:
                audio_data = open(audio_path, "rb").read()
                mime = "audio/ogg"
            os.unlink(audio_path)
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(audio_data)))
            self.end_headers()
            self.wfile.write(audio_data)
        except Exception as e:
            self.send_error(500, str(e))

if __name__ == "__main__":
    print(f"[VoiceProxy] :{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), VoiceProxyHandler).serve_forever()
