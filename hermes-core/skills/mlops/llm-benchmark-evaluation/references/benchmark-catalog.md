# Benchmark Catalog — LLM Evaluation (July 2026)

## Quick Reference: SOTA Scores

| Benchmark | Metric | SOTA Score | SOTA Model | Notes |
|-----------|--------|------------|------------|-------|
| SciCode | Main problem resolve rate | 10.8% | o3-mini-low | Hardest code benchmark |
| SciCode | Subproblem resolve rate | 34.4% | o3-mini-high | |
| BFCL V4 | Overall accuracy | 81.1% | Llama 3.1 405B | Tool use |
| SWE-bench Verified | Resolve rate | >80% | Claude 3.7+ (vendor) | Real GitHub issues |
| HumanEval+ | pass@1 | ~95% | Frontier models | Rigorous code gen |
| MMLU | Accuracy | ~89% | GPT-4o, Gemini 2.5 | General knowledge |
| GSM8K | Accuracy | ~95% | Frontier models | Math reasoning |
| τ-bench | Task success | ~70% | Claude 3.7 | Tool-agent-user |
| HarmBench | Refusal rate (abliterated) | <5% | Heretic abliterated | Safety/refusal |
| Humanity's Last Exam | Score | 44.9 | Kimi K2 Thinking | Expert-level |

## Function Calling & Tool Use Benchmarks

### BFCL V4 (Berkeley Function Calling Leaderboard)
- **What**: Function calling accuracy across simple, parallel, multiple, multi-turn, web search, memory, format sensitivity
- **Dataset**: 2000+ test cases across 5 major categories
- **Paper**: ICML 2025
- **GitHub**: https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard
- **Leaderboard**: https://gorilla.cs.berkeley.edu/leaderboard.html
- **Install**: `pip install bfcl-eval`
- **vLLM integration**: `--skip-server-setup` flag + `REMOTE_OPENAI_BASE_URL` env var
- **Categories**: simple_python, parallel, live_multiple, multi_turn_base, web_search, memory, format_sensitivity
- **Small model highlight**: ToolACE-8B and Qwen3.5-4B (97.5% in local test) punch above weight

### τ-bench / τ²-bench / τ³-bench
- **What**: Tool-Agent-User interaction in dynamic dialogue with domain policies
- **Domains**: airline, retail, telecom, banking_knowledge (τ³ adds voice + RAG)
- **Paper**: https://arxiv.org/abs/2406.12045 (τ¹), https://arxiv.org/abs/2506.07982 (τ²)
- **GitHub**: https://github.com/sierra-research/tau2-bench
- **Leaderboard**: https://taubench.com
- **Install**: `uv sync` (requires Python ≥3.12)
- **vLLM integration**: Uses LiteLLM → any OpenAI-compatible endpoint
- **τ³ new features**: Voice full-duplex (OpenAI/Gemini/xAI realtime), knowledge retrieval with configurable RAG

### ToolBench
- 16,000+ real-world RESTful APIs. https://github.com/OpenBMB/ToolBench

### ComplexFuncBench
- Complex function calling: multi-step, constraints, long parameters, 128k context. https://github.com/THUDM/ComplexFuncBench

### MCP-specific benchmarks (2025-2026)
- **LiveMCPBench**: Large-scale MCP toolset evaluation
- **MCP-Universe**: Real-world MCP server interaction (financial analysis, browser automation)

## Scientific Code Benchmarks

### SciCode
- **What**: 80 research problems → 338 subproblems, 16 subdomains (Physics, Math, Chemistry, Biology, Materials Science)
- **Paper**: NeurIPS 2024 D&B, https://arxiv.org/abs/2407.13168
- **GitHub**: https://github.com/scicode-bench/SciCode
- **Test data**: Google Drive (test_data.h5)
- **Framework**: inspect_ai (recommended) or OpenCompass
- **Difficulty**: o3-mini solves only 10.8%. Most models < 5%.

### ResearchCodeBench (2025)
- 212 coding challenges from ML research papers (2024-2025)

## General Code Benchmarks

### HumanEval+ / MBPP+ (EvalPlus)
- Rigorous code generation with 80x/35x more tests than originals
- https://github.com/evalplus/evalplus — `pip install evalplus`

### LiveCodeBench
- Contamination-free — continuously collects new problems from competitive programming
- https://github.com/LiveCodeBench/LiveCodeBench

### SWE-bench / Verified / Pro
- Resolve real GitHub issues by generating patches
- SWE-bench: 2,294 problems. Verified: 500 human-validated. Pro: 1,865 from 41 repos.
- https://github.com/SWE-bench/SWE-bench — https://swebench.com/
- **Warning**: Scores NOT directly comparable across vendors (different scaffolds/tools)

### Aider Polyglot Benchmark
- 225 Exercism exercises across C++, Go, Java, JavaScript, Python, Rust
- https://aider.chat/docs/leaderboards/

## General Knowledge & Reasoning

### lm-evaluation-harness (EleutherAI)
- 200+ tasks, 25+ model backends. https://github.com/EleutherAI/lm-evaluation-harness
- Key tasks: MMLU, MMLU-Pro, GSM8K, MATH, HumanEval, ARC, HellaSwag, IFEval, TruthfulQA, Winogrande, BBH, GPQA
- vLLM: Use `local-chat-completions` model type with `base_url` parameter

### LightEval (Hugging Face)
- https://github.com/huggingface/lighteval

### EvalScope (ModelScope)
- 156+ benchmarks, performance stress testing. https://github.com/modelscope/evalscope

### LiveBench
- Contamination-free, refreshed every 6 months. https://livebench.ai/

### Humanity's Last Exam (HLE)
- 2,500 expert-level academic questions. https://lastexam.ai/

## Safety Benchmarks

### HarmBench
- 400 harmful behaviors across 7 categories
- Dataset: `walledai/HarmBench` on HuggingFace
- Custom script: `templates/harmbench_eval.py` — heuristic refusal detection

### MASK Benchmark
- Disentangles honesty from accuracy. https://scale.com/leaderboard/mask

### FACTS Grounding
- Long-form factuality grounded in context documents (up to 32k tokens)

## Agentic Benchmarks

### GAIA
- Real-world questions requiring reasoning, multi-modality, web browsing, tool use
- https://huggingface.co/spaces/gaia-benchmark/leaderboard

### AgentBench
- 8 environments: OS, Database, Web Shopping. https://github.com/THUDM/AgentBench

### BrowseComp
- 1,266 questions requiring persistent web navigation

## Computer Interaction (GUI/Web)

### OSWorld
- 369 real-world tasks in Windows, macOS, Ubuntu. https://os-world.github.io/

### WebArena
- Self-hostable web environment. https://github.com/web-arena-x/webarena

### AndroidWorld
- 116 tasks across 20 Android apps. https://github.com/google-research/android_world

## Abliteration Quality Research (April 2026)

Source: Nathan Sapwell, https://nathan.sapwell.net/posts/hauhaucs-abliteration-analysis/

### Methodology
1. **Capability benchmarks**: lm-eval-harness with vLLM at bf16
2. **Safety evaluation**: HarmBench 400 (7 categories)
3. **KL divergence**: Output distribution shift from original
4. **Weight analysis**: SVD, fingerprint, edit vector overlap, per-layer

### Key Findings
- Abliteration is **NOT lossless** — all techniques cause some quality drop
- Bigger models suffer MORE collateral damage
- **Heretic** (by p-e-w): most consistent, least quality drop, but non-deterministic
- **HauhauCS**: claims "0 refusals" and "lossless" — both claims do NOT hold
- **Huihui**: inconsistent across models
- Architecture matters: hybrid Mamba2+Transformer (Qwen3.5) interacts differently than pure Transformer

## Full Benchmark Compendium

50+ benchmarks categorized: https://github.com/philschmid/ai-agent-benchmark-compendium

## Framework Comparison

| Framework | Focus | Tasks | vLLM | Install |
|-----------|-------|-------|------|---------|
| lm-eval-harness | General | 200+ | local-completions | `pip install lm-eval` |
| LightEval | General | 100+ | vLLM backend | `pip install lighteval` |
| EvalScope | General + perf | 156+ | yes | `pip install evalscope` |
| inspect-ai | Agentic | SciCode + custom | OpenAI compat | `pip install inspect-ai` |
| BFCL | Tool use | 2000+ | skip-server-setup | `pip install bfcl-eval` |
| EvalPlus | Code | HumanEval+, MBPP+ | openai backend | `pip install evalplus` |
| DeepEval | App-level | Custom metrics | yes | `pip install deepeval` |
