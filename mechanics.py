"""
mechanics.py — Dice, outcome resolution, resource consumption, weather
"""

import random
import json
from typing import Optional

# ── Dice ─────────────────────────────────────────────────────────────────────

def roll_d20() -> int:
    return random.randint(1, 20)


def get_outcome(final_roll: int) -> str:
    if final_roll == 1:
        return "CRITICAL_FAILURE"
    elif final_roll <= 5:
        return "FAILURE"
    elif final_roll <= 10:
        return "PARTIAL_FAILURE"
    elif final_roll <= 15:
        return "PARTIAL_SUCCESS"
    elif final_roll <= 19:
        return "SUCCESS"
    else:
        return "CRITICAL_SUCCESS"


OUTCOME_LABELS = {
    "CRITICAL_FAILURE": "💥 Критический провал",
    "FAILURE": "❌ Провал",
    "PARTIAL_FAILURE": "⚠️ Плохо",
    "PARTIAL_SUCCESS": "🔶 Частичный успех",
    "SUCCESS": "✅ Успех",
    "CRITICAL_SUCCESS": "🌟 Критический успех",
}

OUTCOME_COLORS = {
    "CRITICAL_FAILURE": 0xFF0000,
    "FAILURE": 0xCC3333,
    "PARTIAL_FAILURE": 0xFF8C00,
    "PARTIAL_SUCCESS": 0xFFD700,
    "SUCCESS": 0x2ECC71,
    "CRITICAL_SUCCESS": 0x00FF88,
}


def calc_modifier(faction: dict, action_type: str) -> int:
    """Calculate stat modifier based on action type."""
    mapping = {
        "GATHER":   "stat_body",
        "BUILD":    "stat_body",
        "RESEARCH": "stat_mind",
        "MOVE":     "stat_body",
        "ATTACK":   "stat_body",
        "MIRACLE":  "stat_energy",
        "DIPLOMACY":"stat_concentration",
        "SPY":      "stat_concentration",
        "TRADE":    "stat_mind",
    }
    stat_key = mapping.get(action_type.upper(), "stat_body")
    stat_val = faction.get(stat_key, 5)
    # Modifier: (stat - 5) / 2, rounded down — similar to D&D feel
    return (stat_val - 5) // 2


# ── Resource calculation ──────────────────────────────────────────────────────

def calc_resource_delta(action_type: str, outcome: str,
                        units: int, faction: dict) -> dict:
    """
    Returns a dict of resource changes based on action type and outcome.
    Multipliers: CRITICAL_SUCCESS=1.5, SUCCESS=1.0, PARTIAL=0.5, FAIL=-0.1
    """
    multipliers = {
        "CRITICAL_SUCCESS": 1.5,
        "SUCCESS": 1.0,
        "PARTIAL_SUCCESS": 0.6,
        "PARTIAL_FAILURE": 0.3,
        "FAILURE": 0.0,
        "CRITICAL_FAILURE": -0.1,
    }
    m = multipliers.get(outcome, 0.5)
    base = units * 5  # base yield per unit

    delta = {}

    if action_type == "GATHER":
        delta["food"] = int(base * m * 1.5)
        delta["wood"] = int(base * m * 0.5)

    elif action_type == "MINE":
        delta["fuel"] = int(base * m * 1.2)
        delta["stone"] = int(base * m * 0.8)
        delta["metal"] = int(base * m * 0.3)

    elif action_type == "BUILD":
        # Building costs resources
        delta["wood"] = -int(units * 3)
        delta["stone"] = -int(units * 2)

    elif action_type == "RESEARCH":
        # No direct resource gain; handled by tech progress
        delta["faith"] = int(units * m * 0.5)

    elif action_type == "MIRACLE":
        delta["faith"] = -faction.get("miracle_cost", 20)

    elif action_type == "ATTACK":
        if m > 0:
            delta["food"] = int(base * m * 0.3)  # loot
        else:
            delta["food"] = -int(units * 2)  # losses cost food

    elif action_type == "TRADE":
        delta["food"] = int(base * m * 0.5)

    # Remove zero values
    return {k: v for k, v in delta.items() if v != 0}


# ── Per-turn consumption ──────────────────────────────────────────────────────

SEASONS_FUEL_MULT = {
    "AUTUMN": 1.0,
    "WINTER": 2.0,
    "SPRING": 1.0,
    "SUMMER": 0.7,
}

SEASONS_FOOD_MULT = {
    "AUTUMN": 1.0,
    "WINTER": 1.5,
    "SPRING": 1.2,
    "SUMMER": 1.0,
}


def calc_consumption(faction: dict, season: str) -> dict:
    """How many resources the faction consumes this turn."""
    pop = faction.get("population", 50)
    race = faction.get("race", "").lower()

    fuel_mult = SEASONS_FUEL_MULT.get(season, 1.0)
    food_mult = SEASONS_FOOD_MULT.get(season, 1.0)

    # Golimory eat coal (fuel = food for them)
    if "голимор" in race or "golimor" in race:
        return {
            "fuel": int(pop * 1.0 * fuel_mult),
            "food": 0,
        }

    # Magmatites need no food if near volcano (simplified: always 0)
    if "магматит" in race or "magmatit" in race:
        return {
            "fuel": 0,
            "food": 0,
        }

    # Everyone else
    return {
        "food": int(pop * 1.0 * food_mult),
        "fuel": int(pop * 0.3 * fuel_mult),
    }


def check_starvation(faction: dict, consumption: dict) -> list[str]:
    """Returns list of warning strings if resources are critically low."""
    warnings = []
    for res, amount in consumption.items():
        current = faction.get(res, 0)
        if current < amount:
            warnings.append(
                f"⚠️ **{faction['faction_name']}** не хватает `{res}` "
                f"(нужно {amount}, есть {current})!"
            )
    return warnings


# ── Weather ──────────────────────────────────────────────────────────────────

SEASON_CYCLE = ["AUTUMN", "WINTER", "SPRING", "SUMMER"]
SEASON_NAMES = {
    "AUTUMN": "Осень",
    "WINTER": "Зима",
    "SPRING": "Весна",
    "SUMMER": "Лето",
}

MONTHS = {
    "AUTUMN": ["Сентябрь", "Октябрь", "Ноябрь"],
    "WINTER": ["Декабрь", "Январь", "Февраль"],
    "SPRING": ["Март", "Апрель", "Май"],
    "SUMMER": ["Июнь", "Июль", "Август"],
}

BASE_TEMP = {
    "AUTUMN":  10,
    "WINTER": -25,
    "SPRING":  15,
    "SUMMER":  30,
}


def next_month(current_month: str, current_season: str,
               turn_number: int) -> tuple[str, str, int]:
    """Returns (new_month, new_season, new_temp)."""
    season_months = MONTHS[current_season]
    try:
        idx = season_months.index(current_month)
    except ValueError:
        idx = 0

    if idx < len(season_months) - 1:
        new_month = season_months[idx + 1]
        new_season = current_season
    else:
        # Advance season
        si = SEASON_CYCLE.index(current_season)
        new_season = SEASON_CYCLE[(si + 1) % 4]
        new_month = MONTHS[new_season][0]

    temp = BASE_TEMP[new_season] + random.randint(-5, 5)
    return new_month, new_season, temp


WEATHER_EVENTS = [
    ("Ясно", "Погода благоприятна. Штрафов нет.", {}),
    ("Ливень", "Сильный дождь мешает работе на поверхности.", {"gather_penalty": -2}),
    ("Туман", "Густой туман. Дальность атак сокращена.", {"attack_penalty": -2}),
    ("Пылевая буря", "Буря снижает точность всех действий.", {"concentration_penalty": -2}),
    ("Магнитная буря", "Помехи нарушают связь богов с расами.", {"miracle_blocked": True}),
    ("Аномальная жара", "Жара изматывает войска.", {"food_extra": 10}),
]


def random_weather_event():
    return random.choice(WEATHER_EVENTS)


# ── Faith income ──────────────────────────────────────────────────────────────

def calc_faith_income(faction: dict) -> int:
    pop = faction.get("population", 50)
    base = int(pop * 0.5)
    return max(1, base)
