# 🎮 Эпоха Осколков — Discord Bot GM

Полнофункциональный Discord-бот для проведения текстовой стратегической игры **"Эпоха Осколков"** (Era of Shards) с использованием искусственного интеллекта.

> **ЭпохаОсколков** — это пошаговая стратегическая игра, где каждая фракция управляет своей цивилизацией, тратит ресурсы, развивает технологии и взаимодействует с другими игроками через Discord.

---

## 🌟 Возможности

- 🤖 **AI Game Master** — Claude обрабатывает действия игроков, генерирует нарративы и события
- 📝 **Свободный текст** — игроки пишут действия естественным языком, ИИ их парсит
- 🎲 **D&D-like система** — броски d20 с модификаторами и исходами (крит.успех → крит.провал)
- 💾 **SQLite БД** — полная история игры, ресурсы, достижения, технологии
- 🕹️ **Асинхронные операции** — нет блокировок, быстрая обработка
- 👥 **Множество фракций** — система рас, богов, путей развития и мировоззрений
- 📊 **Статистика** — отслеживание населения, ресурсов, веры и воли

---

## 🚀 Быстрый старт

### Требования
- Python 3.10+
- Discord Bot Token
- Anthropic API Key

### Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <ваш-репозиторий>
   cd DS_bot_AI
   ```

2. **Создайте виртуальное окружение:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # или
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Создайте файл `.env`:**
   ```bash
   cp env.example .env
   ```

5. **Заполните `.env` файл:**
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   GM_ROLE_NAME=GM  # Роль для ГМ-ов (по умолчанию)
   ```

6. **Запустите бота:**
   ```bash
   python Main.py
   ```

---

## 📖 Структура проекта

```
DS_bot_AI/
├── Main.py           # Точка входа, slash-команды бота
├── database.py       # SQLite схема и помощники
├── ai_gm.py         # Интеграция с Anthropic Claude
├── mechanics.py      # Система бросков, исходов, погоды
├── embeds.py        # Discord Embed'ы для красивого вывода
├── requirements.txt  # Зависимости Python
├── env.example      # Пример конфигурации
└── game.db          # SQLite база данных (создается автоматически)
```

### 📋 Модули

**`Main.py`** - Основной бот
- Команда `/register` — регистрация новой фракции
- Команда `/status` — показать статус фракции
- Команда `/action` — отправить действия на ход (свободный текст)
- Команда `/turn_advance` — [ГМ] рассчитать ход и перейти к следующему

**`ai_gm.py`** - ИИ Гейм-Мастер
- `parse_actions()` — парсит свободный текст в структурированные действия
- `generate_narrative()` — создает атмосферное описание результата
- `generate_global_event()` — генерирует глобальные события

**`database.py`** - База данных
- Таблицы: `game`, `factions`, `resources`, `turn_actions`, `achievements`, `technologies`
- Асинхронные операции с SQLite через `aiosqlite`

**`mechanics.py`** - Игровые механики
- D&D система бросков (d20)
- Модификаторы в зависимости от типа действия
- Система исходов (6 уровней)
- Система сезонов и погоды

**`embeds.py`** - Discord встраивания
- Красивое отображение статуса фракции
- Результаты действий
- Ошибки и успехи

---

## 🎮 Как играть

### 1. Регистрация фракции
```
/register faction_name: "Люди Запада" 
          race: "Люди" 
          god_name: "Солнца" 
          path: "CULTIVATION" 
          alignment: "GOOD"
```

### 2. Просмотр статуса
```
/status
```
Показывает характеристики, население, ресурсы, веру и волю.

### 3. Отправка действий (свободный текст)
```
/action text: "Отправляем 30 юнитов собирать еду в лес, 10 юнитов добывают камень в горах"
```
ИИ автоматически:
- Парсит действия
- Распределяет юниты
- Отмечает тайные действия

### 4. ГМ обрабатывает ход
```
/turn_advance
```
Система:
- Бросает d20 для каждого действия
- Применяет модификаторы
- Генерирует атмосферный нарратив
- Обновляет ресурсы
- Генерирует глобальное событие

---

## ⚙️ Конфигурация

### Роль Гейм-Мастера
По умолчанию требуется роль `GM` на сервере для команд `/turn_advance`.

Измените в `Main.py`:
```python
GM_ROLE = os.getenv("GM_ROLE_NAME", "GM")
```

или в `.env`:
```env
GM_ROLE_NAME=Dungeon Master
```

### Модель Claude
По умолчанию используется `claude-sonnet-4-20250514`.

Измените в `ai_gm.py`:
```python
MODEL = "claude-sonnet-4-20250514"
```

### Токены
- **max_tokens для парсинга**: 1000
- **max_tokens для нарратива**: 300
- **max_tokens для событий**: 500

---

## 🗄️ База данных

### Таблица `factions`
```sql
id, discord_user_id, faction_name, race, god_name, path, alignment,
stat_body, stat_mind, stat_energy, stat_concentration,
population, pop_cap, faith, will_points, turn_submitted, created_at
```

### Таблица `resources`
```sql
faction_id, food, fuel, stone, wood, metal, special_name, special_qty
```

### Таблица `turn_actions`
```sql
id, faction_id, turn_number, action_type, description, units_assigned,
dice_roll, modifier, final_roll, outcome, result_text, resource_delta,
is_secret, processed, submitted_at
```

### Таблица `game`
```sql
id, turn_number, month, season, temperature, is_active, deadline_ts
```

---

## 🐛 Решение проблем

### Ошибка: `TypeError: AsyncClient.__init__() got an unexpected keyword argument 'proxies'`
**Решение**: Обновите anthropic SDK
```bash
pip install --upgrade anthropic
```

### Бот не отвечает на команды
1. Проверьте, что `DISCORD_TOKEN` верный
2. Убедитесь, что у бота есть необходимые интенты:
   - `message_content` — для чтения сообщений
   - `guilds` — для работы с серверами
3. Проверьте логи в консоли

### БД заблокирована
SQLite использует WAL (Write-Ahead Logging). При одновременных операциях:
- Убедитесь, что БД не открыта в другом приложении
- Проверьте файлы `game.db-wal` и `game.db-shm`

---

## 📚 Типы действий

| Действие | Код | Описание |
|----------|-----|---------|
| Сбор ресурсов | `GATHER` | Еда, дерево, камень с природы |
| Добыча | `MINE` | Уголь, камень, металл из шахт |
| Строительство | `BUILD` | Здания, стены, туннели |
| Исследование | `RESEARCH` | Технологии и наука |
| Перемещение | `MOVE` | Перемещение юнитов |
| Атака | `ATTACK` | На врагов или животных |
| Чудо | `MIRACLE` | Божественное вмешательство |
| Дипломатия | `DIPLOMACY` | Переговоры, союзы, торговля |
| Шпионаж | `SPY` | Разведка (тайное действие) |
| Торговля | `TRADE` | Обмен с другими фракциями |
| Прочее | `OTHER` | Что-то еще |

---

## 🛠️ Разработка

### Добавление новой команды

1. Создайте функцию в `Main.py`:
```python
@bot.tree.command(name="my_command", description="Описание")
async def my_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    # Ваша логика
    await interaction.followup.send("Результат")
```

2. Синхронизируйте команды:
```python
await self.tree.sync()  # Автоматически при запуске
```

### Добавление новой таблицы

1. Отредактируйте `database.py` в `init_db()`:
```python
CREATE TABLE IF NOT EXISTS my_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
);
```

2. Добавьте помощники в `database.py`

---

## 📝 Лицензия

MIT License — Используйте свободно

---

## 👥 Контакты

Для вопросов, багов и предложений открывайте Issues на GitHub.

---

## 🎯 Планы развития

- [ ] Система достижений
- [ ] Торговля между фракциями
- [ ] Альянсы и войны
- [ ] Система технологических деревьев
- [ ] Карта мира с визуализацией
- [ ] Веб-панель администратора
- [ ] Экспорт логов игры

---

**Создано с ❤️ для стратегических игроков на Discord**
