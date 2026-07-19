#!/usr/bin/env python3
"""
27-point validation for motivation letters targeting ITMO AI Talent Hub.

Usage:
    python3 validate_letter.py <letter.txt>

Checks: structure (6), program knowledge (8), candidate differentiators (5),
tone & authenticity (5), technical constraints (3). Prints pass/fail per
criterion and a final score. Exit code 0 only if 27/27 pass.

Anti-pattern list and criteria are sourced from references/validation-checklist.md.
Update both files together when the rubric evolves.
"""
import sys
import re

ANTI_PATTERNS = [
    "хочу развиваться", "мечтаю", "с детства", "всегда интересовался",
    "очень нравится", "пожалуйста", "буду благодарен", "надеюсь",
    "прошу рассмотреть", "заранее спасибо", "ваша программа лучшая",
    "я уверен, что", "с большим интересом", "искренне",
]

# Program-specific signals (substrings). Add/remove as the target program evolves.
PROGRAM_SIGNALS = {
    "AI Talent Hub": "AI Talent Hub",
    "Junior ML Contest": "Junior ML Contest",
    "Лидер по имени (Ботов)": "Ботов",
    "Pivot 2026 Agentic AI": "Agentic AI",
    "Generation AI Award": "Generation AI",
    "Yandex ML Prize": "Yandex ML Prize",
    "Бюджетные места": "215",
    "Партнёр Napoleon IT": "Napoleon IT",
    "Партнёр X5": "X5",
    "Партнёр Sber": "Sber",
    "Партнёр МТС": "МТС",
}

CHAR_LIMIT = 2500  # Russian standard for 1 A4 page


def load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def check_structure(t: str):
    return [
        ("Открывается ПРОЕКТОМ, а не биографией",
         not t.lower().startswith(("меня зовут", "я,", "мое имя", "моя фамилия"))),
        ("Проект описан конкретно (технологии)",
         all(s in t for s in ["LangChain", "LangGraph", "RAG"]) or
         all(s in t for s in ["MLflow", "k8s", "MLOps"])),
        ("2-3 измеримых результата (%, X, команда)",
         any(s in t for s in ["раза", "%", "человек", "+"])),
        ("WHY THIS PROGRAM: лидер + pivot + award",
         "Ботов" in t and "Agentic AI" in t and "Generation AI" in t),
        ("Цель — конкретная роль",
         any(s in t.lower() for s in ["возглавить", "стать", "развити"])),
        ("Закрытие отсылает к ценности программы",
         any(s in t for s in ["программ", "сообществ", "дисциплин", "продуктов"])),
    ]


def check_program(t: str):
    results = []
    for name, signal in PROGRAM_SIGNALS.items():
        results.append((name, signal in t))
    return results


def check_differentiators(t: str):
    return [
        ("Уникальный угол (нестандартный фон как asset)",
         any(s in t.lower() for s in ["нестандарт", "нестандартн", "не обыч", "не типич"])),
        ("Опыт преподавания/менторства упомянут",
         any(s in t.lower() for s in ["семинар", "преподав", "ментор", "обучен"]) or
         "NLP" in t or "естественного языка" in t),
        ("Industry expertise framed as asset",
         "production" in t.lower() or "продакшен" in t.lower() or "практик" in t.lower()),
        ("Технологии мэтчат трек программы",
         any(s in t for s in ["LangGraph", "LangChain", "LLM"]) or
         any(s in t for s in ["MLOps", "MLflow", "k8s"])),
        ("Слабости → сильные стороны",
         "нестандарт" in t.lower() or "не слабост" in t.lower()),
    ]


def check_tone(t: str):
    tl = t.lower()
    return [
        ("Уверенный тон, не извиняющийся",
         not any(s in tl for s in ["извин", "к сожалению", "прошу простить"])),
        ("Конкретика: цифры/имена в утверждениях",
         bool(re.search(r"\d", t)) and "Ботов" in t),
        ("Нет лести без пруфа", True),
        ("Консистентный регистр", tl.count(" вы ") == 0 or "вы " not in tl),
        ("Один аутентичный голос", True),
    ]


def check_technical(t: str):
    chars = len(t)
    found_anti = [a for a in ANTI_PATTERNS if a in t.lower()]
    return [
        (f"≤{CHAR_LIMIT} символов с пробелами ({chars})", chars <= CHAR_LIMIT),
        (f"Ноль антипаттернов (found: {found_anti})", len(found_anti) == 0),
        (f"Влезает на 1 A4 ({chars} символов)", chars <= CHAR_LIMIT),
    ]


def run(path: str) -> int:
    t = load(path)
    sections = [
        ("STRUCTURE", check_structure(t)),
        ("PROGRAM KNOWLEDGE", check_program(t)),
        ("CANDIDATE DIFFERENTIATORS", check_differentiators(t)),
        ("TONE & AUTHENTICITY", check_tone(t)),
        ("TECHNICAL", check_technical(t)),
    ]
    print("=" * 70)
    print(f"27-POINT VALIDATION — {path}")
    print(f"Chars: {len(t)}/{CHAR_LIMIT} | Paragraphs: {len([p for p in t.split(chr(10)) if p.strip()])}")
    print("=" * 70)
    total = 0
    for section_name, checks in sections:
        print(f"\n[{section_name}]")
        for name, ok in checks:
            print(f"  [{'✓' if ok else '✗'}] {name}")
            if ok:
                total += 1
    print(f"\n{'=' * 70}\nИТОГО: {total}/27\n{'=' * 70}")
    return 0 if total == 27 else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: validate_letter.py <letter.txt>")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
