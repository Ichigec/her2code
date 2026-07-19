#!/usr/bin/env python3
"""
Compare benchmark results between two models (e.g., original vs abliterated).

Usage:
  python3 compare_models.py <model_a_label> <model_b_label> [--results-dir DIR]
  python3 compare_models.py original abliterated

Workflow (abliteration audit):
  1. Run benchmarks on original:  ./run_benchmarks.sh all  (MODEL_LABEL=original)
  2. Run benchmarks on abliterated: ./run_benchmarks.sh all (MODEL_LABEL=abliterated)
  3. Compare: python3 compare_models.py original abliterated
"""

import json
import sys
from pathlib import Path


def load_summary(results_dir, model_label):
    summary_file = Path(results_dir) / model_label / "summary.json"
    if not summary_file.exists():
        print(f"ERROR: No summary found for '{model_label}' at {summary_file}")
        return None
    with open(summary_file) as f:
        return json.load(f)


def flatten_results(summary):
    flat = {}
    benchmarks = summary.get("benchmarks", {})
    for bench_name, bench_data in benchmarks.items():
        if not bench_data or not isinstance(bench_data, dict):
            continue
        if bench_name == "harmbench":
            if "refusal_rate" in bench_data:
                flat[f"{bench_name}.refusal_rate"] = bench_data["refusal_rate"]
            if "compliance_rate" in bench_data:
                flat[f"{bench_name}.compliance_rate"] = bench_data["compliance_rate"]
            continue
        for key, value in bench_data.items():
            if isinstance(value, dict):
                for k2, v2 in value.items():
                    if isinstance(v2, (int, float)):
                        flat[f"{bench_name}.{key}.{k2}"] = v2
            elif isinstance(value, (int, float)):
                flat[f"{bench_name}.{key}"] = value
    return flat


def color_delta(delta):
    if delta < -0.01:
        return f"\033[0;31m{delta:+.4f}\033[0m"
    elif delta > 0.01:
        return f"\033[0;32m{delta:+.4f}\033[0m"
    else:
        return f"{delta:+.4f}"


def main():
    if len(sys.argv) < 3:
        print("Usage: compare_models.py <model_a> <model_b> [--results-dir DIR]")
        sys.exit(1)

    model_a = sys.argv[1]
    model_b = sys.argv[2]
    results_dir = "./results"
    if "--results-dir" in sys.argv:
        idx = sys.argv.index("--results-dir")
        results_dir = sys.argv[idx + 1]

    summary_a = load_summary(results_dir, model_a)
    summary_b = load_summary(results_dir, model_b)
    if not summary_a or not summary_b:
        sys.exit(1)

    flat_a = flatten_results(summary_a)
    flat_b = flatten_results(summary_b)
    all_keys = sorted(set(flat_a.keys()) | set(flat_b.keys()))

    print(f"\n{'=' * 90}")
    print(f"  Model Comparison: {model_a}  vs  {model_b}")
    print(f"{'=' * 90}")
    print(f"\n{'Metric':<55s} {'A':>10s} {'B':>10s} {'Delta':>10s}")
    print("-" * 90)

    degradations = []
    improvements = []
    unchanged = 0

    for key in all_keys:
        val_a = flat_a.get(key)
        val_b = flat_b.get(key)
        if val_a is None:
            print(f"{key:<55s} {'N/A':>10s} {val_b:>10.4f} {'N/A':>10s}")
        elif val_b is None:
            print(f"{key:<55s} {val_a:>10.4f} {'N/A':>10s} {'N/A':>10s}")
        else:
            delta = val_b - val_a
            pct = (delta / abs(val_a) * 100) if val_a != 0 else 0
            if delta < -0.01:
                degradations.append((key, delta, pct))
            elif delta > 0.01:
                improvements.append((key, delta, pct))
            else:
                unchanged += 1
            print(f"{key:<55s} {val_a:>10.4f} {val_b:>10.4f} {color_delta(delta):>10s}")

    print(f"\n{'=' * 90}")
    print(f"\n  Summary: Total={len(all_keys)}  Improvements={len(improvements)}  "
          f"Degradations={len(degradations)}  Unchanged={unchanged}")

    if degradations:
        print(f"\n  Top Degradations (potential collateral damage):")
        for key, delta, pct in sorted(degradations, key=lambda x: x[1])[:15]:
            print(f"    {key:<50s} {delta:+.4f} ({pct:+.1f}%)")

    if improvements:
        print(f"\n  Top Improvements:")
        for key, delta, pct in sorted(improvements, key=lambda x: -x[1])[:10]:
            print(f"    {key:<50s} {delta:+.4f} ({pct:+.1f}%)")

    # Abliteration-specific analysis
    print(f"\n  Abliteration Audit:")
    ref_a = flat_a.get("harmbench.refusal_rate")
    ref_b = flat_b.get("harmbench.refusal_rate")
    if ref_a is not None and ref_b is not None:
        print(f"    Refusal rate:  {ref_a:.1f}% -> {ref_b:.1f}% (delta: {ref_b - ref_a:+.1f}%)")
        if ref_b < ref_a:
            print(f"    OK: Abliteration reduced refusals as expected")
        else:
            print(f"    WARNING: Abliteration did NOT reduce refusals")

    mmlu_a = next((v for k, v in flat_a.items() if "mmlu" in k.lower() and "acc" in k.lower()), None)
    mmlu_b = next((v for k, v in flat_b.items() if "mmlu" in k.lower() and "acc" in k.lower()), None)
    if mmlu_a is not None and mmlu_b is not None:
        delta = mmlu_b - mmlu_a
        print(f"    MMLU:          {mmlu_a:.4f} -> {mmlu_b:.4f} (delta: {delta:+.4f})")
        if delta < -0.02:
            print(f"    WARNING: Significant knowledge degradation ({delta*100:+.1f}%)")
        elif delta < -0.005:
            print(f"    Minor knowledge degradation ({delta*100:+.1f}%)")
        else:
            print(f"    OK: No significant knowledge loss")

    print(f"\n{'=' * 90}\n")


if __name__ == "__main__":
    main()
