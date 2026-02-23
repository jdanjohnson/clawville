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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                owner_id INTEGER REFERENCES agents(id),
                claimed_at TEXT,
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
        """)
        await db.commit()

        # Seed crop types as a constant (no table needed for MVP)
        # Initialize world grid if empty
        cursor = await db.execute("SELECT COUNT(*) FROM parcels")
        row = await cursor.fetchone()
        if row[0] == 0:
            # Create a 20x20 world grid (400 parcels)
            params = [(x, y) for x in range(20) for y in range(20)]
            await db.executemany(
                "INSERT INTO parcels (x, y) VALUES (?, ?)",
                params
            )
            # Create 3x3 plots for each parcel
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
    finally:
        await db.close()

# Crop definitions
CROPS = {
    "sea_kelp": {
        "name": "Sea Kelp",
        "grow_time_minutes": 2,
        "points": 10,
        "emoji": "🌿",
        "color": "#2d5a27"
    },
    "coral_bloom": {
        "name": "Coral Bloom",
        "grow_time_minutes": 5,
        "points": 25,
        "emoji": "🪸",
        "color": "#ff6b6b"
    },
    "pearl_oyster": {
        "name": "Pearl Oyster",
        "grow_time_minutes": 10,
        "points": 50,
        "emoji": "🦪",
        "color": "#e8d5b7"
    },
    "bioluminescent_algae": {
        "name": "Bioluminescent Algae",
        "grow_time_minutes": 3,
        "points": 20,
        "emoji": "✨",
        "color": "#00ff88"
    },
    "anemone": {
        "name": "Anemone",
        "grow_time_minutes": 7,
        "points": 35,
        "emoji": "🌺",
        "color": "#ff69b4"
    },
    "deep_sea_mushroom": {
        "name": "Deep Sea Mushroom",
        "grow_time_minutes": 15,
        "points": 75,
        "emoji": "🍄",
        "color": "#9b59b6"
    }
}
