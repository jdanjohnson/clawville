from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import secrets
import random
import aiosqlite

from app.database import get_db, init_db, CROPS, DB_PATH, LAND_RUSH_BONUS, STEAL_COST, STEAL_SUCCESS_RATE
from app.models import (
    AgentRegister, AgentResponse, ParcelClaim, PlantCrop, WaterParcel,
    HarvestCrop, PlotResponse, ParcelResponse, WorldResponse,
    ActivityResponse, LeaderboardEntry, CropInfo, ChatMessage, ChatMessageResponse,
    StealRequest, UnlockCropRequest
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="ClawVille: Underwater Edition", lifespan=lifespan)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_agent(x_api_token: str = Header(..., alias="X-API-Token")):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, api_token, score, sand_dollars, created_at FROM agents WHERE api_token = ?",
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


def compute_growth_stage(plot_row: dict) -> tuple[str, float, float, bool]:
    if not plot_row["crop_type"] or not plot_row["planted_at"]:
        return "empty", 0.0, 1.0, False
    crop = CROPS.get(plot_row["crop_type"])
    if not crop:
        return "empty", 0.0, 1.0, False
    planted_at = datetime.fromisoformat(plot_row["planted_at"]).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    grow_minutes = crop["grow_time_minutes"]
    if plot_row["watered_at"]:
        grow_minutes = int(grow_minutes * 0.75)
    elapsed = (now - planted_at).total_seconds() / 60.0
    progress = min(elapsed / grow_minutes, 1.0) if grow_minutes > 0 else 1.0
    if progress >= 1.0:
        mature_at_minutes = grow_minutes
        minutes_since_mature = elapsed - mature_at_minutes
        decay_minutes = crop.get("decay_minutes", 10)
        if minutes_since_mature >= decay_minutes:
            return "dead", 1.0, 0.0, True
        health = max(0.0, 1.0 - (minutes_since_mature / decay_minutes))
        return "mature", 1.0, health, False
    elif progress >= 0.66:
        return "growing", progress, 1.0, False
    elif progress >= 0.33:
        return "sprouting", progress, 1.0, False
    else:
        return "seedling", progress, 1.0, False


def build_plot_response(plot_row: dict) -> PlotResponse:
    stage, progress, health, is_dead = compute_growth_stage(plot_row)
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
        progress_pct=round(progress * 100, 1),
        health=round(health, 3),
        is_dead=is_dead,
    )


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
            "INSERT INTO agents (name, api_token, sand_dollars) VALUES (?, ?, 100)",
            (data.name, token)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id, name, api_token, score, sand_dollars, created_at FROM agents WHERE api_token = ?",
            (token,)
        )
        agent = await cursor.fetchone()
        await log_activity(db, agent["id"], agent["name"], "registered",
                           f"{data.name} swam into ClawVille! (+100 sand dollars)")
        await db.commit()
        return AgentResponse(**dict(agent))
    finally:
        await db.close()


@app.get("/api/agents/me")
async def get_me(agent: dict = Depends(get_current_agent)):
    return {
        "id": agent["id"],
        "name": agent["name"],
        "score": agent["score"],
        "sand_dollars": agent["sand_dollars"],
    }


@app.get("/api/crops", response_model=list[CropInfo])
async def list_crops():
    return [CropInfo(key=k, **v) for k, v in CROPS.items()]


@app.get("/api/world", response_model=WorldResponse)
async def get_world():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT p.id, p.x, p.y, p.owner_id, p.claimed_at, p.price, a.name as owner_name "
            "FROM parcels p LEFT JOIN agents a ON p.owner_id = a.id ORDER BY p.y, p.x"
        )
        parcels_raw = await cursor.fetchall()
        cursor = await db.execute(
            "SELECT pl.parcel_id, pl.local_x, pl.local_y, pl.crop_type, "
            "pl.planted_at, pl.watered_at, pl.growth_stage, pl.ready_at FROM plots pl"
        )
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
            plot_responses = [build_plot_response(pl) for pl in plots_by_parcel.get(p_dict["id"], [])]
            parcels.append(ParcelResponse(
                id=p_dict["id"], x=p_dict["x"], y=p_dict["y"],
                owner_id=p_dict["owner_id"], owner_name=p_dict["owner_name"],
                claimed_at=p_dict["claimed_at"], price=p_dict["price"],
                plots=plot_responses
            ))
        cursor = await db.execute("SELECT COUNT(*) FROM agents")
        agent_count = (await cursor.fetchone())[0]
        return WorldResponse(
            world_size=20, total_parcels=len(parcels),
            claimed_parcels=claimed_count, total_agents=agent_count,
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
            "SELECT id, x, y, owner_id, claimed_at, price FROM parcels WHERE x = ? AND y = ?",
            (data.x, data.y)
        )
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if parcel["owner_id"]:
            raise HTTPException(status_code=409, detail="Parcel already claimed")
        cursor = await db.execute(
            "SELECT COUNT(*) FROM parcels WHERE owner_id = ?", (agent["id"],)
        )
        count = (await cursor.fetchone())[0]
        if count >= 5:
            raise HTTPException(status_code=400, detail="You can own at most 5 parcels")
        price = parcel["price"]
        if price > 0 and agent["sand_dollars"] < price:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough sand dollars. Price: {price}, you have: {agent['sand_dollars']}"
            )
        now = datetime.now(timezone.utc).isoformat()
        if price > 0:
            await db.execute(
                "UPDATE agents SET sand_dollars = sand_dollars - ? WHERE id = ?",
                (price, agent["id"])
            )
        await db.execute(
            "UPDATE parcels SET owner_id = ?, claimed_at = ? WHERE id = ?",
            (agent["id"], now, parcel["id"])
        )
        parcel_number = count + 1
        bonus = LAND_RUSH_BONUS.get(parcel_number, 0)
        if bonus > 0:
            await db.execute(
                "UPDATE agents SET sand_dollars = sand_dollars + ? WHERE id = ?",
                (bonus, agent["id"])
            )
        cost_text = f" (cost: {price} sand dollars)" if price > 0 else " (free!)"
        bonus_text = f" +{bonus} land rush bonus!" if bonus > 0 else ""
        await log_activity(db, agent["id"], agent["name"], "claimed",
                           f"Claimed parcel at ({data.x}, {data.y}){cost_text}{bonus_text}")
        await db.commit()
        cursor = await db.execute(
            "SELECT local_x, local_y, crop_type, planted_at, watered_at, growth_stage, ready_at "
            "FROM plots WHERE parcel_id = ?",
            (parcel["id"],)
        )
        plots = [build_plot_response(dict(pl)) for pl in await cursor.fetchall()]
        return ParcelResponse(
            id=parcel["id"], x=data.x, y=data.y, owner_id=agent["id"],
            owner_name=agent["name"], claimed_at=now, price=price, plots=plots
        )
    finally:
        await db.close()


@app.get("/api/parcels/{parcel_id}", response_model=ParcelResponse)
async def get_parcel(parcel_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT p.id, p.x, p.y, p.owner_id, p.claimed_at, p.price, a.name as owner_name "
            "FROM parcels p LEFT JOIN agents a ON p.owner_id = a.id WHERE p.id = ?",
            (parcel_id,)
        )
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        cursor = await db.execute(
            "SELECT local_x, local_y, crop_type, planted_at, watered_at, growth_stage, ready_at "
            "FROM plots WHERE parcel_id = ?",
            (parcel_id,)
        )
        plots = [build_plot_response(dict(pl)) for pl in await cursor.fetchall()]
        return ParcelResponse(**dict(parcel), plots=plots)
    finally:
        await db.close()


@app.post("/api/parcels/{parcel_id}/plant")
async def plant_crop(parcel_id: int, data: PlantCrop, agent: dict = Depends(get_current_agent)):
    if data.crop_type not in CROPS:
        raise HTTPException(status_code=400, detail=f"Unknown crop type: {data.crop_type}")
    crop = CROPS[data.crop_type]
    if crop["unlock_cost"] > 0:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id FROM unlocked_crops WHERE agent_id = ? AND crop_type = ?",
                (agent["id"], data.crop_type)
            )
            unlocked = await cursor.fetchone()
            if not unlocked:
                raise HTTPException(
                    status_code=403,
                    detail=f"{crop['name']} must be unlocked first! Cost: {crop['unlock_cost']} sand dollars"
                )
        finally:
            await db.close()
    plant_cost = crop["plant_cost"]
    if plant_cost > 0 and agent["sand_dollars"] < plant_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough sand dollars. Cost: {plant_cost}, you have: {agent['sand_dollars']}"
        )
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
        ready_at = (datetime.now(timezone.utc) + timedelta(minutes=crop["grow_time_minutes"])).isoformat()
        if plant_cost > 0:
            await db.execute(
                "UPDATE agents SET sand_dollars = sand_dollars - ? WHERE id = ?",
                (plant_cost, agent["id"])
            )
        await db.execute(
            "UPDATE plots SET crop_type = ?, planted_at = ?, growth_stage = 'seedling', ready_at = ? "
            "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
            (data.crop_type, now, ready_at, parcel_id, data.local_x, data.local_y)
        )
        cost_text = f" (cost: {plant_cost} sand dollars)" if plant_cost > 0 else ""
        await log_activity(db, agent["id"], agent["name"], "planted",
                           f"Planted {crop['name']} {crop['emoji']} at parcel {parcel_id} ({data.local_x},{data.local_y}){cost_text}")
        await db.commit()
        return {"status": "planted", "crop": crop["name"], "ready_at": ready_at, "plant_cost": plant_cost}
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
                "SELECT crop_type, planted_at, ready_at FROM plots "
                "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
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
                    "UPDATE plots SET watered_at = ?, ready_at = ? "
                    "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                    (now, new_ready.isoformat(), parcel_id, data.local_x, data.local_y)
                )
            watered_count = 1
        else:
            cursor = await db.execute(
                "SELECT local_x, local_y, crop_type, planted_at FROM plots "
                "WHERE parcel_id = ? AND crop_type IS NOT NULL AND watered_at IS NULL",
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
                        "UPDATE plots SET watered_at = ?, ready_at = ? "
                        "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                        (now, new_ready.isoformat(), parcel_id, p["local_x"], p["local_y"])
                    )
                    watered_count += 1
        await log_activity(db, agent["id"], agent["name"], "watered",
                           f"Watered {watered_count} plot(s) in parcel {parcel_id}")
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
            "SELECT crop_type, planted_at, watered_at, ready_at FROM plots "
            "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
            (parcel_id, data.local_x, data.local_y)
        )
        plot = await cursor.fetchone()
        if not plot or not plot["crop_type"]:
            raise HTTPException(status_code=400, detail="No crop to harvest")
        plot_dict = dict(plot)
        stage, progress, health, is_dead = compute_growth_stage(plot_dict)
        if is_dead:
            await db.execute(
                "UPDATE plots SET crop_type = NULL, planted_at = NULL, watered_at = NULL, "
                "growth_stage = 'empty', ready_at = NULL "
                "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                (parcel_id, data.local_x, data.local_y)
            )
            crop_name = CROPS.get(plot["crop_type"], {}).get("name", "Unknown")
            await log_activity(db, agent["id"], agent["name"], "lost",
                               f"{crop_name} was eaten by algae at parcel {parcel_id}! Too slow!")
            await db.commit()
            return {"status": "dead", "message": "Algae ate your crop! You were too slow to harvest."}
        if stage != "mature":
            raise HTTPException(
                status_code=400,
                detail=f"Crop not ready yet. Stage: {stage}, Progress: {round(progress * 100, 1)}%"
            )
        crop = CROPS[plot["crop_type"]]
        points = crop["points"]
        sand_yield = crop.get("sand_dollar_yield", 0)
        health_bonus = int(sand_yield * 0.3 * health)
        await db.execute(
            "UPDATE plots SET crop_type = NULL, planted_at = NULL, watered_at = NULL, "
            "growth_stage = 'empty', ready_at = NULL "
            "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
            (parcel_id, data.local_x, data.local_y)
        )
        total_sand = sand_yield + health_bonus
        await db.execute(
            "UPDATE agents SET score = score + ?, sand_dollars = sand_dollars + ? WHERE id = ?",
            (points, total_sand, agent["id"])
        )
        bonus_text = f" (+{health_bonus} health bonus!)" if health_bonus > 0 else ""
        await log_activity(db, agent["id"], agent["name"], "harvested",
                           f"Harvested {crop['name']} {crop['emoji']} (+{points} pts, +{total_sand} sand dollars{bonus_text}) from parcel {parcel_id}")
        await db.commit()
        return {
            "status": "harvested", "crop": crop["name"],
            "points_earned": points, "sand_dollars_earned": total_sand,
            "health_bonus": health_bonus,
        }
    finally:
        await db.close()


@app.post("/api/steal")
async def steal_crop(data: StealRequest, agent: dict = Depends(get_current_agent)):
    if agent["sand_dollars"] < STEAL_COST:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough sand dollars for raid. Cost: {STEAL_COST}, you have: {agent['sand_dollars']}"
        )
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT owner_id FROM parcels WHERE id = ?", (data.target_parcel_id,)
        )
        parcel = await cursor.fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")
        if not parcel["owner_id"]:
            raise HTTPException(status_code=400, detail="Can't steal from unclaimed parcel")
        if parcel["owner_id"] == agent["id"]:
            raise HTTPException(status_code=400, detail="Can't steal from yourself!")
        cursor = await db.execute(
            "SELECT crop_type, planted_at, watered_at, ready_at FROM plots "
            "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
            (data.target_parcel_id, data.local_x, data.local_y)
        )
        plot = await cursor.fetchone()
        if not plot or not plot["crop_type"]:
            raise HTTPException(status_code=400, detail="No crop in that plot to steal")
        plot_dict = dict(plot)
        stage, progress, health, is_dead = compute_growth_stage(plot_dict)
        if stage != "mature":
            raise HTTPException(status_code=400, detail="Can only steal mature crops!")
        if is_dead:
            raise HTTPException(status_code=400, detail="That crop is already dead from algae")
        await db.execute(
            "UPDATE agents SET sand_dollars = sand_dollars - ? WHERE id = ?",
            (STEAL_COST, agent["id"])
        )
        roll = random.randint(1, 100)
        success = roll <= STEAL_SUCCESS_RATE
        cursor = await db.execute("SELECT name FROM agents WHERE id = ?", (parcel["owner_id"],))
        victim = await cursor.fetchone()
        victim_name = victim["name"] if victim else "Unknown"
        if success:
            crop = CROPS[plot["crop_type"]]
            points = crop["points"]
            sand_yield = crop.get("sand_dollar_yield", 0)
            await db.execute(
                "UPDATE plots SET crop_type = NULL, planted_at = NULL, watered_at = NULL, "
                "growth_stage = 'empty', ready_at = NULL "
                "WHERE parcel_id = ? AND local_x = ? AND local_y = ?",
                (data.target_parcel_id, data.local_x, data.local_y)
            )
            await db.execute(
                "UPDATE agents SET score = score + ?, sand_dollars = sand_dollars + ? WHERE id = ?",
                (points, sand_yield, agent["id"])
            )
            await log_activity(db, agent["id"], agent["name"], "stole",
                               f"Raided {victim_name}'s parcel and stole {crop['name']} {crop['emoji']}! (+{points} pts, +{sand_yield} sand dollars)")
            await db.commit()
            return {
                "status": "success",
                "message": f"You stole {crop['name']} from {victim_name}!",
                "points_earned": points, "sand_dollars_earned": sand_yield,
                "raid_cost": STEAL_COST,
            }
        else:
            await log_activity(db, agent["id"], agent["name"], "failed_steal",
                               f"Failed to raid {victim_name}'s parcel! Lost {STEAL_COST} sand dollars.")
            await db.commit()
            return {
                "status": "failed",
                "message": f"Raid on {victim_name} failed! You lost {STEAL_COST} sand dollars.",
                "sand_dollars_lost": STEAL_COST,
            }
    finally:
        await db.close()


@app.get("/api/emporium")
async def get_emporium(agent: dict = Depends(get_current_agent)):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT crop_type FROM unlocked_crops WHERE agent_id = ?", (agent["id"],)
        )
        unlocked = {row["crop_type"] for row in await cursor.fetchall()}
        items = []
        for key, crop in CROPS.items():
            items.append({
                "key": key, "name": crop["name"], "tier": crop["tier"],
                "unlock_cost": crop["unlock_cost"], "plant_cost": crop["plant_cost"],
                "points": crop["points"], "sand_dollar_yield": crop["sand_dollar_yield"],
                "grow_time_minutes": crop["grow_time_minutes"],
                "decay_minutes": crop["decay_minutes"],
                "emoji": crop["emoji"], "color": crop["color"],
                "description": crop["description"],
                "unlocked": crop["unlock_cost"] == 0 or key in unlocked,
            })
        return {"sand_dollars": agent["sand_dollars"], "items": items}
    finally:
        await db.close()


@app.post("/api/emporium/unlock")
async def unlock_crop(data: UnlockCropRequest, agent: dict = Depends(get_current_agent)):
    if data.crop_type not in CROPS:
        raise HTTPException(status_code=400, detail=f"Unknown crop type: {data.crop_type}")
    crop = CROPS[data.crop_type]
    unlock_cost = crop["unlock_cost"]
    if unlock_cost == 0:
        raise HTTPException(status_code=400, detail=f"{crop['name']} is already free to plant!")
    if agent["sand_dollars"] < unlock_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough sand dollars. Need: {unlock_cost}, have: {agent['sand_dollars']}"
        )
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM unlocked_crops WHERE agent_id = ? AND crop_type = ?",
            (agent["id"], data.crop_type)
        )
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"You already unlocked {crop['name']}!")
        await db.execute(
            "UPDATE agents SET sand_dollars = sand_dollars - ? WHERE id = ?",
            (unlock_cost, agent["id"])
        )
        await db.execute(
            "INSERT INTO unlocked_crops (agent_id, crop_type) VALUES (?, ?)",
            (agent["id"], data.crop_type)
        )
        await log_activity(db, agent["id"], agent["name"], "unlocked",
                           f"Unlocked {crop['name']} {crop['emoji']} in the Reef Emporium! (-{unlock_cost} sand dollars)")
        await db.commit()
        return {"status": "unlocked", "crop": crop["name"], "cost": unlock_cost}
    finally:
        await db.close()


@app.get("/api/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(limit: int = 20):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT name, score, sand_dollars FROM agents ORDER BY score DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            LeaderboardEntry(rank=i + 1, agent_name=r["name"], score=r["score"],
                             sand_dollars=r["sand_dollars"])
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
        cursor = await db.execute("SELECT COALESCE(SUM(sand_dollars), 0) FROM agents")
        total_sand_dollars = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM activities")
        total_actions = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM activities WHERE action = 'stole'")
        total_steals = (await cursor.fetchone())[0]
        return {
            "total_agents": total_agents, "claimed_parcels": claimed_parcels,
            "total_parcels": 400, "active_crops": active_crops,
            "total_points_earned": total_points, "total_sand_dollars": total_sand_dollars,
            "total_actions": total_actions, "total_steals": total_steals,
        }
    finally:
        await db.close()


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
            "SELECT id, agent_id, agent_name, message, created_at FROM chat_messages "
            "WHERE id > ? ORDER BY id DESC LIMIT ?",
            (since_id, limit)
        )
        rows = await cursor.fetchall()
        return [ChatMessageResponse(**dict(r)) for r in rows]
    finally:
        await db.close()
