#!/usr/bin/env python3
"""
DiffusionGemma OpenAI-compatible API server for LiteLLM integration.
Wraps llama-diffusion-cli (PR #24423) as an HTTP server.

Env vars:
  DG_MODEL_PATH   - path to .gguf model (required)
  DG_BINARY       - path to llama-diffusion-cli (required)
  DG_NGL          - GPU layers (default: 99)
  DG_CTX_SIZE     - context size (default: 65536)
  DG_PORT         - HTTP port (default: 8646)
  DG_MODEL_NAME   - model name in API (default: diffusion-gemma-26b)
  DG_DEFAULT_STEPS - diffusion steps (default: 64)
  DG_DEFAULT_MAX_TOKENS - max tokens (default: 256)
"""

import asyncio
import json
import os
import re
import time
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

MODEL_PATH = os.environ["DG_MODEL_PATH"]
BINARY = os.environ["DG_BINARY"]
NGL = int(os.environ.get("DG_NGL", "99"))
CTX_SIZE = int(os.environ.get("DG_CTX_SIZE", "65536"))
PORT = int(os.environ.get("DG_PORT", "8646"))
MODEL_NAME = os.environ.get("DG_MODEL_NAME", "diffusion-gemma-26b")
DEFAULT_STEPS = int(os.environ.get("DG_DEFAULT_STEPS", "64"))
DEFAULT_MAX_TOKENS = int(os.environ.get("DG_DEFAULT_MAX_TOKENS", "256"))

app = FastAPI(title="DiffusionGemma API", docs_url=None, redoc_url=None)
_infer_lock = asyncio.Semaphore(1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def messages_to_prompt(messages: List[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"<start_of_turn>user\n[System: {content}]<end_of_turn>")
        elif role == "user":
            parts.append(f"<start_of_turn>user\n{content}<end_of_turn>")
        elif role == "assistant":
            parts.append(f"<start_of_turn>model\n{content}<end_of_turn>")
    parts.append("<start_of_turn>model\n")
    return "\n".join(parts)


def parse_output(raw: str) -> str:
    raw = re.sub(r"^<\|channel>thought\s*", "", raw.strip())
    match = re.search(r"<channel\|>(.*?)(?:total time:|$)", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    lines = [l for l in raw.splitlines()
             if not l.startswith("total time:") and not l.startswith("step")]
    return "\n".join(lines).strip()


def build_cmd(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
              temperature: float = 0.7, steps: int = DEFAULT_STEPS) -> list:
    return [
        BINARY,
        "-m", MODEL_PATH,
        "-p", prompt,
        "-ngl", str(NGL),
        "-c", str(CTX_SIZE),
        "-n", str(max_tokens),
        "--temp", str(temperature),
        "--diffusion-steps", str(steps),
        "--log-colors", "off",
    ]


async def run_inference(cmd: list, timeout: int = 900) -> str:
    async with _infer_lock:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=504, detail="Inference timed out")

        stderr_text = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Inference failed (rc={proc.returncode}): {stderr_text[-500:]}"
            )
        result = parse_output(stdout.decode("utf-8", errors="replace"))
        if not result:
            raise HTTPException(status_code=500, detail="Empty model output")
        return result


# ── API ───────────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = MODEL_NAME
    messages: List[Message]
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = 0.7
    stream: bool = False
    diffusion_steps: int = DEFAULT_STEPS


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id": MODEL_NAME,
            "object": "model",
            "created": 0,
            "owned_by": "local"
        }]
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    prompt = messages_to_prompt([m.model_dump() for m in req.messages])
    cmd = build_cmd(
        prompt,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        steps=req.diffusion_steps,
    )

    req_id = uuid.uuid4().hex

    if req.stream:
        async def stream_gen():
            content = await run_inference(cmd)
            chunk = {
                "id": f"chatcmpl-{req_id}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": MODEL_NAME,
                "choices": [{
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            done = {
                "id": f"chatcmpl-{req_id}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": MODEL_NAME,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n"

        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    content = await run_inference(cmd)
    return {
        "id": f"chatcmpl-{req_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": -1, "completion_tokens": -1, "total_tokens": -1}
    }


if __name__ == "__main__":
    import uvicorn
    print(f"DiffusionGemma server on :{PORT} (model={MODEL_NAME}, steps={DEFAULT_STEPS})")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
