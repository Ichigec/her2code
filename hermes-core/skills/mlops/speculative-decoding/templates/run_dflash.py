#!/usr/bin/env python3
"""
DFlash speculative decoding — universal runner template.
Supports both Qwen3.6-27B (dense) and Qwen3.6-35B-A3B (MoE).

Usage:
  python run_dflash.py --model 27b                    # one-shot DFlash
  python run_dflash.py --model 35b --chat              # interactive MoE
  python run_dflash.py --model 27b --baseline          # no DFlash (comparison)
  python run_dflash.py --model 27b --prompt "Hello" --max-new-tokens 1024

Requirements: transformers >= 5.13, torch, venv with CUDA support.
On GB10: /home/user/vllm_venv/bin/python run_dflash.py --model 27b
"""
import os, sys, time, argparse, importlib.util
import torch

# ─── Model Registry ──────────────────────────────────────────────────────────

MODELS = {
    "27b": {
        "target_path": "/home/user/models/Qwen3.6-27B",
        "draft_path":  "/home/user/models/Qwen3.6-27B-DFlash",
        "import_class": (
            "from transformers.models.qwen3_5.modeling_qwen3_5 "
            "import Qwen3_5ForConditionalGeneration as TargetClass"
        ),
        "label": "Qwen3.6-27B (dense)",
    },
    "35b": {
        "target_path": "/home/user/models/Qwen3.6-35B-A3B",
        "draft_path":  "/home/user/models/Qwen3.6-35B-A3B-DFlash",
        "import_class": (
            "from transformers.models.qwen3_5_moe.modeling_qwen3_5_moe "
            "import Qwen3_5MoeForConditionalGeneration as TargetClass"
        ),
        "label": "Qwen3.6-35B-A3B (MoE)",
    },
}

DEV   = "cuda:0"
DTYPE = torch.bfloat16

# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_dflash_module(draft_path):
    """Load dflash.py from the model directory (it's NOT a pip package)."""
    spec = importlib.util.spec_from_file_location(
        "dflash_mod", os.path.join(draft_path, "dflash.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def prep_input(tokenizer, messages):
    """Tokenize with chat template, handle transformers v5 BatchEncoding return.

    CRITICAL: apply_chat_template(return_tensors='pt') returns a BatchEncoding
    object in transformers v5, NOT a dict and NOT a tensor. BatchEncoding is
    dict-LIKE (supports ['key']) but isinstance(r, dict) is False. It also has
    a .to() method that works (moves all tensors), but accessing .shape on it
    fails with KeyError. Must extract input_ids as a tensor explicitly.
    """
    try:
        r = tokenizer.apply_chat_template(
            messages, return_tensors="pt",
            add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        r = tokenizer.apply_chat_template(
            messages, return_tensors="pt", add_generation_prompt=True)
    # Robust extraction — handles Tensor, dict, BatchEncoding, list
    if isinstance(r, torch.Tensor):
        ids = r
    elif isinstance(r, dict):
        ids = r["input_ids"]
    else:
        ids = getattr(r, "input_ids", r)
    if not isinstance(ids, torch.Tensor):
        ids = torch.tensor(ids, dtype=torch.long)
    ids = ids.to(DEV)
    if ids.dim() == 1:
        ids = ids.unsqueeze(0)
    stops = list(set(
        [tokenizer.encode(t, add_special_tokens=False)[-1]
         for t in ["<|im_end|>", "<|endoftext|>"]
         if tokenizer.encode(t, add_special_tokens=False)]
        + ([tokenizer.eos_token_id] if tokenizer.eos_token_id else [])
    ))
    return ids, stops

def load_draft_with_config_fix(draft_path):
    """Load DFlash draft model, fixing config issues that vary between releases.

    Two known issues with 35B-DFlash (not present in 27B-DFlash):
    (a) block_size is nested inside dflash_config instead of top-level.
        dflash.py does config.block_size → AttributeError. Fix: hoist it.
    (b) dflash.py uses DynamicCache() without config, needed for linear-attention.
        Fix: patch the dflash.py file itself (see SKILL.md pitfall #32).
    """
    from transformers import AutoModel, AutoConfig
    draft_cfg = AutoConfig.from_pretrained(draft_path, trust_remote_code=True)
    if not hasattr(draft_cfg, "block_size") and hasattr(draft_cfg, "dflash_config"):
        draft_cfg.block_size = draft_cfg.dflash_config.get("block_size", 16)
    draft = AutoModel.from_pretrained(
        draft_path, config=draft_cfg, dtype=DTYPE, trust_remote_code=True).to(DEV)
    return draft

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="DFlash speculative decoding runner")
    ap.add_argument("--model", choices=["27b", "35b"], default="27b")
    ap.add_argument("--prompt", default="Write a Python function to check if a number is prime. Keep it short.")
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--baseline", action="store_true", help="Disable DFlash (AR only)")
    ap.add_argument("--chat", action="store_true", help="Interactive chat mode")
    args = ap.parse_args()

    cfg = MODELS[args.model]
    use_dflash = not args.baseline

    from transformers import AutoTokenizer, AutoModel
    exec(cfg["import_class"], globals())

    # Load tokenizer
    print("Loading tokenizer...", end=" ", flush=True)
    tok = AutoTokenizer.from_pretrained(cfg["target_path"])
    print("OK")

    # Load target
    print(f"Loading {cfg['label']}... ", end="", flush=True)
    t0 = time.perf_counter()
    target = TargetClass.from_pretrained(cfg["target_path"], dtype=DTYPE).to(DEV)
    target.eval()
    if use_dflash:
        # CRITICAL: dflash.py accesses target.model.embed_tokens, but Qwen3_5/Qwen3_5Moe
        # nests it under target.model.language_model.embed_tokens
        target.model.embed_tokens = target.model.language_model.embed_tokens
    print(f"OK {time.perf_counter()-t0:.1f}s  VRAM {torch.cuda.memory_allocated()/1e9:.1f} GB")

    # Load draft
    dflash_mod = draft = None
    if use_dflash:
        print("Loading DFlash draft... ", end="", flush=True)
        t0 = time.perf_counter()
        draft = load_draft_with_config_fix(cfg["draft_path"])
        draft.eval()
        dflash_mod = load_dflash_module(cfg["draft_path"])
        print(f"OK {time.perf_counter()-t0:.1f}s  VRAM {torch.cuda.memory_allocated()/1e9:.1f} GB")
        print(f"  block_size={draft.block_size} mask_token_id={draft.mask_token_id}")

    mode = "DFlash" if use_dflash else "Baseline"
    print(f"\n{'='*60}\n  {cfg['label']} [{mode}]\n{'='*60}")

    def generate(messages):
        ids, stops = prep_input(tok, messages)
        with torch.inference_mode():
            if use_dflash:
                s = dflash_mod.dflash_generate(
                    model=draft, target=target, input_ids=ids,
                    max_new_tokens=args.max_new_tokens, stop_token_ids=stops,
                    temperature=args.temperature, return_stats=True)
                text = tok.decode(s.output_ids[0, ids.shape[1]:], skip_special_tokens=True)
                acc = sum(s.acceptance_lengths)/len(s.acceptance_lengths) if s.acceptance_lengths else 0
                print(f"\n\033[2m[{s.num_output_tokens} tok | {1/s.time_per_output_token:.1f} tok/s | "
                      f"TTFT {s.time_to_first_token:.2f}s | acc {acc:.1f}/{draft.block_size}]\033[0m")
                return text
            else:
                torch.cuda.synchronize(); t0 = time.perf_counter()
                out = target.generate(ids, max_new_tokens=args.max_new_tokens,
                                      do_sample=False, use_cache=True)
                torch.cuda.synchronize(); dt = time.perf_counter()-t0
                text = tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)
                n = out.shape[1]-ids.shape[1]
                print(f"\n\033[2m[{n} tok | {n/dt:.1f} tok/s | {dt:.2f}s]\033[0m")
                return text

    if args.chat:
        history = []
        print("Interactive mode — type 'quit' to exit.\n")
        while True:
            try:
                user = input("┌─ You:\n│ ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if user.lower() in ("quit", "exit", "q"):
                break
            if not user:
                continue
            history.append({"role": "user", "content": user})
            print("└─ Assistant: ", end="", flush=True)
            text = generate(history)
            print(text)
            history.append({"role": "assistant", "content": text})
            print()
    else:
        print(f"\nPrompt: {args.prompt}\n")
        text = generate([{"role": "user", "content": args.prompt}])
        print(f"\n{text}\n{'='*60}")

if __name__ == "__main__":
    main()
