# Russian AI Market — Localization Knowledge Bank (July 2026)

Condensed data for adapting global AI agent analysis to the Russian market.
Covers: market size, API pricing, labor costs, regulations, adoption cases,
build-vs-buy TCO in rubles. **Half-life ~6 months** — verify before citing.

## Russian AI Market Size

| Metric | Value | Source |
|--------|-------|--------|
| Big Data + AI market (2025) | 520 billion RUB (+20% YoY) | Incomand.ru |
| AI software market (2025) | 25 billion RUB (+27% YoY) | Tadviser |
| AI platforms segment growth | +53.5% YoY | Apple Hills Digital |
| CAGR forecast to 2030 | 22.7% | Apple Hills |
| LLM access market | ~3 billion RUB/year | Tadviser |
| Global AI agents market (context) | $9.8B (2025) -> $220.9B (2035) | Vedomosti |

## Russian LLM API Pricing (per 1000 tokens, RUB)

| Provider / Model | Input | Output | Context | Notes |
|------------------|-------|--------|---------|-------|
| GigaChat-2 Lite | 0.065 | 0.065 | 32K | Cheapest; FSTEK, 1C/Bitrix24 |
| GigaChat-2 Pro | ~0.24 | ~0.24 | 32K | Comparable to GPT-4o on Russian |
| GigaChat-2 Max | 0.65 | 0.65 | 128K | Best quality |
| YandexGPT 5 Lite | ~0.17 | ~0.17 | 32K | 1M tokens/month free (PERS tier) |
| YandexGPT 5.1 Pro | ~1.04 | ~1.04 | 128K | Most powerful Yandex model |

Key: GigaChat-2 Lite is **~38x cheaper** than GPT-4o on inference. Russian APIs
work without VPN, payment in RUB, 152-FZ compliant.

Free tier: GigaChat = 1M tokens/year; YandexGPT = 1M tokens/month.

## Russian IT Labor Costs (monthly, RUB, 2025-2026)

| Role | Median | Senior range | Source |
|------|--------|-------------|--------|
| ML engineer | 225,000 | 300K-450K | Practicum, IT Institute |
| AI engineer | 220,000 | 300K-500K | thecode.media |
| Data Scientist | 252,000 | 300K-500K | hh.ru, IT Institute |
| MLOps engineer | 250,000 | 350K-500K | Habr Career, RBC |
| DevOps engineer | 210,000 | 300K-450K | hh.ru |
| Python developer | 165,000 | 250K-380K | hh.ru |
| ML developer | 229,000 | 350K-500K | career.habr.com |

**Team cost for enterprise agent (5 people):** ~1.14M RUB/month FOT,
~15.7M RUB/year FOT, ~22M RUB/year with taxes/overhead.

## Build vs Buy TCO — Russia (3-year, RUB)

| | BUILD | BUY (RU SaaS) | BUY (OSS self-host) |
|---|-------|---------------|---------------------|
| Upfront | 3M-15M | 0-500K | 0-200K |
| Monthly | 500K-1.5M | 50K-300K | 30K-100K |
| 3yr TCO | 20M-65M | 2M-12M | 1M-4M |
| Time-to-value | 6-18 months | 2-8 weeks | 1-4 weeks |

## Custom Agent Development Cost (Russia, RUB)

| Tier | Cost | Source |
|------|------|--------|
| Simple RAG bot | 150K-300K | agentech.ru, FriendAdmin |
| Production agent (multi-step, RAG) | 500K-800K | agentech.ru |
| Enterprise (orchestration, security) | 5M-15M+ | ai-journal.ru |
| Range across market | 50K-10M | ai-journal.ru |

## Russian Regulatory Landscape

| Regulation | Status | Impact on agents |
|------------|--------|-----------------|
| 152-FZ (Personal Data) | Active, tightening 2025-26 | Data must stay in RF; automated PD processing needs consent; fines up to 18M RUB |
| AI Law (Gosduma) | Passed Jul 8, 2026 (2nd+3rd reading) | Key rules for AI in RF: ethics, human control, regulatory sandboxes |
| Minstsifry AI concept | In development 2025-26 | Risk classification, accountability |
| FSTEK certification | Active | Mandatory for gov sector AI |
| Russian Software Registry | 24,300+ solutions (+24% 2024) | Gov companies must use registry software; GigaChat/YandexGPT/1C listed |
| Regulatory sandboxes (EPR) | Active since 2020, expanding | Legal sandboxes for AI agent testing in regulated industries |

Critical: **Foreign SaaS (Salesforce, MS Copilot) is unusable** for gov companies
and financial sector due to 152-FZ + registry requirements. Custom agents and
Russian platforms are the **only legal path** for these segments.

## Russian Platform Landscape

| Platform | Type | Registry | Pricing |
|----------|------|----------|---------|
| GigaChat-2 / GigaCowork (Sber) | Proprietary | Yes | 0.065-0.65 RUB/1K tok |
| YandexGPT 5 / Alisa Pro (Yandex) | Proprietary | Yes | ~0.17-1.04 RUB/1K tok |
| MTS AI / Kodify (MTS) | Proprietary | Yes | On request |
| Rosatom AI platform | Proprietary | Yes (Jul 2026) | On request |
| 1F Assistant (1Forma) | Proprietary | Yes | On request |
| OpenWebUI + Ollama (imported OSS) | OSS | **No** | 0 RUB |
| Hermes Agent (imported OSS) | OSS | **No** | 0 RUB |
| n8n (self-hosted) | Fair-code | **No** | 0 RUB |

Gap insight: **No Russian open-source AI agent in the domestic software registry.**
First such project would have huge competitive advantage on gov market.

## Russian Adoption Cases

| Company | Case | Effect |
|---------|------|--------|
| Sber | GigaChat + GigaCowork (TsIPR-2026) | 450B RUB (2025) -> 550B RUB (2026 forecast, Gref) |
| Sber | AI investment 2026 | 350B RUB (2x YoY) |
| Yandex | Alisa AI agents (Oct 2025) | Booking, shopping, search for millions |
| Rosatom | AI agent platform | Registry of domestic SW (Jul 2026) |
| MTS | Agent marketplace (MTS Link) | Companies sell custom agents |
| 1C | AI in accounting | Automated primary docs, FNS responses |

## Localization Adaptation Pattern

When adapting global AI market analysis to Russia, these dimensions MUST be
recalculated:

1. **Currency** — convert all $ to RUB, recalculate TCO with local salaries
2. **Labor costs** — Russian ML salaries are 3-5x lower than US/EU but still
   the dominant TCO component (60-70% of build cost)
3. **API pricing** — GigaChat/YandexGPT are 15-40x cheaper than GPT-4o; this
   flips the build-vs-buy calculus for inference-heavy workloads
4. **Regulatory** — 152-FZ + software registry = foreign SaaS blocked for
   gov/finance; this is a hard constraint, not a preference
5. **Platform landscape** — no Russian OSS AI agent in registry = gap/opportunity
6. **Adoption funnel** — same shape as global (88% pilot -> 5% EBIT impact) but
   shifted 6-12 months behind due to sanctions, GPU access, talent shortage

## Search Query Patterns (Russian Market)

| Data needed | Query pattern (RU) |
|-------------|-------------------|
| IT salaries | `зарплата {role} Россия 2025 2026 средняя hh.ru рубли` |
| Dev cost | `разработка ИИ агента стоимость рубли Россия 2025 2026 цена` |
| Market size | `российский рынок ИИ размер 2025 2026 прогноз млрд рублей` |
| API pricing | `GigaChat API тарифы цена за 1000 токенов рубли 2026` / `YandexGPT API стоимость тарифы рубли 2025 2026` |
| Regulation | `152-ФЗ персональные данные ИИ агенты регулирование Россия 2025 2026` |
| Company cases | `кейсы внедрения ИИ агентов Россия 2025 2026 {company} результаты ROI` |
| Platforms | `российские ИИ агенты платформы компании 2025 2026` |
| Import substitution | `импортозамещение ИИ Россия реестр отечественного ПО ФСТЭК 2025 2026` |
