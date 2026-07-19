#!/usr/bin/env python3
"""Benchmark each local model through LiteLLM — tokens/sec measurement.

Usage:
    python3 benchmark-models.py
    python3 benchmark-models.py --litellm-key sk-local --max-tokens 1024

Requires: LiteLLM running on localhost:4000 with models configured.
"""

import argparse
import json
import time
import urllib.request


def benchmark(model_name, litellm_url, api_key, max_tokens, prompt):
    payload = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        litellm_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    print(f"  Sending request ({max_tokens} max tokens)...", end=" ", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    t1 = time.time()

    elapsed = t1 - t0
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    tps = completion_tokens / elapsed if elapsed > 0 else 0
    total_tps = total_tokens / elapsed if elapsed > 0 else 0

    preview = data["choices"][0]["message"]["content"][:120].replace("\n", " ")

    print(f"done in {elapsed:.1f}s")
    print(f"    Prompt tokens:     {prompt_tokens}")
    print(f"    Completion tokens: {completion_tokens}")
    print(f"    Time:              {elapsed:.2f}s")
    print(f"    Output tok/s:      {tps:.1f}")
    print(f"    Total tok/s:       {total_tps:.1f}")
    print(f"    Preview: {preview}...")

    return {
        "model": model_name,
        "elapsed": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "output_tps": tps,
        "total_tps": total_tps,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark local models via LiteLLM")
    parser.add_argument("--litellm-url", default="http://localhost:4000/v1/chat/completions",
                        help="LiteLLM chat completions endpoint")
    parser.add_argument("--litellm-key", default="sk-local",
                        help="LiteLLM API key")
    parser.add_argument("--max-tokens", type=int, default=512,
                        help="Max tokens to generate per model")
    parser.add_argument("--prompt",
                        default="Write a detailed essay about the history of computing, "
                                "from Charles Babbage to modern AI. Include at least 5 paragraphs.",
                        help="Prompt to send")
    parser.add_argument("--models", nargs="*",
                        default=["nex-n2-mini", "agents-a1-abliterated", "agentworld"],
                        help="Model names to benchmark")
    args = parser.parse_args()

    print("=" * 65)
    print(f"  LOCAL MODEL BENCHMARK — tokens/sec via LiteLLM")
    print(f"  Max output: {args.max_tokens} tokens")
    print("=" * 65)
    print()

    results = []
    for model in args.models:
        print(f"-- {model}")
        try:
            r = benchmark(model, args.litellm_url, args.litellm_key,
                          args.max_tokens, args.prompt)
            results.append(r)
        except Exception as e:
            print(f"    ERROR: {e}")
        print()

    # Summary table
    print("=" * 65)
    print("  SUMMARY")
    print("=" * 65)
    print(f"  {'Model':<35} {'Tokens':>8} {'Time':>8} {'Out tok/s':>12}")
    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*12}")
    for r in results:
        print(f"  {r['model']:<35} {r['completion_tokens']:>8} "
              f"{r['elapsed']:>7.1f}s {r['output_tps']:>11.1f}")
    print()


if __name__ == "__main__":
    main()
