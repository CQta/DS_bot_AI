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
            turn_submitted  INTEGER DEFAULT 0,
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
            modifier        INTEGER DEFAULT 0,
            final_roll      INTEGER DEFAULT 0,
            outcome         TEXT    DEFAULT '',
            result_text     TEXT    DEFAULT '',
            resource_delta  TEXT    DEFAULT '{}',  -- JSON
            is_secret       INTEGER DEFAULT 0,
            processed       INTEGER DEFAULT 0,
            submitted_at    REAL    DEFAULT (unixepoch())
        );

        -- Achievements
        CREATE TABLE IF NOT EXISTS achievements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_id  INTEGER REFERENCES factions(id),
            name        TEXT    NOT NULL,
            description TEXT    NOT NULL,
            bonus_json  TEXT    DEFAULT '{}',
            earned_at   REAL    DEFAULT (unixepoch())
        );

        -- Technologies
        CREATE TABLE IF NOT EXISTS technologies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_id  INTEGER REFERENCES factions(id),
            tier        INTEGER DEFAULT 1,
            name        TEXT    NOT NULL,
            is_researched INTEGER DEFAULT 0,
            progress    INTEGER DEFAULT 0
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

        -- Diplomacy
        CREATE TABLE IF NOT EXISTS diplomacy (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            faction_a   INTEGER REFERENCES factions(id),
            faction_b   INTEGER REFERENCES factions(id),
            status      TEXT    DEFAULT 'NEUTRAL',  -- NEUTRAL/ALLIANCE/WAR
            updated_at  REAL    DEFAULT (unixepoch()),
            UNIQUE(faction_a, faction_b)
        );

        -- Insert default game row
        INSERT OR IGNORE INTO game (id) VALUES (1);
        """)
        await db.commit()
    print("[DB] Database initialized.")


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
        await db.execute(query, params)
        await db.commit()


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
        'turn_submitted'
    }
    if field not in allowed:
        return
    await execute(
        f"UPDATE factions SET {field} = ? WHERE id = ?",
        (value, faction_id)
    )


async def reset_turn_flags():
    await execute("UPDATE factions SET turn_submitted = 0")


async def log_event(turn_number: int, faction_id: Optional[int],
                    event_type: str, title: str, description: str):
    await execute(
        "INSERT INTO turn_log (turn_number, faction_id, event_type, title, description) "
        "VALUES (?,?,?,?,?)",
        (turn_number, faction_id, event_type, title, description)
    )
