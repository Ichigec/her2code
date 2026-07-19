#!/usr/bin/env python3
"""Benchmark vLLM with/without EAGLE3 speculator.

Usage:
    python benchmark.py <label> [--url URL] [--model MODEL_PATH]

Sends a warmup request (for JIT/CUDAgraph), then 3 timed requests,
then extracts spec decoding metrics from /metrics.

Examples:
    # Baseline (no speculator)
    python benchmark.py baseline

    # Speculator
    python benchmark.py speculator
"""
import argparse
import json
import time
import urllib.request

DEFAULT_URL = "http://localhost:8000/v1/chat/completions"
DEFAULT_MODEL = "/home/user/dev/a1-agents"

PROMPTS = [
    "Write a Python function for quicksort. Explain each line.",
    "What is the capital of France? Give a one paragraph answer.",
    "Write a SQL query to find the top 10 customers by total order value from a table called orders with columns customer_id, order_value, order_date.",
]


def send_request(url, model, prompt, max_tokens=256):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - start
    return data, elapsed


def fetch_metrics(base_url):
    metrics_url = base_url.rstrip("/").removesuffix("/v1") + "/metrics"
    try:
        with urllib.request.urlopen(metrics_url, timeout=10) as resp:
            return resp.read().decode()
    except Exception:
        return ""


def parse_metrics(metrics_text):
    data = {}
    for line in metrics_text.split("\n"):
        if not line.startswith("vllm:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].split("{")[0]
        val = parts[-1]
        for key in ("speculative_token_draft_total", "speculative_token_accepted_total",
                    "time_to_first_token_seconds_sum", "time_to_first_token_seconds_count",
                    "inter_token_latency_seconds_sum", "inter_token_latency_seconds_count",
                    "request_generation_tokens_sum"):
            if key in name:
                data[key] = float(val)
    return data


def main():
    parser = argparse.ArgumentParser(description="Benchmark vLLM speculator")
    parser.add_argument("label", help="Label for this run (e.g. baseline, speculator)")
    parser.add_argument("--url", default=DEFAULT_URL, help="vLLM completions URL")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model path")
    args = parser.parse_args()

    base_url = args.url.rstrip("/").removesuffix("/v1")

    # Warmup (JIT/CUDAgraph compilation)
    print(f"=== [{args.label}] Warmup ===")
    _, warmup_time = send_request(args.url, args.model, "Hello", max_tokens=16)
    print(f"Warmup: {warmup_time:.2f}s (JIT/CUDAgraph compilation)")
    print()

    # Timed runs
    results = []
    for i, prompt in enumerate(PROMPTS):
        data, elapsed = send_request(args.url, args.model, prompt)
        tokens = data["usage"]["completion_tokens"]
        text = data["choices"][0]["message"]["content"]
        tok_s = tokens / elapsed if elapsed > 0 else 0
        print(f"=== [{args.label}] PROMPT {i+1} ===")
        print(f"Time: {elapsed:.2f}s | Tokens: {tokens} | Throughput: {tok_s:.1f} tok/s")
        print(f"First 100 chars: {text[:100]}")
        print()
        results.append({"prompt": prompt, "time": elapsed, "tokens": tokens, "text": text})

    # Metrics
    metrics_text = fetch_metrics(base_url)
    data = parse_metrics(metrics_text)

    print(f"=== [{args.label}] METRICS ===")
    ttft_s = data.get("vllm:time_to_first_token_seconds_sum", 0)
    ttft_c = data.get("vllm:time_to_first_token_seconds_count", 0)
    itl_s = data.get("vllm:inter_token_latency_seconds_sum", 0)
    itl_c = data.get("vllm:inter_token_latency_seconds_count", 0)
    draft = data.get("vllm:speculative_token_draft_total", 0)
    accepted = data.get("vllm:speculative_token_accepted_total", 0)

    if ttft_c:
        print(f"TTFT (avg): {ttft_s/ttft_c:.3f}s")
    if itl_c:
        print(f"Inter-token latency (avg): {itl_s/itl_c*1000:.1f}ms")
        print(f"Throughput (from metrics): {1/(itl_s/itl_c):.1f} tok/s")
    if draft > 0:
        print(f"Draft proposed: {int(draft)}")
        print(f"Draft accepted: {int(accepted)}")
        print(f"Acceptance rate: {accepted/draft*100:.1f}%")

    # Save results
    import os
    out_dir = os.environ.get("BENCH_OUTPUT_DIR", "/tmp/eagle3_bench")
    os.makedirs(out_dir, exist_ok=True)
    with open(f"{out_dir}/{args.label}_results.json", "w") as f:
        json.dump({"results": results, "metrics": data}, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_dir}/{args.label}_results.json")


if __name__ == "__main__":
    main()
