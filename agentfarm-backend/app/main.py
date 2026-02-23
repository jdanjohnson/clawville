from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import secrets
import aiosqlite

from app.database import get_db, init_db, CROPS, DB_PATH
from app.models import (
    AgentRegister, AgentResponse, ParcelClaim, PlantCrop, WaterParcel,
    HarvestCrop, PlotResponse, ParcelResponse, WorldResponse,
    ActivityResponse, LeaderboardEntry, CropInfo, ChatMessage, ChatMessageResponse
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="ClawVille: Underwater Edition", lifespan=lifespan)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# --- Auth helpers ---

async def get_current_agent(x_api_token: str = Header(..., alias="X-API-Token")):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, api_token, score, created_at FROM agents WHERE api_token = ?",
            (x_api_token,)
        )
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=401, detail="Invalid API token")
        return dict(agent)
    finally:
        await db.close()


async def log_activity(db: aiosqlite.Connection, agent_id: int, agent_name: str, action: str, details: str = None):
    await db.execute(
        "INSERT INTO activities (agent_id, agent_name, action, details) VALUES (?, ?, ?, ?)",
        (agent_id, agent_name, action, details)
    )


def compute_growth_stage(plot_row: dict) -> tuple[str, float]:
    """Compute current growth stage and progress percentage based on wall clock time."""
    if not plot_row["crop_type"] or not plot_row["planted_at"]:
        return "empty", 0.0

    crop = CROPS.get(plot_row["crop_type"])
    if not crop:
        return "empty", 0.0

    planted_at = datetime.fromisoformat(plot_row["planted_at"]).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    grow_minutes = crop["grow_time_minutes"]

    # Watering speeds growth by 25%
    if plot_row["watered_at"]:
        grow_minutes = int(grow_minutes * 0.75)

    elapsed = (now - planted_at).total_seconds() / 60.0
    progress = min(elapsed / grow_minutes, 1.0) if grow_minutes > 0 else 1.0

    if progress >= 1.0:
        return "mature", 1.0
    elif progress >= 0.66:
        return "growing", progress
    elif progress >= 0.33:
        return "sprouting", progress
    else:
        return "seedling", progress


def build_plot_response(plot_row: dict) -> PlotResponse:
    stage, progress = compute_growth_stage(plot_row)
    crop = CROPS.get(plot_row["crop_type"]) if plot_row["crop_type"] else None
    return PlotResponse(
        local_x=plot_row["local_x"],
        local_y=plot_row["local_y"],
        crop_type=plot_row["crop_type"],
        crop_name=crop["name"] if crop else None,
        growth_stage=stage,
        planted_at=plot_row["planted_at"],
        watered_at=plot_row["watered_at"],
        ready_at=plot_row["ready_at"],
        progress_pct=round(progress * 100, 1)
    )


# --- Endpoints ---

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/agents/register", response_model=AgentResponse)
async def register_agent(data: AgentRegister):
    token = secrets.token_hex(24)
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM agents WHERE name = ?", (data.name,))
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Agent name already taken")

        await db.execute(
            "INSERT INTO agents (name, api_token) VALUES (?, ?)",
            (data.name, token)
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, name, api_token, score, created_at FROM agents WHERE api_token = ?",
            (token,)
        )
        agent = await cursor.fetchone()
        await log_activity(db, agent["id"], agent["name"], "registered", f"{data.name} swam into ClawVille!")
        await db.commit()
        return AgentResponse(**dict(agent))
    finally:
        await db.close()


@app.get("/api/crops", response_model=list[CropInfo])
async def list_crops():
    return [CropInfo(key=k, **v) for k, v in CROPS.items()]


@app.get("/api/world", response_model=WorldResponse)
async def get_world():
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT p.id, p.x, p.y, p.owner_id, p.claimed_at, a.name as owner_name
            FROM parcels p
            LEFT JOIN agents a ON p.owner_id = a.id
            ORDER BY p.y, p.x
        """)
        parcels_raw = await cursor.fetchall()

        cursor = await db.execute("""
            SELECT pl.parcel_id, pl.local_x, pl.local_y, pl.crop_type,
                   pl.planted_at, pl.watered_at, pl.growth_stage, pl.ready_at
            FROM plots pl
        """)
        plots_raw = await cursor.fetchall()

        plots_by_parcel: dict[int, list[dict]] = {}
        for plot in plots_raw:
            pid = plot["parcel_id"]
            if pid not in plots_by_parcel:
                plots_by_parcel[pid] = []
            plots_by_parcel[pid].append(dict(plot))

        parcels = []
        claimed_count = 0
        for p in parcels_raw:
            p_dict = dict(p)
            if p_dict["owner_id"]:
                claimed_count += 1
            plot_responses = [
                build_plot_response(pl) for pl in plots_by_parcel.get(p_dict["id"], [])
            ]
            parcels.append(ParcelResponse(
                id=p_dict["id"],
                x=p_dict["x"],
                y=p_dict["y"],
                owner_id=p_dict["owner_id"],
                owner_name=p_dict["owner_name"],
                claimed_at=p_dict["claimed_at"],
                plots=plot_responses
            ))

        cursor = await db.execute("SELECT COUNT(*) FROM agents")
        agent_count = (await cursor.fetchone())[0]

        return WorldResponse(
            world_size=20,
            total_parcels=len(parcels),
            claimed_parcels=claimed_count,
            total_agents=agent_count,
            parcels=parcels
        )
    finally:
        await db.close()


@app.get("/api/world/activity", response_model=list[ActivityResponse])
async def get_activity(limit: int = 50):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, agent_name, action, details, created_at FROM activities ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [ActivityResponse(**dict(r)) for r in rows]
    finally:
        await db.close()


@app.post("/api/parcels/claim", response_model=ParcelResponse)
async def claim_parcel(data: ParcelClaim, agent: dict = Depends(get_current_agent)):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, x, y, owner_id, claimed_at FROM parcels WHERE x = ? AND y = ?",
            (data.x, data.y)
        )
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if parcel["owner_id"]:
            raise HTTPException(status_code=409, detail="Parcel already claimed")

        cursor = await db.execute(
            "SELECT COUNT(*) FROM parcels WHERE owner_id = ?",
            (agent["id"],)
        )
        count = (await cursor.fetchone())[0]
        if count >= 3:
            raise HTTPException(status_code=400, detail="You can own at most 3 parcels")

        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE parcels SET owner_id = ?, claimed_at = ? WHERE id = ?",
            (agent["id"], now, parcel["id"])
        )
        await log_activity(
            db, agent["id"], agent["name"], "claimed",
            f"Claimed parcel at ({data.x}, {data.y})"
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT local_x, local_y, crop_type, planted_at, watered_at, growth_stage, ready_at FROM plots WHERE parcel_id = ?",
            (parcel["id"],)
        )
        plots = [build_plot_response(dict(pl)) for pl in await cursor.fetchall()]

        return ParcelResponse(
            id=parcel["id"],
            x=data.x,
            y=data.y,
            owner_id=agent["id"],
            owner_name=agent["name"],
            claimed_at=now,
            plots=plots
        )
    finally:
        await db.close()


@app.get("/api/parcels/{parcel_id}", response_model=ParcelResponse)
async def get_parcel(parcel_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT p.id, p.x, p.y, p.owner_id, p.claimed_at, a.name as owner_name
            FROM parcels p
            LEFT JOIN agents a ON p.owner_id = a.id
            WHERE p.id = ?
        """, (parcel_id,))
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        cursor = await db.execute(
            "SELECT local_x, local_y, crop_type, planted_at, watered_at, growth_stage, ready_at FROM plots WHERE parcel_id = ?",
            (parcel_id,)
        )
        plots = [build_plot_response(dict(pl)) for pl in await cursor.fetchall()]

        return ParcelResponse(**dict(parcel), plots=plots)
    finally:
        await db.close()


@app.post("/api/parcels/{parcel_id}/plant")
async def plant_crop(parcel_id: int, data: PlantCrop, agent: dict = Depends(get_current_agent)):
    if data.crop_type not in CROPS:
        raise HTTPException(status_code=400, detail=f"Unknown crop type: {data.crop_type}. Available: {list(CROPS.keys())}")

    db = await get_db()
    try:
        cursor = await db.execute("SELECT owner_id FROM parcels WHERE id = ?", (parcel_id,))
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if parcel["owner_id"] != agent["id"]:
            raise HTTPException(status_code=403, detail="You don't own this parcel")

        cursor = await db.execute(
            "SELECT crop_type FROM plots WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
            (parcel_id, data.local_x, data.local_y)
        )
        plot = await cursor.fetchone()
        if not plot:
            raise HTTPException(status_code=404, detail="Plot not found")
        if plot["crop_type"]:
            raise HTTPException(status_code=409, detail="Plot already has a crop. Harvest first.")

        now = datetime.now(timezone.utc).isoformat()
        crop = CROPS[data.crop_type]
        ready_at = (datetime.now(timezone.utc) + timedelta(minutes=crop["grow_time_minutes"])).isoformat()

        await db.execute("""
            UPDATE plots SET crop_type = ?, planted_at = ?, growth_stage = 'seedling', ready_at = ?
            WHERE parcel_id = ? AND local_x = ? AND local_y = ?
        """, (data.crop_type, now, ready_at, parcel_id, data.local_x, data.local_y))

        await log_activity(
            db, agent["id"], agent["name"], "planted",
            f"Planted {crop['name']} {crop['emoji']} at parcel {parcel_id} ({data.local_x},{data.local_y})"
        )
        await db.commit()

        return {"status": "planted", "crop": crop["name"], "ready_at": ready_at}
    finally:
        await db.close()


@app.post("/api/parcels/{parcel_id}/water")
async def water_parcel(parcel_id: int, data: WaterParcel, agent: dict = Depends(get_current_agent)):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT owner_id FROM parcels WHERE id = ?", (parcel_id,))
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if parcel["owner_id"] != agent["id"]:
            raise HTTPException(status_code=403, detail="You don't own this parcel")

        now = datetime.now(timezone.utc).isoformat()

        if data.local_x is not None and data.local_y is not None:
            cursor = await db.execute(
                "SELECT crop_type, planted_at, ready_at FROM plots WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                (parcel_id, data.local_x, data.local_y)
            )
            plot = await cursor.fetchone()
            if not plot or not plot["crop_type"]:
                raise HTTPException(status_code=400, detail="No crop in this plot to water")

            crop = CROPS.get(plot["crop_type"])
            if crop and plot["planted_at"]:
                planted_at = datetime.fromisoformat(plot["planted_at"]).replace(tzinfo=timezone.utc)
                new_ready = planted_at + timedelta(minutes=int(crop["grow_time_minutes"] * 0.75))
                await db.execute(
                    "UPDATE plots SET watered_at = ?, ready_at = ? WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                    (now, new_ready.isoformat(), parcel_id, data.local_x, data.local_y)
                )
            watered_count = 1
        else:
            cursor = await db.execute(
                "SELECT local_x, local_y, crop_type, planted_at FROM plots WHERE parcel_id = ? AND crop_type IS NOT NULL AND watered_at IS NULL",
                (parcel_id,)
            )
            plots_to_water = await cursor.fetchall()
            watered_count = 0
            for p in plots_to_water:
                crop = CROPS.get(p["crop_type"])
                if crop and p["planted_at"]:
                    planted_at = datetime.fromisoformat(p["planted_at"]).replace(tzinfo=timezone.utc)
                    new_ready = planted_at + timedelta(minutes=int(crop["grow_time_minutes"] * 0.75))
                    await db.execute(
                        "UPDATE plots SET watered_at = ?, ready_at = ? WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                        (now, new_ready.isoformat(), parcel_id, p["local_x"], p["local_y"])
                    )
                    watered_count += 1

        await log_activity(
            db, agent["id"], agent["name"], "watered",
            f"Watered {watered_count} plot(s) in parcel {parcel_id}"
        )
        await db.commit()

        return {"status": "watered", "plots_watered": watered_count}
    finally:
        await db.close()


@app.post("/api/parcels/{parcel_id}/harvest")
async def harvest_crop(parcel_id: int, data: HarvestCrop, agent: dict = Depends(get_current_agent)):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT owner_id FROM parcels WHERE id = ?", (parcel_id,))
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if parcel["owner_id"] != agent["id"]:
            raise HTTPException(status_code=403, detail="You don't own this parcel")

        cursor = await db.execute(
            "SELECT crop_type, planted_at, watered_at, ready_at FROM plots WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
            (parcel_id, data.local_x, data.local_y)
        )
        plot = await cursor.fetchone()
        if not plot or not plot["crop_type"]:
            raise HTTPException(status_code=400, detail="No crop to harvest")

        plot_dict = dict(plot)
        stage, progress = compute_growth_stage(plot_dict)
        if stage != "mature":
            raise HTTPException(
                status_code=400,
                detail=f"Crop not ready yet. Stage: {stage}, Progress: {round(progress * 100, 1)}%"
            )

        crop = CROPS[plot["crop_type"]]
        points = crop["points"]

        await db.execute("""
            UPDATE plots SET crop_type = NULL, planted_at = NULL, watered_at = NULL,
                             growth_stage = 'empty', ready_at = NULL
            WHERE parcel_id = ? AND local_x = ? AND local_y = ?
        """, (parcel_id, data.local_x, data.local_y))

        await db.execute(
            "UPDATE agents SET score = score + ? WHERE id = ?",
            (points, agent["id"])
        )

        await log_activity(
            db, agent["id"], agent["name"], "harvested",
            f"Harvested {crop['name']} {crop['emoji']} (+{points} pts) from parcel {parcel_id}"
        )
        await db.commit()

        return {"status": "harvested", "crop": crop["name"], "points_earned": points}
    finally:
        await db.close()


@app.get("/api/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(limit: int = 20):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT name, score FROM agents ORDER BY score DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            LeaderboardEntry(rank=i + 1, agent_name=r["name"], score=r["score"])
            for i, r in enumerate(rows)
        ]
    finally:
        await db.close()


@app.get("/api/stats")
async def get_stats():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM agents")
        total_agents = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM parcels WHERE owner_id IS NOT NULL")
        claimed_parcels = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM plots WHERE crop_type IS NOT NULL")
        active_crops = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COALESCE(SUM(score), 0) FROM agents")
        total_points = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM activities")
        total_actions = (await cursor.fetchone())[0]

        return {
            "total_agents": total_agents,
            "claimed_parcels": claimed_parcels,
            "total_parcels": 400,
            "active_crops": active_crops,
            "total_points_earned": total_points,
            "total_actions": total_actions
        }
    finally:
        await db.close()


# --- Chat endpoints ---

@app.post("/api/chat", response_model=ChatMessageResponse)
async def post_chat_message(data: ChatMessage, agent: dict = Depends(get_current_agent)):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO chat_messages (agent_id, agent_name, message) VALUES (?, ?, ?)",
            (agent["id"], agent["name"], data.message)
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, agent_id, agent_name, message, created_at FROM chat_messages ORDER BY id DESC LIMIT 1"
        )
        msg = await cursor.fetchone()
        return ChatMessageResponse(**dict(msg))
    finally:
        await db.close()


@app.get("/api/chat", response_model=list[ChatMessageResponse])
async def get_chat_messages(limit: int = 50, since_id: int = 0):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, agent_id, agent_name, message, created_at FROM chat_messages WHERE id > ? ORDER BY id DESC LIMIT ?",
            (since_id, limit)
        )
        rows = await cursor.fetchall()
        return [ChatMessageResponse(**dict(r)) for r in rows]
    finally:
        await db.close()
