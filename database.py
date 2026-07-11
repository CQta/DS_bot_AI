"""
database.py — SQLite schema and helper functions
"""

import aiosqlite
import json
from typing import Optional

DB_PATH = "game.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;

        -- Game session (one active game at a time)
        CREATE TABLE IF NOT EXISTS game (
            id          INTEGER PRIMARY KEY DEFAULT 1,
            turn_number INTEGER DEFAULT 1,
            month       TEXT    DEFAULT 'Сентябрь',
            season      TEXT    DEFAULT 'AUTUMN',
            temperature INTEGER DEFAULT 10,
            is_active   INTEGER DEFAULT 0,
            deadline_ts REAL    DEFAULT 0
        );

        -- Player factions
        CREATE TABLE IF NOT EXISTS factions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_user_id TEXT    UNIQUE NOT NULL,
            discord_name    TEXT    NOT NULL,
            faction_name    TEXT    NOT NULL,
            race            TEXT    NOT NULL,
            god_name        TEXT    NOT NULL,
            path            TEXT    NOT NULL,   -- CULTIVATION/MAGIC/HOLY/TECHNOLOGY
            alignment       TEXT    NOT NULL,   -- GOOD/NEUTRAL/EVIL
            -- Stats
            stat_body       INTEGER DEFAULT 5,
            stat_mind       INTEGER DEFAULT 5,
            stat_energy     INTEGER DEFAULT 5,
            stat_concentration INTEGER DEFAULT 5,
            -- Population
            population      INTEGER DEFAULT 50,
            pop_cap         INTEGER DEFAULT 60,
            -- Divine resources
            faith           INTEGER DEFAULT 10,
            will_points     INTEGER DEFAULT 3,
            -- Turn state
            free_pop  INTEGER DEFAULT 50,
            created_at      REAL    DEFAULT (unixepoch())
        );

        -- Resources (separate table for clarity)
        CREATE TABLE IF NOT EXISTS resources (
            faction_id  INTEGER PRIMARY KEY REFERENCES factions(id),
            food        INTEGER DEFAULT 150,
            fuel        INTEGER DEFAULT 100,
            stone       INTEGER DEFAULT 50,
            wood        INTEGER DEFAULT 80,
            metal       INTEGER DEFAULT 0,
            special_name TEXT   DEFAULT '',
            special_qty  INTEGER DEFAULT 0
        );

        -- Actions submitted this turn
        CREATE TABLE IF NOT EXISTS turn_actions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_id      INTEGER REFERENCES factions(id),
            turn_number     INTEGER NOT NULL,
            action_type     TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            units_assigned  INTEGER DEFAULT 0,
            dice_roll       INTEGER DEFAULT 0,
            final_roll      INTEGER DEFAULT 0,
            outcome         TEXT    DEFAULT '',
            result_text     TEXT    DEFAULT '',
            resource_delta  TEXT    DEFAULT '{}',  -- JSON
            is_secret       INTEGER DEFAULT 0,
            processed       INTEGER DEFAULT 0,
            submitted_at    REAL    DEFAULT (unixepoch())
        );

        -- Bonuses
        CREATE TABLE IF NOT EXISTS bonuses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_id  INTEGER REFERENCES factions(id),
            bonus_type  TEXT    DEFAULT '{}',
            bonus_value REAL    DEFAULT (unixepoch()),
            is_active   INTEGER DEFAULT 0,
            duration    INTEGER DEFAULT -1
        );

        -- Technologies
        CREATE TABLE IF NOT EXISTS technologies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_id  INTEGER REFERENCES factions(id),
            tier        INTEGER DEFAULT 1,
            name        TEXT    NOT NULL,
            is_researched INTEGER DEFAULT 0,
            research_cost    INTEGER DEFAULT 0,
            research_progress    INTEGER DEFAULT 0,
            bonus_id INTEGER REFERENCES bonuses(id)
        );
        
        -- Buildings
        CREATE TABLE IF NOT EXISTS buildings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_id  INTEGER REFERENCES factions(id),
            tier        INTEGER DEFAULT 1,
            name        TEXT    NOT NULL,
            is_builded INTEGER DEFAULT 0,
            build_cost    INTEGER DEFAULT 0,
            build_progress    INTEGER DEFAULT 0,
            bonus_id INTEGER REFERENCES bonuses(id)
        );
        
        -- Turn history log
        CREATE TABLE IF NOT EXISTS turn_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            turn_number INTEGER NOT NULL,
            faction_id  INTEGER,
            event_type  TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            description TEXT    NOT NULL,
            created_at  REAL    DEFAULT (unixepoch())
        );

        -- Insert default game row
        INSERT OR IGNORE INTO game (id) VALUES (1);
        """)
        await db.commit()
    print("[DB] Database initialized.")

# ── Technologies helper ──────────────────────────────────────────────────────────

def _normalize_technology_row(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    normalized = dict(row)
    if "research_progress" in normalized and "progress" not in normalized:
        normalized["progress"] = normalized["research_progress"]
    return normalized


async def get_technologies(faction_id: int) -> list[dict]:
    rows = await fetch_all(
        "SELECT * FROM technologies WHERE faction_id = ?",
        (faction_id,)
    )
    return [_normalize_technology_row(row) for row in rows]

async def get_technology_by_id(faction_id: int, tech_id: int) -> Optional[dict]:
    return _normalize_technology_row(await fetch_one(
        "SELECT * FROM technologies WHERE faction_id = ? AND id = ?",
        (faction_id, tech_id)
    ))
    
async def get_not_researched_technologies(faction_id: int) -> dict[str, int]:
    result = await fetch_all(
        "SELECT id, name FROM technologies WHERE faction_id = ? AND is_researched = 0",
        (faction_id,)
    )
    return {item["name"]: item["id"] for item in result}

async def mark_technology_as_researched(faction_id: int, tech_id: int):
    await execute(
        "UPDATE technologies SET is_researched = 1 WHERE faction_id = ? AND id = ?",
        (faction_id, tech_id)
    )
    
async def update_technology_progress(faction_id: int, tech_id: int, progress_delta: int):
    await execute(
        "UPDATE technologies SET research_progress = research_progress + ? "
        "WHERE faction_id = ? AND id = ?",
        (progress_delta, faction_id, tech_id)
    )
    
async def create_technology(faction_id: int, name: str, tier: int, research_cost: int, research_progress: int = 0, is_researched: int = 0, bonus_id: Optional[int] = None):
    await execute(
        "INSERT INTO technologies (faction_id, name, tier, research_cost, research_progress, is_researched, bonus_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (faction_id, name, tier, research_cost, research_progress, is_researched, bonus_id)
    )

# ── Building helper ──────────────────────────────────────────────────────────

def _normalize_building_row(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    normalized = dict(row)
    if "build_progress" in normalized and "progress" not in normalized:
        normalized["progress"] = normalized["build_progress"]
    return normalized


async def get_buildings(faction_id: int) -> list[dict]:
    rows = await fetch_all(
        "SELECT * FROM buildings WHERE faction_id = ?",
        (faction_id,)
    )
    return [_normalize_building_row(row) for row in rows]

async def get_not_built_buildings(faction_id: int) -> dict[str, int]:
    result = await fetch_all(
        "SELECT id, name FROM buildings WHERE faction_id = ? AND is_builded = 0",
        (faction_id,)
    )
    return {item["name"]: item["id"] for item in result}

async def update_building_progress(faction_id: int, building_id: int, progress_delta: int):
    await execute(
        "UPDATE buildings SET build_progress = build_progress + ? "
        "WHERE faction_id = ? AND id = ?",
        (progress_delta, faction_id, building_id)
    )

async def create_building(faction_id: int, name: str, tier: int, build_cost: int, build_progress: int = 0, is_builded: int = 0, bonus_id: Optional[int] = None):
    await execute(
        "INSERT INTO buildings (faction_id, name, tier, build_cost, build_progress, is_builded, bonus_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (faction_id, name, tier, build_cost, build_progress, is_builded, bonus_id)
    )
async def get_building_by_id(faction_id: int, building_id: int) -> Optional[dict]:
    return _normalize_building_row(await fetch_one(
        "SELECT * FROM buildings WHERE faction_id = ? AND id = ?",
        (faction_id, building_id)
    ))
async def mark_building_as_built(faction_id: int, building_id: int):
    await execute(
        "UPDATE buildings SET is_builded = 1 WHERE faction_id = ? AND id = ?",
        (faction_id, building_id)
    )
    
# ── Bonuses helper ──────────────────────────────────────────────────────────

async def create_bonus(faction_id: int, bonus_type: str, bonus_value: float, is_active: int = 0, duration: Optional[int] = -1) -> int:
    cursor = await execute(
        "INSERT INTO bonuses (faction_id, bonus_type, bonus_value, is_active, duration) "
        "VALUES (?, ?, ?, ?, ?)",
        (faction_id, bonus_type, bonus_value, is_active, duration)
    )
    return cursor.lastrowid  # Return the ID of the newly created bonus

async def create_bonus_for_all_fractions(targets: dict[str, float], is_active: int = 1, duration: Optional[int] = 0):  #Позже заменить на вариант лучше, пока сойдет
    factions = await get_all_factions()
    for faction in factions:
        for bonus_type, bonus_value in targets.items():
            await create_bonus(faction['id'], bonus_type, bonus_value, is_active, duration)

async def get_all_modificators_active_bonuses(faction_id: int) -> list[dict]:
    return await fetch_all(
        "SELECT bonus_type, bonus_value FROM bonuses WHERE faction_id = ? AND is_active = 1",
        (faction_id,)
    )
    
async def get_all_unactive_bonuses(faction_id: int) -> list[dict]:
    return await fetch_all(
        "SELECT * FROM bonuses WHERE faction_id = ? AND is_active = 0",
        (faction_id,)
    )

async def activate_bonus(faction_id: int, bonus_id: int):
    # Получаем информацию о бонусе
    bonus = await fetch_one(
        """
        SELECT bonus_type, bonus_value
        FROM bonuses
        WHERE faction_id = ? AND id = ?
        """,
        (faction_id, bonus_id)
    )

    if bonus is None:
        return False

    bonus_type = bonus["bonus_type"]
    bonus_value = bonus["bonus_value"]

    # Активируем бонус
    await execute(
        """
        UPDATE bonuses
        SET is_active = 1
        WHERE faction_id = ? AND id = ?
        """,
        (faction_id, bonus_id)
    )

    # Если это бонус на жилища
    if bonus_type == "home":
        await execute(
            """
            UPDATE factions
            SET pop_cap = pop_cap + ?
            WHERE id = ?
            """,
            (bonus_value, faction_id)
        )

    
# ── Generic helpers ──────────────────────────────────────────────────────────

async def fetch_one(query: str, params=()) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def fetch_all(query: str, params=()) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def execute(query: str, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor


# ── Faction helpers ──────────────────────────────────────────────────────────

async def get_faction(discord_user_id: str) -> Optional[dict]:
    return await fetch_one(
        "SELECT f.*, r.food, r.fuel, r.stone, r.wood, r.metal, "
        "r.special_name, r.special_qty "
        "FROM factions f LEFT JOIN resources r ON r.faction_id = f.id "
        "WHERE f.discord_user_id = ?",
        (discord_user_id,)
    )


async def get_faction_by_id(faction_id: int) -> Optional[dict]:
    return await fetch_one(
        "SELECT f.*, r.food, r.fuel, r.stone, r.wood, r.metal "
        "FROM factions f LEFT JOIN resources r ON r.faction_id = f.id "
        "WHERE f.id = ?",
        (faction_id,)
    )


async def get_all_factions() -> list[dict]:
    return await fetch_all(
        "SELECT f.*, r.food, r.fuel, r.stone, r.wood, r.metal "
        "FROM factions f LEFT JOIN resources r ON r.faction_id = f.id"
    )


async def create_faction(discord_user_id: str, discord_name: str,
                          faction_name: str, race: str, god_name: str,
                          path: str, alignment: str,
                          body: int, mind: int, energy: int, conc: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO factions
               (discord_user_id, discord_name, faction_name, race, god_name,
                path, alignment, stat_body, stat_mind, stat_energy, stat_concentration)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (discord_user_id, discord_name, faction_name, race, god_name,
             path, alignment, body, mind, energy, conc)
        )
        fid = cur.lastrowid
        await db.execute(
            "INSERT INTO resources (faction_id) VALUES (?)", (fid,)
        )
        await db.commit()
        return fid


async def get_game() -> dict:
    return await fetch_one("SELECT * FROM game WHERE id = 1")


async def update_resource(faction_id: int, resource: str, delta: int):
    """Add delta to a resource (can be negative). Clamps to 0 minimum."""
    allowed = {'food', 'fuel', 'stone', 'wood', 'metal', 'special_qty'}
    if resource not in allowed:
        return
    await execute(
        f"UPDATE resources SET {resource} = MAX(0, {resource} + ?) "
        f"WHERE faction_id = ?",
        (delta, faction_id)
    )


async def update_faction_field(faction_id: int, field: str, value):
    allowed = {
        'faith', 'will_points', 'population', 'pop_cap',
        'stat_body', 'stat_mind', 'stat_energy', 'stat_concentration',
        'free_pop'
    }
    if field not in allowed:
        return
    await execute(
        f"UPDATE factions SET {field} = ? WHERE id = ?",
        (value, faction_id)
    )


async def reset_turn_flags():
    await execute("UPDATE factions SET free_pop = population")


async def log_event(turn_number: int, faction_id: Optional[int],
                    event_type: str, title: str, description: str):
    await execute(
        "INSERT INTO turn_log (turn_number, faction_id, event_type, title, description) "
        "VALUES (?,?,?,?,?)",
        (turn_number, faction_id, event_type, title, description)
    )
