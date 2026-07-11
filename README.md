# DS_bot_AI

Discord-бот для пошаговой стратегической игры в стиле «Эпоха Осколков» с использованием искусственного интеллекта и SQLite как хранилища состояния мира.

Проект сейчас соответствует актуальной кодовой базе: точка входа — [Main.py](Main.py), логика GM и Gemini — [ai_gm.py](ai_gm.py), схема данных — [database.py](database.py), а визуализация — [embeds.py](embeds.py).

## Что умеет бот

- регистрация фракций через `/register`
- просмотр состояния фракции через `/status`
- список построек через `/buildings`
- список исследований через `/researches`
- подача действий на ход через `/action`
- обработка хода и переход к следующему через `/turn_advance` для GM
- вывод списка фракций через `/factions_list` для GM
- генерация событий и нарратива через Google Gemini
- хранение состояния в SQLite (`game.db` создаётся автоматически)

## Технологический стек

- Python 3.10+
- discord.py
- google-genai
- aiosqlite
- python-dotenv
- pytest / pytest-asyncio

## Быстрый старт

### 1. Клонируйте репозиторий

```bash
git clone <repo-url>
cd DS_bot_AI
```

### 2. Создайте виртуальное окружение

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Установите зависимости

```bash
pip install -r requirements.txt
```

### 4. Настройте переменные окружения

Скопируйте шаблон:

```bash
copy env.example .env
```

Пример `.env`:

```env
DISCORD_TOKEN=your_discord_bot_token_here
GOOGLE_API_KEY=your_google_gemini_api_key_here
# или
GEMINI_API_KEY=your_google_gemini_api_key_here
GM_ROLE_NAME=GM
```

### 5. Запустите бота

```bash
python Main.py
```

## Команды бота

### Для игроков

- `/register` — регистрация фракции
- `/status` — просмотр текущих характеристик и ресурсов
- `/buildings` — список построек
- `/researches` — список исследований
- `/action` — подача действия на текущий ход

### Для GM

- `/turn_advance` — расчёт хода и переход к следующему
- `/factions_list` — список всех зарегистрированных фракций

## Актуальная конфигурация

### Роль GM

В текущем коде роль GM читается из переменной окружения:

```python
GM_ROLE = os.getenv("GM_ROLE_NAME", "GM")
```

По умолчанию для доступа к GM-командам требуется роль `GM`.

### Gemini

В текущей реализации используется Google Gemini через пакет `google-genai`.

Поддерживаются оба имени переменных:

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`

Модель по умолчанию в [ai_gm.py](ai_gm.py) сейчас настроена как:

```python
MODEL = "gemini-3.1-flash-lite"
```

## Структура проекта

```text
DS_bot_AI/
├── Main.py               # точка входа бота и slash-команды
├── ai_gm.py              # работа с Gemini: парсинг, нарратив, события
├── database.py           # SQLite-схема и helper-функции
├── mechanics.py          # механика бросков, сезонов, ресурсов и исходов
├── embeds.py             # Discord Embed для статусов и вывода
├── requirements.txt      # зависимости Python
├── env.example           # шаблон переменных окружения
├── scripts/              # утилиты и вспомогательные скрипты
├── test_database.py      # проверки схемы и SQLite-логики
├── test_embeds.py        # проверки визуального вывода
└── game.db               # SQLite БД, создаётся автоматически
```

## Как проходит игровой цикл

1. Игрок регистрирует фракцию через `/register`.
2. Игрок смотрит состояние через `/status`.
3. Игрок отправляет действие через `/action`.
4. GM запускает `/turn_advance`.
5. Бот обрабатывает действия, обновляет базу и формирует итоговый вывод.

## База данных

Проект использует SQLite и создаёт таблицы автоматически при запуске через `init_db()` в [database.py](database.py).

Основные сущности:

- `game` — текущий ход, месяц, сезон и температура
- `factions` — игроки и их фракции
- `resources` — запасы ресурсов фракции
- `turn_actions` — действия, отправленные на ход
- `technologies` — исследования
- `buildings` — постройки
- `bonuses` — временные бонусы и модификаторы
- `turn_log` — лог событий хода

## Разработка и проверка

Проверить доступные модели Gemini можно через:

```bash
python scripts/list_gemini_models.py
```

Запустить тесты:

```bash
pytest
```

## Частые вопросы

### Почему бот не реагирует на команды?

Проверьте:

- правильность `DISCORD_TOKEN`
- права и разрешения бота в Discord
- корректность `.env`
- наличие `GOOGLE_API_KEY` или `GEMINI_API_KEY`

### Где лежит состояние игры?

В локальной SQLite базе `game.db`, которая создаётся автоматически при первом запуске.

### Что делать, если ИИ не работает?

Проверьте, что API-ключ для Gemini указан в `.env`, и что пакет `google-genai` установлен из [requirements.txt](requirements.txt).

## Лицензия

Проект распространяется по лицензии MIT.

