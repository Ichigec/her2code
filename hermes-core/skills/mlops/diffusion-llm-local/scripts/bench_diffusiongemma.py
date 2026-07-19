#!/usr/bin/env python3
"""bench_diffusiongemma.py — Benchmark DiffusionGemma throughput on DGX Spark.

Tests canvas fill effect: short vs long outputs.
Diffusion tok/s depends on output length (per-canvas cost, not per-token).

Usage:
    python3 bench_diffusiongemma.py
    python3 bench_diffusiongemma.py --thinking false
    python3 bench_diffusiongemma.py --warmup
"""

import argparse
import json
import time
import urllib.request

URL = "http://localhost:8000/v1/chat/completions"
MODEL = "diffusiongemma-abliterated"

TESTS = [
    {
        "name": "short (8 tokens)",
        "prompt": "Say hello.",
        "max_tokens": 8,
    },
    {
        "name": "medium (128 tokens)",
        "prompt": "Explain what a diffusion language model is in 2 sentences.",
        "max_tokens": 128,
    },
    {
        "name": "full canvas (256 tokens)",
        "prompt": "Write a detailed paragraph about the architecture of DiffusionGemma. Include details about the MoE backbone, canvas-based generation, denoising steps, and bidirectional attention.",
        "max_tokens": 256,
    },
    {
        "name": "multi-canvas (512 tokens, prose)",
        "prompt": "Write a comprehensive technical analysis of block-diffusion language models. Cover: 1) how diffusion applies to discrete text, 2) the canvas and denoising process, 3) advantages over autoregressive decoding, 4) throughput characteristics and why tok/s is misleading, 5) tool calling and reasoning capabilities, 6) deployment considerations on edge hardware like DGX Spark.",
        "max_tokens": 512,
    },
    {
        "name": "code generation (512 tokens)",
        "prompt": "Write a Python class implementing a simple LRU cache with get, put, and delete methods. Include type hints, docstrings, and a usage example.",
        "max_tokens": 512,
    },
]


def run_test(test: dict, thinking: bool, warmup: bool = False) -> dict:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": test["prompt"]}],
        "max_tokens": test["max_tokens"],
        "temperature": 0,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": thinking},
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})

    start = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    elapsed = time.time() - start

    usage = result.get("usage", {})
    output_tokens = usage.get("completion_tokens", 0)
    input_tokens = usage.get("prompt_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    tok_s = output_tokens / elapsed if elapsed > 0 else 0
    total_tok_s = total_tokens / elapsed if elapsed > 0 else 0

    return {
        "name": test["name"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "elapsed_s": round(elapsed, 2),
        "output_tok_s": round(tok_s, 1),
        "total_tok_s": round(total_tok_s, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark DiffusionGemma throughput")
    parser.add_argument("--thinking", choices=["true", "false"], default="false",
                        help="Enable thinking (default: false for clean throughput)")
    parser.add_argument("--warmup", action="store_true", help="Run warmup request first")
    args = parser.parse_args()

    thinking = args.thinking == "true"

    try:
        urllib.request.urlopen("http://localhost:8000/health", timeout=5)
    except Exception:
        print("Server not running on :8000. Start with: ~/models/serve_diffusiongemma.sh")
        return

    print(f"DiffusionGemma BF16 Benchmark — DGX Spark (GB10)")
    print(f"Thinking: {thinking}")
    print(f"Model: {MODEL}")
    print(f"Endpoint: {URL}")
    print()

    if args.warmup:
        print("Warmup request...")
        run_test(TESTS[2], thinking)
        print("Warmup done.\n")

    results = []
    for test in TESTS:
        print(f"Running: {test['name']}...", end=" ", flush=True)
        r = run_test(test, thinking)
        results.append(r)
        print(f"{r['output_tok_s']} tok/s ({r['output_tokens']} tokens in {r['elapsed_s']}s)")

    print()
    print("=" * 80)
    print(f"{'Test':<36} {'Out tok':>8} {'Time':>8} {'Out tok/s':>12}")
    print("=" * 80)
    for r in results:
        print(f"{r['name']:<36} {r['output_tokens']:>8} {r['elapsed_s']:>7.1f}s {r['output_tok_s']:>11.1f}")
    print("=" * 80)

    print()
    short = results[0]
    full = results[2]
    multi = results[3]
    code = results[4]
    print(f"Canvas fill effect:")
    print(f"  Short ({short['output_tokens']} tok):  {short['output_tok_s']} tok/s  — canvas barely filled")
    print(f"  Full canvas ({full['output_tokens']} tok): {full['output_tok_s']} tok/s  — 1 canvas, fully utilized")
    print(f"  Multi-canvas ({multi['output_tokens']} tok): {multi['output_tok_s']} tok/s  — 2 canvases")
    print(f"  Code gen ({code['output_tokens']} tok): {code['output_tok_s']} tok/s  — code is predictable, better fill")
    print()
    if full['output_tok_s'] > 0 and short['output_tok_s'] > 0:
        ratio = full['output_tok_s'] / short['output_tok_s']
        print(f"  Full canvas is {ratio:.1f}x faster than short (per-canvas cost amortization)")
    print()
    print(f"Thinking: {thinking}")
    if thinking:
        print("  NOTE: thinking tokens are counted in output_tokens but not shown.")
        print("  Real visible tok/s may be lower. Disable thinking for clean speed.")


if __name__ == "__main__":
    main()
