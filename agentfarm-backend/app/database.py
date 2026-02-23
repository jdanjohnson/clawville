import aiosqlite
import os
import json
from datetime import datetime, timezone

# Use /data/app.db for persistent storage in production, local for dev
DB_PATH = os.environ.get("DATABASE_PATH", "/data/app.db" if os.path.exists("/data") else "app.db")

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_token TEXT NOT NULL UNIQUE,
                score INTEGER DEFAULT 0,
                sand_dollars INTEGER DEFAULT 100,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                owner_id INTEGER REFERENCES agents(id),
                claimed_at TEXT,
                price INTEGER NOT NULL DEFAULT 0,
                UNIQUE(x, y)
            );

            CREATE TABLE IF NOT EXISTS plots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parcel_id INTEGER NOT NULL REFERENCES parcels(id),
                local_x INTEGER NOT NULL,
                local_y INTEGER NOT NULL,
                crop_type TEXT,
                planted_at TEXT,
                watered_at TEXT,
                growth_stage TEXT DEFAULT 'empty',
                ready_at TEXT,
                UNIQUE(parcel_id, local_x, local_y)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER REFERENCES agents(id),
                agent_name TEXT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL REFERENCES agents(id),
                agent_name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS unlocked_crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL REFERENCES agents(id),
                crop_type TEXT NOT NULL,
                unlocked_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(agent_id, crop_type)
            );
        """)
        await db.commit()

        # Initialize world grid if empty
        cursor = await db.execute("SELECT COUNT(*) FROM parcels")
        row = await cursor.fetchone()
        if row[0] == 0:
            center = 9.5
            params = []
            for x in range(20):
                for y in range(20):
                    dist = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                    if dist <= 4:
                        price = 0
                    elif dist <= 7:
                        price = 50
                    elif dist <= 10:
                        price = 150
                    else:
                        price = 400
                    params.append((x, y, price))
            await db.executemany(
                "INSERT INTO parcels (x, y, price) VALUES (?, ?, ?)",
                params
            )
            cursor = await db.execute("SELECT id FROM parcels")
            parcel_ids = await cursor.fetchall()
            plot_params = []
            for parcel in parcel_ids:
                for lx in range(3):
                    for ly in range(3):
                        plot_params.append((parcel[0], lx, ly))
            await db.executemany(
                "INSERT INTO plots (parcel_id, local_x, local_y) VALUES (?, ?, ?)",
                plot_params
            )
            await db.commit()

        # Migrations for existing DBs
        try:
            await db.execute("SELECT sand_dollars FROM agents LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE agents ADD COLUMN sand_dollars INTEGER DEFAULT 100")
            await db.commit()

        try:
            await db.execute("SELECT price FROM parcels LIMIT 1")
        except Exception:
            await db.execute("ALTER TABLE parcels ADD COLUMN price INTEGER DEFAULT 0")
            await db.commit()

    finally:
        await db.close()


# ============================
# CORAL SPECIES (5 unique types)
# ============================
CROPS = {
    "brain_coral": {
        "name": "Brain Coral",
        "grow_time_minutes": 3,
        "decay_minutes": 10,
        "points": 15,
        "sand_dollar_yield": 8,
        "plant_cost": 0,
        "unlock_cost": 0,
        "emoji": "🧠",
        "color": "#e88a5a",
        "tier": 1,
        "description": "Hardy beginner coral. Quick to grow, forgiving decay window."
    },
    "sea_fan": {
        "name": "Sea Fan",
        "grow_time_minutes": 6,
        "decay_minutes": 8,
        "points": 30,
        "sand_dollar_yield": 18,
        "plant_cost": 5,
        "unlock_cost": 0,
        "emoji": "🪭",
        "color": "#ff6eb4",
        "tier": 1,
        "description": "Elegant fan-shaped coral. Beautiful glow when mature."
    },
    "staghorn": {
        "name": "Staghorn Coral",
        "grow_time_minutes": 12,
        "decay_minutes": 8,
        "points": 55,
        "sand_dollar_yield": 35,
        "plant_cost": 15,
        "unlock_cost": 100,
        "tier": 2,
        "emoji": "🦌",
        "color": "#4ecdc4",
        "description": "Branching antler-like growth. Medium risk, medium reward."
    },
    "bubble_coral": {
        "name": "Bubble Coral",
        "grow_time_minutes": 20,
        "decay_minutes": 6,
        "points": 90,
        "sand_dollar_yield": 60,
        "plant_cost": 30,
        "unlock_cost": 300,
        "tier": 3,
        "emoji": "🫧",
        "color": "#a78bfa",
        "description": "Mesmerizing bubble clusters. High value but decays fast."
    },
    "tube_sponge": {
        "name": "Tube Sponge",
        "grow_time_minutes": 35,
        "decay_minutes": 5,
        "points": 160,
        "sand_dollar_yield": 110,
        "plant_cost": 60,
        "unlock_cost": 750,
        "tier": 4,
        "emoji": "🧪",
        "color": "#f472b6",
        "description": "Rare deep-sea sponge. Massive payout but tightest decay window. Snooze = lose."
    },
}

# Land rush bonus: sand dollars awarded for claiming parcels
LAND_RUSH_BONUS = {
    1: 50,
    2: 30,
    3: 20,
}

# Steal mechanic
STEAL_COST = 20
STEAL_SUCCESS_RATE = 60
