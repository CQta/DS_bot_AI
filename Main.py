import os
import json
import asyncio
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Импорт наших собственных модулей
import database as db
import mechanics
import ai_gm
import embeds

# Загрузка конфигурации
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GM_ROLE = os.getenv("GM_ROLE_NAME", "GM")

# Настройка интентов Discord
intents = discord.Intents.default()
intents.message_content = True

class PangeaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Инициализируем базу данных при запуске
        await db.init_db()
        # Синхронизируем команды (для продакшна лучше делать локально или по id сервера)
        await self.tree.sync()
        print("[Bot] Слэш-команды синхронизированы.")

bot = PangeaBot()

@bot.event
async def on_ready():
    print(f"[Bot] Вошел в сеть как {bot.user.name} (ID: {bot.user.id})")


# ─── ВСПОМОГАТЕЛЬНЫЕ ПРОВЕРКИ ────────────────────────────────────────────────

def is_gm():
    """Проверка, есть ли у пользователя роль Гейм-Мастера."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        role = discord.utils.get(interaction.user.roles, name=GM_ROLE)
        if not role:
            await interaction.response.send_message(
                f"❌ Эта команда доступна только пользователям с ролью `{GM_ROLE}`.", 
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)


# ─── КОМАНДЫ ИГРОКОВ ─────────────────────────────────────────────────────────

@bot.tree.command(name="register", description="Зарегистрировать свою фракцию в игре")
@app_commands.describe(
    faction_name="Название вашей фракции",
    race="Раса (например: Люди, Голиморы, Магматиты)",
    god_name="Имя вашего бога",
    path="Путь развития фракции",
    alignment="Мировоззрение фракции"
)
@app_commands.choices(
    path=[
        app_commands.Choice(name="🌿 Культивация (CULTIVATION)", value="CULTIVATION"),
        app_commands.Choice(name="✨ Магия (MAGIC)", value="MAGIC"),
        app_commands.Choice(name="🕊️ Святость (HOLY)", value="HOLY"),
        app_commands.Choice(name="⚙️ Технологии (TECHNOLOGY)", value="TECHNOLOGY"),
    ],
    alignment=[
        app_commands.Choice(name="☀️ Добро (GOOD)", value="GOOD"),
        app_commands.Choice(name="⚖️ Нейтралитет (NEUTRAL)", value="NEUTRAL"),
        app_commands.Choice(name="🌑 Зло (EVIL)", value="EVIL"),
    ]
)
async def register(
    interaction: discord.Interaction, 
    faction_name: str, 
    race: str, 
    god_name: str, 
    path: str, 
    alignment: str
):
    await interaction.response.defer(ephemeral=True)
    
    # Проверяем, нет ли уже фракции у игрока
    existing = await db.get_faction(str(interaction.user.id))
    if existing:
        await interaction.followup.send("❌ Вы уже зарегистрировали фракцию!")
        return

    # Распределение базовых характеристик (по умолчанию всем по 5, D&D-like)
    # Игрок может изменить их позже через механики или ГМ-а
    try:
        await db.create_faction(
            discord_user_id=str(interaction.user.id),
            discord_name=interaction.user.name,
            faction_name=faction_name,
            race=race,
            god_name=god_name,
            path=path,
            alignment=alignment,
            body=5, mind=5, energy=5, conc=5
        )
        await interaction.followup.send(embed=embeds.embed_success(f"Фракция **{faction_name}** успешно создана!"))
    except Exception as e:
        await interaction.followup.send(embed=embeds.embed_error(f"Ошибка при создании: {e}"))


@bot.tree.command(name="status", description="Показать статус вашей фракции")
async def status(interaction: discord.Interaction):
    faction = await db.get_faction(str(interaction.user.id))
    if not faction:
        await interaction.response.send_message("❌ У вас еще нет зарегистрированной фракции. Используйте `/register`.", ephemeral=True)
        return
    
    embed = embeds.embed_status(faction)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="action", description="Отправить действия на текущий ход (свободный текст)")
@app_commands.describe(text="Опишите, что делают ваши подданные в этот ход")
async def action(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)
    
    faction = await db.get_faction(str(interaction.user.id))
    if not faction:
        await interaction.followup.send("❌ Сначала зарегистрируйте фракцию через `/register`.")
        return
        
    if faction.get("turn_submitted"):
        await interaction.followup.send("❌ Вы уже завершили ход! Дождитесь итогов.")
        return

    game = await db.get_game()
    current_turn = game["turn_number"]

    # ИИ разбирает свободный текст на структуру JSON
    parsed_actions = await ai_gm.parse_actions(text, faction)
    
    if not parsed_actions:
        await interaction.followup.send("❌ ИИ не смог распознать ваши действия. Попробуйте написать более конкретно.")
        return

    # Записываем действия в базу данных
    for act in parsed_actions:
        await db.execute(
            """INSERT INTO turn_actions 
               (faction_id, turn_number, action_type, description, units_assigned, is_secret)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (faction["id"], current_turn, act["action_type"], act["description"], act["units"], 1 if act.get("is_secret") else 0)
        )

    # Ставим отметку, что ход сдан
    await db.update_faction_field(faction["id"], "turn_submitted", 1)
    
    # Формируем красивый отчет для игрока о том, что понял ИИ
    report_lines = []
    for a in parsed_actions:
        report_lines.append(f"• **[{a['action_type']}]** (Юниты: {a['units']}): {a['description']}")
    
    response_text = "✅ **Ваши действия приняты и поставлены в очередь:**\n" + "\n".join(report_lines)
    await interaction.followup.send(response_text)


# ─── АДМИНИСТРАТИВНЫЕ КОМАНДЫ ГЕЙМ-МАСТЕРА (GM) ──────────────────────────────

@bot.tree.command(name="turn_advance", description="[GM] Рассчитать текущий ход и перейти к следующему")
@is_gm()
async def turn_advance(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    game = await db.get_game()
    current_turn = game["turn_number"]
    current_season = game["season"]
    current_month = game["month"]
    
    factions = await db.get_all_factions()
    all_warnings = []

    # 1. Сбор необработанных действий текущего хода
    actions = await db.fetch_all(
        "SELECT * FROM turn_actions WHERE turn_number = ? AND processed = 0", 
        (current_turn,)
    )

    # 2. Обработка каждого действия (Броски + Модификаторы + Расчет ресурсов + Нарратив ИИ)
    for act in actions:
        faction_id = act["faction_id"]
        faction = await db.get_faction_by_id(faction_id)
        if not faction:
            continue
            
        # Считаем d20 + модификатор от характеристик
        dice = mechanics.roll_d20()
        modifier = mechanics.calc_modifier(faction, act["action_type"])
        final_roll = dice + modifier
        
        # Градация успеха
        outcome = mechanics.get_outcome(final_roll)
        
        # Изменение ресурсов по математике игры
        delta = mechanics.calc_resource_delta(act["action_type"], outcome, act["units_assigned"], faction)
        
        # Применяем изменения в БД
        for resource, amount in delta.items():
            await db.update_resource(faction_id, resource, amount)
            
        # Генерация художественного описания от ИИ Клод
        narrative = await ai_gm.generate_narrative(
            faction, act, outcome, delta, current_season, game["temperature"]
        )
        
        # Сохраняем результаты обратно в действие
        await db.execute(
            """UPDATE turn_actions SET 
               dice_roll = ?, modifier = ?, final_roll = ?, outcome = ?, 
               result_text = ?, resource_delta = ?, processed = 1
               WHERE id = ?""",
            (dice, modifier, final_roll, outcome, narrative, json.dumps(delta), act["id"])
        )
        
        # Логируем в историю мира публичные действия
        if not act["is_secret"]:
            await db.log_event(
                current_turn, faction_id, "ACTION_RESULT", 
                f"{faction['faction_name']}: {act['action_type']}", narrative
            )
            
            # Отправляем красивый эмбед в канал, где была вызвана команда
            embed_res = embeds.embed_action_result(faction, act, outcome, narrative, delta, dice, modifier)
            await interaction.channel.send(embed=embed_res)

    # 3. Фаза потребления ресурсов в конце хода (Еда, Топливо) и проверка голода
    for f in factions:
        consumption = mechanics.calc_consumption(f, current_season)
        
        # Запись предупреждений, если ресурсов мало
        warnings = mechanics.check_starvation(f, consumption)
        all_warnings.extend(warnings)
        
        # Списываем потребление
        for res, amount in consumption.items():
            await db.update_resource(f["id"], res, -amount)
            
        # Начисление пассивной Веры от населения
        faith_income = mechanics.calc_faith_income(f)
        await db.update_faction_field(f["id"], "faith", f.get("faith", 0) + faith_income)

    # 4. Смена погоды, месяца и сезона
    new_month, new_season, new_temp = mechanics.next_month(current_month, current_season, current_turn)
    
    # ИИ генерирует случайное глобальное событие на новый ход
    next_factions_state = await db.get_all_factions() # Обновленное состояние
    global_event = await ai_gm.generate_global_event(next_factions_state, new_season, new_temp)

    # Обновляем состояние игры в БД
    next_turn = current_turn + 1
    await db.execute(
        """UPDATE game SET turn_number = ?, month = ?, season = ?, temperature = ? WHERE id = 1""",
        (next_turn, new_month, new_season, new_temp)
    )
    
    # Сбрасываем флаги готовности ходов у игроков
    await db.reset_turn_flags()

    # 5. Публикация Итогов хода и Анонс Нового Хода
    summary_embed = embeds.embed_turn_summary(current_turn, next_factions_state, all_warnings)
    await interaction.channel.send(embed=summary_embed)
    
    start_embed = embeds.embed_turn_start(next_turn, new_month, new_season, new_temp, global_event)
    await interaction.channel.send(content="🔔 **НАЧАЛСЯ НОВЫЙ ХОД!**", embed=start_embed)
    
    await interaction.followup.send("✅ Ход успешно закрыт и просчитан!")


@bot.tree.command(name="factions_list", description="[GM] Вывести список всех фракций мира")
@is_gm()
async def factions_list(interaction: discord.Interaction):
    factions = await db.get_all_factions()
    embed = embeds.embed_factions_list(factions)
    await interaction.response.send_message(embed=embed)


# Запуск бота
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Ошибка: В файле .env не указан DISCORD_TOKEN")
    else:
        bot.run(TOKEN)