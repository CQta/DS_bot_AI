"""
ai_gm.py — Anthropic-powered GM: action parser + narrative generator + event creator
"""

import json
import os
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"

# ── System prompts ─────────────────────────────────────────────────────────

PARSER_SYSTEM = """Ты — парсер действий для текстовой стратегической игры «Эпоха Осколков».
Твоя задача: разобрать СВОБОДНЫЙ ТЕКСТ игрока и вернуть ТОЛЬКО JSON массив действий.

Допустимые типы действий (action_type):
- GATHER   — сбор еды, ресурсов с природы
- MINE     — добыча угля, камня, металла в шахтах/горах
- BUILD    — строительство зданий, стен, туннелей
- RESEARCH — изучение технологий, науки, крафт инструментов
- MOVE     — перемещение юнитов
- ATTACK   — нападение на врага или зверей
- MIRACLE  — применение Чуда бога
- DIPLOMACY— переговоры, союзы, торговля
- SPY      — тайная разведка
- TRADE    — торговый обмен
- OTHER    — всё остальное

Формат ответа — ТОЛЬКО JSON, без пояснений:
[
  {
    "action_type": "GATHER",
    "units": 20,
    "description": "краткое описание",
    "target": "озеро / горы / лес / etc (если указано)",
    "is_secret": false
  }
]

Если игрок пишет про бога/чудо — используй action_type MIRACLE.
Если юниты не указаны — поставь units: 10.
Суммарные units по всем действиям не должны превышать population фракции."""

NARRATIVE_SYSTEM = """Ты — Хроникёр мира Пангеи-Примы, ведёшь летопись текстовой стратегии.
Напиши КОРОТКИЙ (2-4 предложения) атмосферный результат игрового действия на русском языке.
Учитывай: расу, действие, исход броска, сезон и температуру.
НЕ меняй числа ресурсов — только описывай событие. Пиши живо, кратко, по делу."""

EVENT_SYSTEM = """Ты — Хроникёр мира Пангеи-Примы. Придумай одно глобальное событие для игры.
Верни ТОЛЬКО JSON:
{
  "title": "Название события",
  "description": "2-3 предложения описания",
  "mechanical_effect": "краткое описание механического эффекта на все фракции"
}
Событие должно логично вытекать из текущего состояния мира и быть интересным для игроков."""


# ── Public functions ──────────────────────────────────────────────────────────

async def parse_actions(player_text: str, faction: dict) -> list[dict]:
    """Parse free-form player input into structured action list."""
    context = (
        f"Фракция: {faction['faction_name']} (раса: {faction['race']})\n"
        f"Население: {faction['population']}\n"
        f"Путь: {faction['path']}, Мировоззрение: {faction['alignment']}\n"
        f"Ресурсы: еда={faction.get('food',0)}, "
        f"топливо={faction.get('fuel',0)}, "
        f"камень={faction.get('stone',0)}, "
        f"дерево={faction.get('wood',0)}\n"
        f"Действие игрока: {player_text}"
    )
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=PARSER_SYSTEM,
            messages=[{"role": "user", "content": context}]
        )
        raw = resp.content[0].text.strip()
        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        actions = json.loads(raw)
        # Validate total units
        total = sum(a.get("units", 0) for a in actions)
        pop = faction.get("population", 50)
        if total > pop:
            scale = pop / total
            for a in actions:
                a["units"] = max(1, int(a["units"] * scale))
        return actions
    except Exception as e:
        print(f"[AI Parser Error] {e}")
        # Fallback: treat whole text as single OTHER action
        return [{"action_type": "OTHER", "units": 10,
                 "description": player_text[:200], "target": "", "is_secret": False}]


async def generate_narrative(faction: dict, action: dict,
                              outcome: str, delta: dict,
                              season: str, temperature: int) -> str:
    """Generate atmospheric result text for a resolved action."""
    prompt = (
        f"Раса: {faction['race']} ({faction['faction_name']})\n"
        f"Действие: {action['action_type']} — {action['description']}\n"
        f"Юнитов: {action.get('units', 0)}\n"
        f"Исход: {outcome}\n"
        f"Изменение ресурсов: {delta}\n"
        f"Сезон: {season}, Температура: {temperature}°C\n"
        f"Напиши короткий атмосферный текст результата."
    )
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=NARRATIVE_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"[AI Narrative Error] {e}")
        return f"Действие завершено с исходом: {outcome}."


async def generate_global_event(factions: list[dict], season: str,
                                 temperature: int) -> dict:
    """Generate a global event based on current world state."""
    world_summary = "\n".join(
        f"- {f['faction_name']} ({f['race']}): "
        f"pop={f['population']}, food={f.get('food',0)}, fuel={f.get('fuel',0)}"
        for f in factions
    )
    prompt = (
        f"Сезон: {season}, Температура: {temperature}°C\n"
        f"Фракции:\n{world_summary}\n"
        f"Сгенерируй логичное глобальное событие."
    )
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=EVENT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[AI Event Error] {e}")
        return {
            "title": "Аномалия",
            "description": "В мире происходит нечто необычное.",
            "mechanical_effect": "Штрафов нет."
        }


async def arbitrate(faction: dict, action_description: str,
                    season: str) -> dict:
    """Decide if an unusual action is valid and how to handle it."""
    prompt = (
        f"Раса: {faction['race']}, Путь: {faction['path']}, "
        f"Мировоззрение: {faction['alignment']}\n"
        f"Действие: {action_description}\n"
        f"Сезон: {season}\n\n"
        f"Оцени действие и верни JSON:\n"
        f'{{"valid": true/false, "reason": "почему", '
        f'"suggested_type": "GATHER/BUILD/etc", "difficulty_mod": -3..+3}}'
    )
    try:
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=300,
            system="Ты — справедливый арбитр игры «Эпоха Осколков». "
                   "Оцени логичность действия в контексте мира. Верни только JSON.",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return {"valid": True, "reason": "", "suggested_type": "OTHER", "difficulty_mod": 0}
