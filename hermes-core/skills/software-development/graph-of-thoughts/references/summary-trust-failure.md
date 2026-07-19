# Post-Mortem: Summary-Trust Failure (2026-07-02)

## What happened

Агент получил сессию с двумя конфликтующими входами:
1. Мандат `clarify()` (MANDATORY — FIRST and ONLY action)
2. Context compact + Active Task (GUI desktop — кнопки Plan3/Claw)

Агент проигнорировал мандат, применил «latest message wins» к context compact, и приступил к анализу GUI.

## What the agent did wrong

1. **Поверил summary вместо кода.** Context compact утверждал:
   - «`switchAgentPreset` bails out без сессии» — FALSE (код уже исправлен)
   - «`useMessageStream` игнорирует `agent_id`» — FALSE (код уже обрабатывает)
   - «Кнопки вставляют `/agent` в композер» — FALSE (код уже использует `switchAgentPreset`)

   Все три утверждения были опровергнуты одним `read_file`.

2. **Построил 4-фазный план исправления несуществующих проблем.** План включал патчи для кода, который УЖЕ был правильным.

3. **Analysis paralysis.** Закончил сессию фразой «Скажи — начинаем execute?» — ни одной строки кода не изменено.

4. **Нарушил мандат clarify().** Системный гейт был проигнорирован в пользу conversational-эвристики.

## Root causes (системные)

| Причина | Проявление | Исправление |
|---------|-----------|-------------|
| Summary как источник истины | Агент верит утверждениям из context compact без проверки | Шаг 2.5 в GoT: верификация утверждений кодом |
| Нет self-audit после анализа | Агент не проверяет «мои предположения верны?» | Правило «Код > summary» |
| Нет лимита на планирование | Бесконечный анализ без execution | Правило «3 шага → execute» |
| Конфликт директив без эскалации | Агент сам решил, а не спросил | Pitfall «Clarify-mandate override trap» |

## Что было РЕАЛЬНО недоделано (после проверки кода)

- Индикатор активного агента в ChatHeader (статусбар показывает, чат — нет)
- End-to-end тест (сборка + перезапуск GUI)
- Мутации file_write_gate и observer_checkpoints

## Lessons encoded in skills

- `graph-of-thoughts`: добавлен Шаг 2.5 (верификация), правило 5 («Код > summary»), правило 6 («3 шага → execute»), pitfalls
- `intent-validation`: добавлен pitfall «Context-compact override trap»
- `plan`: добавлен pitfall «Plan-for-nothing trap», pre-plan verification gate
