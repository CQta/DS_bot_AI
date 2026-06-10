"""
ai_gm.py — Google Gemini-powered GM: action parser + narrative generator + event creator
"""

import json
import os

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


def get_gemini_api_key() -> str | None:
    """Return the Gemini API key from either supported env var name."""
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


API_KEY = get_gemini_api_key()
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("[AI] Warning: GOOGLE_API_KEY/GEMINI_API_KEY is not set. Gemini calls will fail until the key is configured.")

MODEL = "gemini-2.5-flash"  # допустимое имя модели Gemini


def list_available_models() -> list[str]:
    """Return available Gemini model names for this account/key."""
    try:
        models = genai.list_models()
        available = []
        seen = set()
        for model in models:
            name = getattr(model, "name", None)
            clean_name = name.replace("models/", "") if isinstance(name, str) else None
            if clean_name and clean_name not in seen:
                seen.add(clean_name)
                available.append(clean_name)
        return available
    except Exception as e:
        print(f"[AI Model List Error] {e}")
        return ["gemini-3.0-flash", "gemini-2.0-flash", "gemini-1.5-pro"]


def extract_json_payload(raw_text: str):
    """Extract and parse JSON from Gemini output, even when it contains markdown fences or trailing text."""
    text = raw_text.strip()

    if text.startswith("```"):
        text = text.split("```", 1)[1]
        if text.lower().startswith("json"):
            text = text[4:]

    text = text.strip().strip("`").strip()
    if not text:
        raise ValueError("Empty Gemini response")

    try:
        return json.JSONDecoder().raw_decode(text)[0]
    except json.JSONDecodeError:
        pass

    first_brace = text.find("{")
    first_bracket = text.find("[")
    start = -1
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start = first_brace
    elif first_bracket != -1:
        start = first_bracket

    if start == -1:
        raise ValueError("No JSON object/array found in Gemini response")

    stack = []
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char in "[{":
            stack.append(char)
            continue

        if char in "]}":
            if not stack:
                break
            opener = stack[-1]
            if (opener == "{" and char == "}") or (opener == "[" and char == "]"):
                stack.pop()
                if not stack:
                    candidate = text[start:index + 1]
                    return json.loads(candidate)
            else:
                break

    raise ValueError("Could not recover valid JSON from Gemini response")


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
        model = genai.GenerativeModel(MODEL)
        resp = model.generate_content(
            [PARSER_SYSTEM, context],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1000,
                temperature=0.7
            )
        )
        raw = resp.text.strip()
        actions = extract_json_payload(raw)
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
        model = genai.GenerativeModel(MODEL)
        resp = model.generate_content(
            [NARRATIVE_SYSTEM, prompt],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=300,
                temperature=0.8
            )
        )
        return resp.text.strip()
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
        model = genai.GenerativeModel(MODEL)
        resp = model.generate_content(
            [EVENT_SYSTEM, prompt],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=500,
                temperature=0.7
            )
        )
        raw = resp.text.strip()
        return extract_json_payload(raw)
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
    arbitration_system = ("Ты — справедливый арбитр игры «Эпоха Осколков». "
                          "Оцени логичность действия в контексте мира. Верни только JSON.")
    try:
        model = genai.GenerativeModel(MODEL)
        resp = model.generate_content(
            [arbitration_system, prompt],
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=300,
                temperature=0.6
            )
        )
        raw = resp.text.strip()
        return extract_json_payload(raw)
    except Exception:
        return {"valid": True, "reason": "", "suggested_type": "OTHER", "difficulty_mod": 0}
