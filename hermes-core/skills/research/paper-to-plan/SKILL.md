---
name: paper-to-plan
description: "Deep research a ML paper and synthesize findings into actionable training/implementation plans with structured deliverables"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Research, Papers, Implementation, Training, Planning]
    related_skills: [arxiv, ocr-and-documents, hermes-agent-skill-authoring]
---

# Paper-to-Plan: Research + Synthesize + Deliver

Deep research a ML/LLM paper and produce structured deliverables: research doc, training plan, and reference materials.

## When to Use

Trigger: user asks to "research" a paper, architecture, or technique and "create a plan" / "make a deliverable" in a target directory.
Trigger: user asks to "verify" or "validate" or "check accuracy of" research already done — run the verification protocol (Phase 1 alternative route: get TeX sources, cross-reference every claim).

## Workflow

### Phase 1: Gather Primary Sources

1. **Get the paper**: Try HTML first (arxiv.org/html/ID), fallback to PDF (arxiv.org/pdf/ID).
2. **Gold source: arxiv e-print TeX** — For critical verification, fetch the TeX source via `arxiv.org/e-print/<id>`. The response is a gzipped tarball containing `.tex` files in `sections/`. Extract with `tar -xzf`, read `sections/method.tex`, `sections/appendix.tex`, `sections/exp.tex` directly. HTML and PDF versions may be truncated or rendered incompletely. TeX is the author's raw submission — the single source of truth.
3. **Try PDF parsing**: Install PyMuPDF (`pip install pymupdf`), stream PDF from curl, extract full text page by page.
4. **Target key sections**:
   - Section 3/4 — Method / Architecture
   - Subsection "Training" or "Training Implementation"
   - Appendix with hyperparameters
   - Ablation studies
   - All figures/tables describing architecture
5. **Also gather**: official GitHub README, any existing local checkpoints or configs.
6. **Code verification**: If a GitHub repo exists, read the actual model code (`model.py`, `model_mlx.py`, etc.) and cross-reference every architectural claim. Do NOT assume the paper description matches the code — verify: attention mechanism, KV injection, projection layers, loss function signature, forward pass logic.

### Phase 2: Read and Extract

Look for these specifics:
- Architecture diagram / component breakdown (encoder, decoder, attention variants, etc.)
- **Loss function** — exact formula, hyperparameters per variant
- **Training hyperparameters**: LR, optimizer, schedule, epochs, batch size, sequence length
- **Dataset**: size, source, preprocessing (tokenization, augmentation, filtering)
- **Ablation results**: what matters and why
- **Hardware requirements**: GPU, VRAM, batch size they used
- **Block size / window / context length** choices and rationale

CRITICAL: When the paper says "details in Appendix" — GO GET THE APPENDIX. Do not skip it. Training implementation details are routinely there.

### Phase 3: Create Deliverables

Create a directory named by the user (usually `/home/user/dev/<project-name>`).

**File 1: `01_deep_research.md`**
- What the technique/framework is (1-page executive summary)
- Architecture breakdown (component-by-component, with formulas where available)
- Full training specification: loss, optimizer, data, hyperparameters
- Ablation studies and key experimental findings
- Adaptation analysis for target hardware (Jetson vs H200, etc.)
- Conclusions

**File 2: `02_training_plan.md`**
- Executive summary with rationale for key choices (e.g., "why block size 16")
- Prerequisites checklist (checkpoints, datasets, dependencies)
- Data pipeline specification
- Model architecture setup
- Training loop pseudocode
- Evaluation metrics and validation pipeline
- Timeline estimate for target hardware
- Fallback strategies (smaller model, smaller block, fewer layers)
- Risks and mitigations table

**File 3: `README.md`**
- Table of contents of the directory
- Links to sources (paper URL, GitHub, local paths)
- Key findings in 3-5 bullet points

### Phase 4: Verify

Before declaring done:
- `ls -la /home/user/dev/<project-name>/` — all files present
- `wc -l` each file — substantial content (at least 150 lines for research doc, 100+ for plan)
- Verify paper citations are accurate (check that what you attribute to the paper actually came from the paper, not hallucinated)
- Cross-reference every claim against the gold source:
  - Loss function formula: check `sections/method.tex` or `sections/appendix.tex` for the exact equation
  - Hyperparameters: check `sections/appendix.tex` Section A.1 (Training Details)
  - Ablation results: check `sections/exp.tex` for every table referenced
  - Architecture details: check the actual `model.py` in the GitHub repo
- Flag any discrepancies explicitly in a verification report (`03_verification_report.md`)
- Report the verdict: what was confirmed, what was wrong, what data is simply absent from the paper

## Pitfalls

- **HTML paper version may be incomplete** — arXiv HTML often has only section headers, not the full body text. Always fallback to PDF for complete content.
- **PDF may also be incomplete or garbled** — arXiv PDFs are converted from TeX. Complex equations, tables, and section references can be misrendered. The safest source is the TeX e-print tarball (`arxiv.org/e-print/<id>`).
- **TeX extraction command**: `wget -qO- "https://arxiv.org/e-print/<paper-id>" | tar -xz --to-stdout sections/appendix.tex 2>/dev/null` — gets a specific section. Or extract all: `tar -xzf <file>.tar.gz -C /tmp/papersrc/` then read `.tex` files.
- **TeX files have LaTeX markup** — strip with `sed` or just read around equation environments. The verbal descriptions and table content is clean even with math commands.
- **Confusing arXiv IDs**: sometimes e-print endpoint uses the numeric ID (e.g., `2602.06036`) while the PDF page uses `abs/2602.06036`. The e-print ID is the same number without the `abs/` prefix.
- **web_extract fails on arXiv raw GitHub URLs** — the markdown-to-text conversion doesn't work well. Use `curl` directly to fetch raw content from GitHub.
- **PDF extraction with PyMuPDF**: works well, `page.get_text()` returns clean text. No need for OCR.
- **Paper authors may change architecture details between v1 and v2** — always check arxiv.org/abs/ID for the latest version. The version suffix in the ID (v1 vs v2) matters.
- **Loss function details are usually in the appendix** — do not stop at section 4 "Training"; the actual formula with hyperparameters is in Appendix A.
- **Hardware in paper is always better than yours** — explicitly compare paper GPU vs Jetson (VRAM, compute, memory BW) when adapting.
- **Do not extrapolate beyond paper data** — If the paper tests block sizes [8, 16] and you conclude block 256 would give tau < 2, mark that as EXTRAPOLATION, not paper fact. Report what the paper actually measured and what your analysis projects separately.
- **User expects self-directed work** — do not ask "which model should we use" or "which block size". Read the paper, decide based on experiments, and justify in the deliverable.
- **Training data availability** — check if the training recipe is actually open-source. Many papers say "will release soon" but the code is not available at analysis time. Account for this in the plan (reimplement from paper description).

## Reference Files

- `references/ablation-table-reading-guide.md` — how to read and interpret common ablation table shapes (block size, layers, features, KV injection) with examples from DFlash paper

## Related Skills

- `arxiv` — finding and reading arXiv papers
- `ocr-and-documents` — local PDF text extraction if PyMuPDF is not available
- `hermes-agent-skill-authoring` — creating well-structured skills
