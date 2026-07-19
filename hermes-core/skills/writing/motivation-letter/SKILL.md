---
name: motivation-letter
description: Write academic motivation letters for Russian master's programs with a 4-phase workflow - research, extract, draft, validate
---

# Motivation Letter — Russian Master's Programs

Full-cycle workflow for writing admission motivation letters for competitive Russian AI/ML master's programs, tested on ITMO AI Talent Hub Junior ML Contest 2026.

## When to use

- Writing a motivation letter for Russian master's programs (магистратура)
- The program is competitive (3+ applicants per place)
- The candidate has industry experience (not fresh out of bachelor's)
- The letter must fit 1 A4 page (~2500 chars with spaces)

## Full-cycle workflow

### Phase 1: Deep research on the program

Go beyond the program's landing page:

1. **Read the program leader's recent writing** — blog posts, Habr articles, interviews. Find their stated vision and recent pivots. This is your most valuable source.
2. **Find awards/recognition** — Generation AI Award, Yandex ML Prize, ratings. Signals what THEY are proud of.
3. **Identify the current pivot** — programs evolve. The 2024 program is not the 2026 program. Find what changed recently.
4. **Extract admission criteria** — JMLC vs portfolio contest vs exams. Know the format.
5. **Find real submission examples** — GitHub repos with CONTEST_READY.md, Habr success stories.
6. **Note partner companies** — X5, Sber AI, MTS, etc. Shows the ecosystem.

### Phase 2: Extract from resume

Map candidate's experience to program's stated direction:

1. **Find the project that aligns with the program's pivot** — this becomes the letter's opening hook, not generic "I have N years of experience."
2. **Extract 2-3 measurable results** — percentages, multipliers, team sizes.
3. **Identify the unique differentiator** — something no other applicant will have (non-CS background that's actually an asset, rare skill combination, teaching experience).
4. **List technologies that match the program's tracks** — if they do Agentic AI, list LangChain/LangGraph; if MLOps, list Kubernetes/MLflow.

### Phase 3: Structure the letter

Six paragraphs, strictly in this order:

| # | Purpose | Example |
|---|---|---|
| 1 | **Project hook** — your main project, not your bio | "Мой основной проект — архитектура универсального AI-агента..." |
| 2 | **Experience bridge** — 2-3 achievements, then why this field matters | "...я вижу, как Agentic AI переходит от экспериментов к инженерной дисциплине..." |
| 3 | **Why THIS program** — name the leader, cite the pivot, mention awards | "Дмитрий Ботов писал в июле 2026: переход к Agentic AI-трекам..." |
| 4 | **Why this admission format** — JMLC vs exams, portfolio vs tests | "Я не теоретик, сдающий экзамены. Я практик..." |
| 5 | **What you bring** — unique differentiator + teaching + industry expertise | "Мой бакалавриат ВШЭ по психометрике дал..." |
| 6 | **Career goal** — specific role, not "I want to grow" | "Возглавить AI-направление..." |

### Phase 4: Validate against rubric

Run the 27-point validation checklist (see `references/validation-checklist.md`).

Key constraints:
- **Max 2500 characters with spaces** (Russian standard for 1 A4 page)
- **Zero anti-patterns**: "хочу развиваться", "мечтаю", "с детства", "всегда интересовался", "очень нравится", "пожалуйста", "буду благодарен", "надеюсь", "прошу рассмотреть", "заранее спасибо"
- **No curriculum vitae in prose** — don't retell the CV, reference it
- **No generic praise** — "ваша программа лучшая" without evidence is worse than nothing

## Pitfalls

- **Writing before researching**: a generic letter is worse than no letter. The research phase IS the writing phase.
- **Opening with biography**: "Меня зовут X, мне Y лет, я закончил Z..." — the reader is already bored. Open with the project.
- **Not naming names**: referencing the program leader by name (Дмитрий Ботов) shows you read THEIR material, not just the landing page.
- **Apologizing for gaps**: never frame a non-standard background as a weakness. Psychometrics becomes statistical validation for AI agents. Frame it as an asset.
- **Exceeding the limit**: 2500 chars is a hard filter in some systems. If over, your letter may be truncated mid-sentence.
- **Using "вы" inconsistently**: pick one register (formal "вы" is standard) and stick to it throughout.
- **Leading with a WORK project when a personal OSS project exists**: for JMLC, the hook project must be fully presentable — code repo linkable, no NDA/IP constraints, unique to the candidate. A personal open-source agent (CLI/web/TG/Android, multi-agent, tool use, memory, production-deployed) beats a bigger Sber/TMH work project that can't be shared or distinguished from the team's contribution. Work projects go in paragraph 2 as experience bridge; the personal OSS project owns paragraph 1. (Learned July 2026: first draft led with work projects and underperformed the candidate's own version that led with the personal agent.)
- **Assuming degree completion from the resume**: Russian CVs list education as "YYYY / Высшее / ВУЗ / факультет" — the YYYY+Высшее format does NOT confirm graduation. ALWAYS verify with the candidate whether each degree was completed. If unfinished, DO NOT hide it and DO NOT mislabel the level (бакалавриат vs магистратура). Own it explicitly and reframe: "Моя магистратура ВШЭ по психометрике не закончена, но дала понимание статистической валидации" — unfinished becomes an asset (statistical rigor for AI evaluation), not a liability.
- **Russian comma errors that pass spellcheck but fail native readers**: run a final scan for (a) comma placement around "но" — comma goes BEFORE "но", never after ("не закончена, но дала" ✓ / "не закончена но, дала" ✗); (b) missing comma before participial phrases ("от исследований, основанных на статистике" ✓ / "от исследований основанных на статистике" ✗). These are the two most common LLM-introduced errors in Russian motivation letters.

## Execution notes (practical pipeline)

End-to-end flow that has worked in production for JMLC submission:

1. **Resume ingestion** — if candidate provides RTF (common from hh.ru/Superjob exports), convert before reading:
   ```bash
   libreoffice --headless --convert-to txt:"Text (encoded):UTF8" "resume.rtf" --outdir /tmp
   ```
2. **Program research** — if `web_extract` fails with "search-only backend cannot extract", fall back to `curl + python regex strip`:
   ```bash
   curl -sL --max-time 30 -A "Mozilla/5.0" "https://ai.itmo.ru/junior_ml_contest" | \
     python3 -c "import sys,re; h=sys.stdin.read(); h=re.sub(r'<script[^>]*>.*?</script>','',h,flags=re.S); h=re.sub(r'<style[^>]*>.*?</style>','',h,flags=re.S); h=re.sub(r'<[^>]+>',' ',h); print(re.sub(r'\s+',' ',h)[:10000])"
   ```
   Browser navigation on ai.itmo.ru has been observed to time out at 60s — prefer curl.
3. **Letter validation** — run the 27-point check as a script instead of retyping inline:
   ```bash
   python3 ~/.hermes/skills/writing/motivation-letter/scripts/validate_letter.py <letter.txt>
   ```
   Exit code 0 = 27/27 pass.
4. **PDF generation** — Russian letters need a Cyrillic-capable TTF. reportlab default Helvetica mangles Cyrillic:
   ```python
   from reportlab.pdfbase import pdfmetrics
   from reportlab.pdfbase.ttfonts import TTFont
   pdfmetrics.registerFont(TTFont('Cyrl', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
   # then use fontName='Cyrl' in ParagraphStyle
   ```
   Target: 1 page A4, 2cm margins, 10.5pt body, justified.

## Pitfall: deadline awareness

JMLC has 3 waves per year; Wave 3 typically closes ~July 20. When the candidate mentions JMLC after July 1, treat the deadline as T-minus-days and surface it at the top of the response — do not let the letter be ready one day late.

## Reference files

- `references/validation-checklist.md` — the full 27-point rubric with anti-pattern list (human-readable spec; `scripts/validate_letter.py` is the runnable mirror — keep both in sync)
- `references/itmo-ai-talent-hub.md` — program intelligence: leadership, pivot, tracks, partners, admission paths, JMLC rubric, project types, submission package, dates (July 2026 snapshot)
- `scripts/validate_letter.py` — runnable 27-point validator. Pass letter path as arg, exit 0 = pass.
