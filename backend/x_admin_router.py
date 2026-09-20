"""Admin management for the landing X rewards plugin: task settings, custom tasks, connected users."""
import re

from fastapi import APIRouter, Request

from core import api_error, new_id, require_admin, short_text
from x_router import EVM_RE, TASK_IDS, now, public_user, task_config, task_points_map, user_points

router = APIRouter(prefix="/api/admin/x")
CHECKS = ("none", "like_rt", "quote")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def db_of(request: Request):
    return request.app.state.db


async def body_of(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise api_error(400, "Invalid JSON")
    return data if isinstance(data, dict) else {}


def parse_points(value, allow_negative=False):
    try:
        points = int(value)
    except (TypeError, ValueError):
        raise api_error(400, "Points must be a whole number")
    if (points < 0 and not allow_negative) or abs(points) > 1_000_000:
        raise api_error(400, "Points out of range")
    return points


async def settings_payload(db):
    cfg = await task_config(db)
    saved = await db.x_settings.find_one({"key": "tasks"}, {"_id": 0}) or {}
    return {"target_username": cfg["target_username"], "tweet_url": cfg["tweet_url"], "tweet_id": cfg["tweet_id"], "quote_text": cfg["quote_text"], "points": cfg["points"],
            "custom_tasks": saved.get("custom_tasks") or [], "source": "database" if saved else "env"}


def admin_user(user, cfg):
    item = public_user(user, cfg)
    item.update({"points_adjustment": int(user.get("points_adjustment") or 0), "created_at": user.get("created_at"), "source": "manual" if str(user["x_id"]).startswith("manual-") else "x",
                 "task_points": sum(points for task_id, points in task_points_map(cfg).items() if (user.get("tasks") or {}).get(task_id, {}).get("done"))})
    return item


# ─── Settings ─────────────────────────────────────────────────────────────────
@router.get("/settings")
async def get_settings(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    return await settings_payload(db)


@router.put("/settings")
async def save_settings(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    body = await body_of(request)
    username = str(body.get("target_username") or "").strip().lstrip("@")
    tweet_url = str(body.get("tweet_url") or "").strip()
    quote_text = str(body.get("quote_text") or "").strip()
    if not USERNAME_RE.match(username):
        raise api_error(400, "Invalid X username")
    if tweet_url and not re.match(r"^https://(x|twitter)\.com/[A-Za-z0-9_]+/status/\d+", tweet_url):
        raise api_error(400, "Tweet link must look like https://x.com/user/status/123")
    if len(quote_text) > 280:
        raise api_error(400, "Quote text must be 280 characters or fewer")
    points = {task_id: parse_points((body.get("points") or {}).get(task_id)) for task_id in TASK_IDS}
    await db.x_settings.update_one({"key": "tasks"}, {"$set": {"key": "tasks", "target_username": username, "tweet_url": tweet_url, "quote_text": quote_text, "points": points, "updated_at": now().isoformat()}}, upsert=True)
    return await settings_payload(db)


# ─── Custom tasks ─────────────────────────────────────────────────────────────
def task_from_body(body, task_id):
    title, text, link = short_text(body.get("title"), 120), str(body.get("text") or "").strip()[:300], str(body.get("link") or "").strip()
    check = body.get("check") if body.get("check") in CHECKS else "none"
    if not title:
        raise api_error(400, "Task title is required")
    if link and not re.match(r"^https?://", link):
        raise api_error(400, "Task link must start with http(s)://")
    if check != "none" and not re.search(r"/status/\d+", link):
        raise api_error(400, "Like/RT and quote checks need a tweet link")
    return {"id": task_id, "title": title, "text": text, "link": link, "points": parse_points(body.get("points")), "check": check, "active": body.get("active", True) is not False}


@router.post("/tasks", status_code=201)
async def add_task(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    task = task_from_body(await body_of(request), "custom-" + new_id()[:8])
    task["created_at"] = now().isoformat()
    await db.x_settings.update_one({"key": "tasks"}, {"$set": {"key": "tasks"}, "$push": {"custom_tasks": task}}, upsert=True)
    return {"task": task}


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, request: Request):
    db = db_of(request)
    await require_admin(db, request)
    task = task_from_body(await body_of(request), task_id)
    result = await db.x_settings.update_one({"key": "tasks", "custom_tasks.id": task_id}, {"$set": {f"custom_tasks.$.{k}": v for k, v in task.items() if k != "id"}})
    if not result.matched_count:
        raise api_error(404, "Task not found")
    return {"task": task}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request):
    db = db_of(request)
    await require_admin(db, request)
    result = await db.x_settings.update_one({"key": "tasks"}, {"$pull": {"custom_tasks": {"id": task_id}}})
    if not result.modified_count:
        raise api_error(404, "Task not found")
    return {"ok": True}


# ─── Users ────────────────────────────────────────────────────────────────────
@router.get("/users")
async def list_users(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    cfg = await task_config(db)
    query = str(request.query_params.get("q") or "").strip().lstrip("@")
    filter_ = {"$or": [{"username": {"$regex": re.escape(query), "$options": "i"}}, {"name": {"$regex": re.escape(query), "$options": "i"}}, {"evm_address": {"$regex": re.escape(query), "$options": "i"}}]} if query else {}
    users = await db.x_users.find(filter_, {"_id": 0, "access_token": 0, "refresh_token": 0}).to_list(2000)
    items = [admin_user(u, cfg) for u in users]
    items.sort(key=lambda u: (-u["points"], u["username"].lower()))
    return {"users": items, "total": await db.x_users.count_documents({}), "tasks": [{"id": t, "points": cfg["points"][t]} for t in TASK_IDS] + [{"id": t["id"], "title": t["title"], "points": t["points"]} for t in cfg["custom_tasks"]]}


@router.post("/users", status_code=201)
async def add_user(request: Request):
    db = db_of(request)
    admin = await require_admin(db, request)
    body = await body_of(request)
    username = str(body.get("username") or "").strip().lstrip("@")
    if not USERNAME_RE.match(username):
        raise api_error(400, "Invalid X username")
    if await db.x_users.find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}):
        raise api_error(409, "A user with this X username already exists")
    evm = str(body.get("evm_address") or "").strip()
    if evm and not EVM_RE.match(evm):
        raise api_error(400, "Invalid EVM address")
    user = {"x_id": "manual-" + new_id()[:12], "username": username, "name": short_text(body.get("name"), 80) or username, "profile_image_url": None, "tasks": {},
            "points_adjustment": parse_points(body.get("points") or 0), "created_at": now().isoformat(), "updated_at": now().isoformat(), "created_by": admin["address"], "points_updated_at": now().isoformat()}
    if evm:
        user.update({"evm_address": evm, "evm_saved_at": now().isoformat()})
    await db.x_users.insert_one(dict(user))
    return {"user": admin_user(user, await task_config(db))}


@router.patch("/users/{x_id}")
async def update_user(x_id: str, request: Request):
    db = db_of(request)
    await require_admin(db, request)
    body = await body_of(request)
    user = await db.x_users.find_one({"x_id": x_id}, {"_id": 0})
    if not user:
        raise api_error(404, "User not found")
    cfg = await task_config(db)
    update = {"updated_at": now().isoformat()}
    if isinstance(body.get("tasks"), dict):
        points = task_points_map(cfg)
        tasks = dict(user.get("tasks") or {})
        for task_id, done in body["tasks"].items():
            if task_id not in points:
                continue
            if done:
                tasks[task_id] = {"done": True, "verified": False, "completed_at": now().isoformat(), "points": points[task_id], "by_admin": True}
            else:
                tasks.pop(task_id, None)
        user["tasks"] = update["tasks"] = tasks
    if "evm_address" in body:
        evm = str(body.get("evm_address") or "").strip()
        if evm and not EVM_RE.match(evm):
            raise api_error(400, "Invalid EVM address")
        if evm:
            update["evm_address"] = evm
            user["evm_address"] = evm
    if "points" in body:
        target = parse_points(body.get("points"))
        user["points_adjustment"] = 0
        update["points_adjustment"] = target - user_points(user, cfg)
        user["points_adjustment"] = update["points_adjustment"]
    update["points"] = user_points(user, cfg)
    update["points_updated_at"] = now().isoformat()
    ops = {"$set": update}
    if "evm_address" in body and not str(body.get("evm_address") or "").strip():
        ops["$unset"] = {"evm_address": "", "evm_saved_at": ""}
        user.pop("evm_address", None)
    await db.x_users.update_one({"x_id": x_id}, ops)
    return {"user": admin_user({**user, **update}, cfg)}


@router.delete("/users/{x_id}")
async def delete_user(x_id: str, request: Request):
    db = db_of(request)
    await require_admin(db, request)
    result = await db.x_users.delete_one({"x_id": x_id})
    if not result.deleted_count:
        raise api_error(404, "User not found")
    await db.x_sessions.delete_many({"x_id": x_id})
    return {"ok": True}
