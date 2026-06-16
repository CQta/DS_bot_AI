"""
ai_gm.py — Google Gemini-powered GM: action parser + narrative generator + event creator
"""

import json
import os
import re

from google import genai
from dotenv import load_dotenv

import mechanics

load_dotenv()


def get_gemini_api_key() -> str | None:
    """Return the Gemini API key from either supported env var name."""
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


API_KEY = get_gemini_api_key()
if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    print("[AI] Warning: GOOGLE_API_KEY/GEMINI_API_KEY is not set. Gemini calls will fail until the key is configured.")
    client = None

MODEL = "gemini-3.1-flash-lite"  # допустимое имя модели Gemini


def list_available_models() -> list[str]:
    """Return available Gemini model names for this account/key."""
    if not client:
        return ["gemini-3.0-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    try:
        available = []
        seen = set()
        for model in client.models.list():
            name = getattr(model, "name", None)
            clean_name = name.replace("models/", "") if isinstance(name, str) else None
            if clean_name and clean_name not in seen:
                seen.add(clean_name)
                available.append(clean_name)
        return available
    except Exception as e:
        print(f"[AI Model List Error] {e}")
        return ["gemini-3.0-flash", "gemini-2.5-flash", "gemini-2.0-flash"]


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


def enrich_action_with_units(action: dict) -> dict:
    """Append the unit count to the action description for clearer player feedback."""
    action = dict(action)
    units = int(action.get("units") or 10)
    difficulty = int(action.get("difficulty") or 2)
    description = str(action.get("description") or "").strip()

    if not description:
        description = action.get("action_type", "OTHER")

    if f"{units} юнит" not in description.lower():
        action["description"] = f"{description} (выделено {units} юнитов)"

    action["difficulty"] = difficulty
    return action


# ── System prompts ─────────────────────────────────────────────────────────

PARSER_SYSTEM = """Ты — парсер действий для текстовой стратегической игры «Эпоха Осколков».
Твоя задача: для данного описания вернуть ТОЛЬКО JSON ответ.

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

Формат ответа — ТОЛЬКО JSON:
{
  "action_type": "GATHER",
  "target": "лес / шахта / враг / etc",
  "is_secret": false
}
"""

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

UNIT_PATTERN = re.compile(
    r"(?P<units>\d+)\s*(?:юнит(?:ов|а|ы)?|бойц(?:ов|ы)?|воин(?:ов|ы)?|рабоч(?:их|ие)?|отряд(?:ов|ы)?|солдат(?:ов)?)",
    re.I
)
SECRET_PATTERN = re.compile(r"\b(тайн|скрыт|секрет|стелс|шпион|разведка)\b", re.I)


def split_player_text(player_text: str) -> list[str]:
    """Split free-form input into action segments using semicolon as separator."""
    parts = [part.strip() for part in player_text.split(";") if part.strip()]
    return parts if parts else [player_text.strip()]


def extract_units_from_segment(segment: str) -> tuple[int, str]:
    """Extract explicit unit count from a segment and return cleaned segment text."""
    match = UNIT_PATTERN.search(segment)
    if match:
        units = int(match.group("units"))
        cleaned = (segment[:match.start()] + segment[match.end():]).strip(" ,.-")
        if not cleaned:
            cleaned = segment.strip()
        return units, cleaned

    # Fallback: use first leading number if no unit keyword found
    digits = re.match(r"^(\d+)\b", segment.strip())
    if digits:
        units = int(digits.group(1))
        cleaned = segment[digits.end():].strip(" ,.-")
        if not cleaned:
            cleaned = segment.strip()
        return units, cleaned

    return 10, segment.strip()


def segment_is_secret(segment: str) -> bool:
    return bool(SECRET_PATTERN.search(segment))


async def parse_actions(player_text: str, faction: dict) -> list[dict]:
    """Parse free-form player input into structured action list in a single API call."""
    segments = split_player_text(player_text)
    action_specs = []

    for i, segment in enumerate(segments, 1):
        units, cleaned_segment = extract_units_from_segment(segment)
        is_secret = segment_is_secret(segment)
        action_specs.append({
            "id": i,
            "units": units,
            "description": cleaned_segment,
            "is_secret": is_secret
        })

    prompt = (
        "Проанализируй список действий фракции. Для каждого укажи action_type и target.\n"
        "Формат ответа — массив JSON объектов с полями: id, action_type, target, is_secret.\n\n"
        "Действия:\n"
    )
    for spec in action_specs:
        prompt += f"{spec['id']}. ({spec['units']} юнитов) {spec['description']}\n"

    try:
        if not client:
            raise RuntimeError("Gemini client not initialized. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
        
        resp = client.models.generate_content(
            model=MODEL,
            contents=[PARSER_SYSTEM, prompt],
            config={
                "max_output_tokens": 500,
                "temperature": 0.3
            }
        )
        raw = resp.text.strip()
        parsed = extract_json_payload(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]

        # Map results back to original specs
        all_actions = []
        for spec in action_specs:
            result = next((p for p in parsed if p.get("id") == spec["id"]), None)
            action = {
                "action_type": result.get("action_type", "OTHER") if result else "OTHER",
                "target": result.get("target", "") if result else "",
                "units": spec["units"],
                "difficulty": mechanics.calc_action_difficulty(
                    result.get("action_type", "OTHER") if result else "OTHER"
                ),
                "description": spec["description"],
                "is_secret": spec["is_secret"] or (result.get("is_secret", False) if result else False)
            }
            action = enrich_action_with_units(action)
            all_actions.append(action)

        # Validate total units
        total = sum(a.get("units", 0) for a in all_actions)
        pop = faction.get("population", 50)
        if total > pop and total > 0:
            scale = pop / total
            for a in all_actions:
                a["units"] = max(1, int(a["units"] * scale))

        return all_actions

    except Exception as e:
        print(f"[AI Parser Error] {e}")
        # Fallback: return each segment as OTHER action
        fallback = []
        for spec in action_specs:
            action = enrich_action_with_units({
                "action_type": "OTHER",
                "units": spec["units"],
                "difficulty": 2,
                "description": spec["description"],
                "target": "",
                "is_secret": spec["is_secret"]
            })
            fallback.append(action)
        return fallback


async def generate_narrative(faction: dict, action: dict,
                              outcome: str, delta: dict,
                              season: str, temperature: int,
                              difficulty: int, dice: int, modifier: int) -> str:
    """Generate atmospheric result text for a resolved action."""
    prompt = (
        f"Раса: {faction['race']} ({faction['faction_name']})\n"
        f"Действие: {action['action_type']} — {action['description']}\n"
        f"Юнитов: {action.get('units', 0)}\n"
        f"Сложность: {difficulty}\n"
        f"Кубик: {dice}, Модификатор: {modifier}\n"
        f"Исход: {outcome}\n"
        f"Изменение ресурсов: {delta}\n"
        f"Сезон: {season}, Температура: {temperature}°C\n"
        f"Ты описываешь событие на русском языке. Не меняй исход, не интерпретируй числа иначе, не пересчитай результат. Только кратко опиши то, что уже произошло."
    )
    try:
        if not client:
            raise RuntimeError("Gemini client not initialized. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
        
        resp = client.models.generate_content(
            model=MODEL,
            contents=[NARRATIVE_SYSTEM, prompt],
            config={
                "max_output_tokens": 2500,
                "temperature": 0.8
            }
        )
        print(f"[AI Narrative] {resp.text.strip()}")
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
        if not client:
            raise RuntimeError("Gemini client not initialized. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
        
        resp = client.models.generate_content(
            model=MODEL,
            contents=[EVENT_SYSTEM, prompt],
            config={
                "max_output_tokens": 500,
                "temperature": 0.7
            }
        )
        raw = resp.text.strip()
        print(f"[AI Event] {raw}")
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
        if not client:
            raise RuntimeError("Gemini client not initialized. Set GOOGLE_API_KEY or GEMINI_API_KEY.")
        
        resp = client.models.generate_content(
            model=MODEL,
            contents=[arbitration_system, prompt],
            config={
                "max_output_tokens": 300,
                "temperature": 0.6
            }
        )
        raw = resp.text.strip()
        return extract_json_payload(raw)
    except Exception:
        return {"valid": True, "reason": "", "suggested_type": "OTHER", "difficulty_mod": 0}
