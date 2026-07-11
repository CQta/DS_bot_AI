"""
embeds.py — Discord Embed builders for consistent formatting
"""

import discord
from mechanics import OUTCOME_LABELS, OUTCOME_COLORS, SEASON_NAMES


def embed_status(faction: dict) -> discord.Embed:
    align_emoji = {"GOOD": "☀️", "NEUTRAL": "⚖️", "EVIL": "🌑"}.get(
        faction.get("alignment", "NEUTRAL"), "⚖️")
    path_emoji = {"CULTIVATION": "🌿", "MAGIC": "✨",
                  "HOLY": "🕊️", "TECHNOLOGY": "⚙️"}.get(
        faction.get("path", ""), "🔮")

    e = discord.Embed(
        title=f"🏛️ {faction['faction_name']}",
        description=(
            f"**Бог:** {faction['god_name']}  {align_emoji}\n"
            f"**Путь:** {path_emoji} {faction['path']}  |  "
            f"**Раса:** {faction['race']}"
        ),
        color=0x2E6DA4
    )

    # Stats
    e.add_field(
        name="📊 Характеристики",
        value=(
            f"💪 Тело: **{faction['stat_body']}**\n"
            f"🧠 Разум: **{faction['stat_mind']}**\n"
            f"🔋 Энергия: **{faction['stat_energy']}**\n"
            f"🎯 Концентрация: **{faction['stat_concentration']}**"
        ),
        inline=True
    )

    # Population & Divine
    e.add_field(
        name="👥 Население и Вера",
        value=(
            f"👥 Население: **{faction['population']}** / {faction['pop_cap']}\n"
            f"🔮 Вера: **{faction['faith']}**\n"
            f"🌀 Воля: **{faction['will_points']}**"
        ),
        inline=True
    )

    # Resources
    special = ""
    if faction.get("special_name"):
        special = f"\n✨ {faction['special_name']}: **{faction.get('special_qty', 0)}**"

    e.add_field(
        name="📦 Ресурсы",
        value=(
            f"🌾 Еда: **{faction.get('food', 0)}**\n"
            f"🪨 Топливо: **{faction.get('fuel', 0)}**\n"
            f"🪵 Дерево: **{faction.get('wood', 0)}**\n"
            f"⛏️ Камень: **{faction.get('stone', 0)}**\n"
            f"🔩 Металл: **{faction.get('metal', 0)}**"
            f"{special}"
        ),
        inline=True
    )

    submitted = "✅ Сдан" if faction.get("free_pop", 0) > 0 else "⏳ Ожидается"
    e.set_footer(text=f"Ход: {submitted}")
    return e


def embed_buildings_list(buildings: list[dict]) -> discord.Embed:
    e = discord.Embed(
        title="🏗️ Постройки",
        description="Вот все ваши текущие постройки и их состояние.",
        color=0x2E6DA4
    )
    if not buildings:
        e.description = "У вас пока нет построек."
        return e

    for building in buildings:
        status = "✅ Завершено" if building.get("is_builded") else "⏳ В процессе"
        cost = building.get("build_cost", 0)
        progress = building.get("build_progress", 0)
        if cost > 0:
            progress_text = f"{progress}/{cost} ({round(progress / cost * 100) if cost else 0}%)"
        else:
            progress_text = str(progress)

        e.add_field(
            name=f"🏠 {building.get('name', 'Постройка')}",
            value=(
                f"Тир: **{building.get('tier', 1)}**\n"
                f"Статус: **{status}**\n"
                f"Прогресс: **{progress_text}**"
            ),
            inline=False
        )

    return e


def embed_researches_list(researches: list[dict]) -> discord.Embed:
    e = discord.Embed(
        title="🔬 Научные исследования",
        description="Вот все ваши текущие исследования и их состояние.",
        color=0x5B2C6F
    )
    if not researches:
        e.description = "У вас пока нет исследований."
        return e

    for research in researches:
        status = "✅ Изучено" if research.get("is_researched") else "⏳ В процессе"
        cost = research.get("research_cost", 0)
        progress = research.get("research_progress", 0)
        if cost > 0:
            progress_text = f"{progress}/{cost} ({round(progress / cost * 100) if cost else 0}%)"
        else:
            progress_text = str(progress)

        e.add_field(
            name=f"🧪 {research.get('name', 'Исследование')}",
            value=(
                f"Тир: **{research.get('tier', 1)}**\n"
                f"Статус: **{status}**\n"
                f"Прогресс: **{progress_text}**"
            ),
            inline=False
        )

    return e


def embed_action_result(faction: dict, action: dict, outcome: str,
                        narrative: str, delta: dict,
                        dice: int, modifier) -> discord.Embed:
    color = OUTCOME_COLORS.get(outcome, 0x888888)
    label = OUTCOME_LABELS.get(outcome, outcome)

    e = discord.Embed(
        title=f"{label} — {faction['faction_name']}",
        description=f"**{action.get('action_type', '?')}:** {action.get('description', '')}",
        color=color
    )
    e.add_field(
        name="🎲 Бросок",
        value=f"`d20({dice}) + {modifier} = {dice + modifier}`",
        inline=True
    )
    
    e.add_field(
        name="👥 Юнитов",
        value=f"`{action.get('units_assigned', 0)}`",
        inline=True
    )

    if delta:
        delta_lines = []
        icons = {"food": "🌾", "fuel": "🪨", "wood": "🪵",
                 "stone": "⛏️", "metal": "🔩", "faith": "🔮", "special_qty": "✨"}
        for k, v in delta.items():
            icon = icons.get(k, "📦")
            sign_str = "+" if v > 0 else ""
            delta_lines.append(f"{icon} {k}: `{sign_str}{v}`")
        e.add_field(name="📊 Изменения", value="\n".join(delta_lines), inline=False)

    if narrative:
        e.add_field(name="📜 Хроника", value=narrative, inline=False)

    return e


def embed_turn_start(turn: int, month: str, season: str,
                     temperature: int, event: dict) -> discord.Embed:
    season_emoji = {"AUTUMN": "🍂", "WINTER": "❄️",
                    "SPRING": "🌸", "SUMMER": "☀️"}.get(season, "🌍")
    season_name = SEASON_NAMES.get(season, season)

    e = discord.Embed(
        title=f"{season_emoji} Ход №{turn} — {month}",
        description=f"**Сезон:** {season_name}  |  **Температура:** {temperature}°C",
        color=0x3498DB
    )

    if event:
        e.add_field(
            name=f"⚡ {event.get('title', 'Событие')}",
            value=(
                f"{event.get('description', '')}\n\n"
                f"*Эффект: {event.get('mechanical_effect', '')}*"
            ),
            inline=False
        )

    e.add_field(
        name="📋 Инструкция",
        value=(
            "Используйте `/action` для подачи действий\n"
            "Используйте `/god_action` для Чудес бога\n"
            "Используйте `/status` для просмотра состояния"
        ),
        inline=False
    )
    e.set_footer(text="Подайте все действия до конца хода")
    return e


def embed_turn_summary(turn: int, factions: list[dict],
                       warnings: list[str]) -> discord.Embed:
    e = discord.Embed(
        title=f"📜 Итоги хода №{turn}",
        color=0xF1C40F
    )

    for f in factions:
        submitted = "✅" if f.get("free_pop", 0) != f.get("population", 0) else "❌ не сдал ход"
        e.add_field(
            name=f"🏛️ {f['faction_name']}",
            value=(
                f"👥 {f['population']}/{f['pop_cap']}  "
                f"🌾 {f.get('food', 0)}  "
                f"🪨 {f.get('fuel', 0)}  "
                f"🔮 {f.get('faith', 0)}  {submitted}"
            ),
            inline=False
        )

    if warnings:
        e.add_field(
            name="",
            value="\n".join(warnings),
            inline=False
        )

    return e


def embed_error(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Ошибка",
        description=message,
        color=0xFF0000
    )


def embed_success(message: str) -> discord.Embed:
    return discord.Embed(
        title="✅ Готово",
        description=message,
        color=0x2ECC71
    )


def embed_roll(user: str, dice: int, outcome: str) -> discord.Embed:
    label = OUTCOME_LABELS.get(outcome, outcome)
    color = OUTCOME_COLORS.get(outcome, 0x888888)
    e = discord.Embed(
        title=f"🎲 Бросок — {user}",
        description=f"d20 = {dice}\n{label}",
        color=color
    )
    return e


def embed_factions_list(factions: list[dict]) -> discord.Embed:
    e = discord.Embed(title="🌍 Все фракции", color=0x2E6DA4)
    if not factions:
        e.description = "Нет зарегистрированных фракций."
        return e
    for f in factions:
        align_emoji = {"GOOD": "☀️", "NEUTRAL": "⚖️", "EVIL": "🌑"}.get(
            f.get("alignment", ""), "⚖️")
        e.add_field(
            name=f"🏛️ {f['faction_name']} {align_emoji}",
            value=(
                f"Игрок: {f['discord_name']}\n"
                f"Раса: {f['race']} | Бог: {f['god_name']}\n"
                f"👥 {f['population']} | 🔮 {f.get('faith', 0)}"
            ),
            inline=True
        )
    return e
