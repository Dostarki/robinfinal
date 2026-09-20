import base64
import hashlib
import os
import re
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/x")

X_AUTH_URL = "https://x.com/i/oauth2/authorize"
X_TOKEN_URL = "https://api.x.com/2/oauth2/token"
X_API = "https://api.x.com/2"
SCOPES = "tweet.read users.read follows.read like.read offline.access"
SESSION_COOKIE = "ri_x_session"
TASK_IDS = ("follow", "like_rt", "quote")
TASK_POINTS = {"follow": 20, "like_rt": 10, "quote": 50}
EVM_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def env(name, default=None):
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


def now():
    return datetime.now(timezone.utc)


def tweet_id_from_url(url):
    match = re.search(r"/status/(\d+)", url or "")
    return match.group(1) if match else None


def task_config():
    tweet_url = env("X_TASK_TWEET_URL", "")
    return {
        "target_username": env("X_TARGET_USERNAME", "RobinityInt"),
        "tweet_url": tweet_url,
        "tweet_id": tweet_id_from_url(tweet_url),
        "quote_text": env("X_QUOTE_TEXT", "Robinity Intelligence — token research with context. @RobinityInt"),
    }


def configured():
    return bool(env("X_CLIENT_ID") and env("X_CLIENT_SECRET") and env("X_REDIRECT_URI"))


def get_db(request: Request):
    return request.app.state.db


async def current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    db = get_db(request)
    session = await db.x_sessions.find_one({"token": token}, {"_id": 0})
    if not session or datetime.fromisoformat(session["expires_at"]) < now():
        return None
    return await db.x_users.find_one({"x_id": session["x_id"]}, {"_id": 0})


def user_points(user):
    return sum(TASK_POINTS[t] for t in TASK_IDS if user.get("tasks", {}).get(t, {}).get("done"))


def public_user(user):
    if not user:
        return None
    return {
        "x_id": user["x_id"],
        "username": user["username"],
        "name": user.get("name"),
        "profile_image_url": user.get("profile_image_url"),
        "evm_address": user.get("evm_address"),
        "tasks": user.get("tasks", {}),
        "points": user_points(user),
    }


@router.get("/config")
async def get_config():
    cfg = task_config()
    return {"configured": configured(), "target_username": cfg["target_username"], "tweet_url": cfg["tweet_url"], "tweet_id": cfg["tweet_id"], "quote_text": cfg["quote_text"], "points": TASK_POINTS}


@router.get("/leaderboard")
async def leaderboard(request: Request):
    db = get_db(request)
    total = await db.x_users.count_documents({"evm_address": {"$exists": True}})
    cursor = db.x_users.find({"evm_address": {"$exists": True}}, {"_id": 0, "x_id": 1, "username": 1, "name": 1, "profile_image_url": 1, "tasks": 1, "points": 1, "points_updated_at": 1})
    users = await cursor.to_list(length=None)
    users.sort(key=lambda u: (-user_points(u), u.get("points_updated_at") or "\uffff"))
    entries = [{"rank": i + 1, "x_id": u["x_id"], "username": u["username"], "name": u.get("name"), "profile_image_url": u.get("profile_image_url"), "points": user_points(u),
                "completed": sum(1 for t in TASK_IDS if u.get("tasks", {}).get(t, {}).get("done"))} for i, u in enumerate(users[:10])]
    return {"entries": entries, "total_participants": total, "points": TASK_POINTS}


@router.get("/auth/login")
async def login(request: Request):
    if not configured():
        raise HTTPException(503, "X API credentials are not configured")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    await get_db(request).x_oauth_states.insert_one({"state": state, "verifier": verifier, "created_at": now().isoformat()})
    params = {
        "response_type": "code",
        "client_id": env("X_CLIENT_ID"),
        "redirect_uri": env("X_REDIRECT_URI"),
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{X_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/callback")
async def callback(request: Request, code: str = None, state: str = None, error: str = None):
    frontend = env("FRONTEND_URL", "/")
    if error or not code or not state:
        return RedirectResponse(f"{frontend}?x_error={error or 'denied'}")
    db = get_db(request)
    saved = await db.x_oauth_states.find_one_and_delete({"state": state})
    if not saved:
        return RedirectResponse(f"{frontend}?x_error=invalid_state")
    basic = base64.b64encode(f"{env('X_CLIENT_ID')}:{env('X_CLIENT_SECRET')}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        token_res = await client.post(X_TOKEN_URL, headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": env("X_REDIRECT_URI"), "code_verifier": saved["verifier"], "client_id": env("X_CLIENT_ID")})
        if token_res.status_code != 200:
            return RedirectResponse(f"{frontend}?x_error=token_exchange_failed")
        tokens = token_res.json()
        me_res = await client.get(f"{X_API}/users/me", params={"user.fields": "profile_image_url,name,username"}, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        if me_res.status_code != 200:
            return RedirectResponse(f"{frontend}?x_error=profile_failed")
        me = me_res.json()["data"]
    image = (me.get("profile_image_url") or "").replace("_normal", "_200x200")
    await db.x_users.update_one({"x_id": me["id"]}, {
        "$set": {"x_id": me["id"], "username": me["username"], "name": me.get("name"), "profile_image_url": image,
                 "access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token"),
                 "token_expires_at": (now() + timedelta(seconds=tokens.get("expires_in", 7200))).isoformat(), "updated_at": now().isoformat()},
        "$setOnInsert": {"created_at": now().isoformat(), "tasks": {}}}, upsert=True)
    session_token = secrets.token_urlsafe(48)
    await db.x_sessions.insert_one({"token": session_token, "x_id": me["id"], "expires_at": (now() + timedelta(days=30)).isoformat()})
    response = RedirectResponse(f"{frontend}?x_connected=1")
    response.set_cookie(SESSION_COOKIE, session_token, max_age=30 * 24 * 3600, httponly=True, secure=True, samesite="lax", path="/")
    return response


@router.get("/auth/dev-login")
async def dev_login(request: Request):
    if env("X_DEV_MOCK") != "1":
        raise HTTPException(404, "Not found")
    db = get_db(request)
    x_id = "dev-000001"
    await db.x_users.update_one({"x_id": x_id}, {"$set": {"x_id": x_id, "username": "robinity_tester", "name": "Robinity Tester", "profile_image_url": "/assets/robinity-logo.png",
                                                            "access_token": "dev", "refresh_token": None, "token_expires_at": (now() + timedelta(days=1)).isoformat()},
                                                   "$setOnInsert": {"created_at": now().isoformat(), "tasks": {}}}, upsert=True)
    session_token = secrets.token_urlsafe(48)
    await db.x_sessions.insert_one({"token": session_token, "x_id": x_id, "expires_at": (now() + timedelta(days=1)).isoformat()})
    response = RedirectResponse(f"{env('FRONTEND_URL', '/')}?x_connected=1")
    response.set_cookie(SESSION_COOKIE, session_token, max_age=24 * 3600, httponly=True, secure=True, samesite="lax", path="/")
    return response


@router.get("/me")
async def me(request: Request):
    return {"user": public_user(await current_user(request))}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await get_db(request).x_sessions.delete_one({"token": token})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


class EvmBody(BaseModel):
    address: str


@router.post("/evm")
async def save_evm(body: EvmBody, request: Request):
    user = await current_user(request)
    if not user:
        raise HTTPException(401, "Connect X first")
    if user.get("evm_address"):
        raise HTTPException(409, "EVM address already saved")
    address = body.address.strip()
    if not EVM_RE.match(address):
        raise HTTPException(400, "Invalid EVM address")
    await get_db(request).x_users.update_one({"x_id": user["x_id"]}, {"$set": {"evm_address": address, "evm_saved_at": now().isoformat()}})
    user["evm_address"] = address
    return {"user": public_user(user)}


async def refresh_access_token(db, user):
    if not user.get("refresh_token"):
        return user["access_token"]
    basic = base64.b64encode(f"{env('X_CLIENT_ID')}:{env('X_CLIENT_SECRET')}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.post(X_TOKEN_URL, headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}, data={
            "grant_type": "refresh_token", "refresh_token": user["refresh_token"], "client_id": env("X_CLIENT_ID")})
    if res.status_code != 200:
        raise HTTPException(401, "X session expired, please reconnect")
    tokens = res.json()
    await db.x_users.update_one({"x_id": user["x_id"]}, {"$set": {"access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token", user["refresh_token"]),
                                                                 "token_expires_at": (now() + timedelta(seconds=tokens.get("expires_in", 7200))).isoformat()}})
    return tokens["access_token"]


async def x_get(client, token, path, params=None):
    res = await client.get(f"{X_API}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
    if res.status_code in (402, 403):
        return None
    if res.status_code == 429:
        raise HTTPException(429, "X API rate limit reached, try again in a few minutes")
    if res.status_code != 200:
        raise HTTPException(502, f"X API error ({res.status_code})")
    return res.json()


async def check_follow(client, token, user, cfg):
    data = await x_get(client, token, f"/users/by/username/{cfg['target_username']}", {"user.fields": "connection_status"})
    if data is None:
        return None
    status = data.get("data", {}).get("connection_status")
    if status is not None:
        return "following" in status
    target_id = data["data"]["id"]
    token_next = None
    for _ in range(5):
        params = {"max_results": 1000}
        if token_next:
            params["pagination_token"] = token_next
        page = await x_get(client, token, f"/users/{user['x_id']}/following", params)
        if page is None:
            return None
        if any(u["id"] == target_id for u in page.get("data", [])):
            return True
        token_next = page.get("meta", {}).get("next_token")
        if not token_next:
            break
    return False


async def user_refs(client, token, user, kind, tweet_id):
    data = await x_get(client, token, f"/users/{user['x_id']}/tweets", {"max_results": 50, "tweet.fields": "referenced_tweets"})
    if data is None:
        return None
    return any(ref.get("type") == kind and ref.get("id") == tweet_id for t in data.get("data", []) for ref in t.get("referenced_tweets", []))


async def check_like_rt(client, token, user, cfg):
    liked = await x_get(client, token, f"/users/{user['x_id']}/liked_tweets", {"max_results": 100})
    liked_ok = None if liked is None else any(t["id"] == cfg["tweet_id"] for t in liked.get("data", []))
    rt_ok = await user_refs(client, token, user, "retweeted", cfg["tweet_id"])
    if liked_ok is None or rt_ok is None:
        return None
    return liked_ok and rt_ok


async def check_quote(client, token, user, cfg):
    return await user_refs(client, token, user, "quoted", cfg["tweet_id"])


CHECKS = {"follow": check_follow, "like_rt": check_like_rt, "quote": check_quote}


@router.post("/tasks/{task_id}/verify")
async def verify_task(task_id: str, request: Request):
    if task_id not in TASK_IDS:
        raise HTTPException(404, "Unknown task")
    user = await current_user(request)
    if not user:
        raise HTTPException(401, "Connect X first")
    if not user.get("evm_address"):
        raise HTTPException(400, "Save your EVM address first")
    cfg = task_config()
    if task_id != "follow" and not cfg["tweet_id"]:
        raise HTTPException(503, "Task tweet link is not configured")
    db = get_db(request)
    token = user["access_token"]
    if datetime.fromisoformat(user["token_expires_at"]) < now() + timedelta(minutes=1):
        token = await refresh_access_token(db, user)
    if token == "dev":
        result = None
    else:
        async with httpx.AsyncClient(timeout=20) as client:
            result = await CHECKS[task_id](client, token, user, cfg)
    if result is False:
        raise HTTPException(422, "Not completed yet on X. Finish the action, then verify again.")
    entry = {"done": True, "verified": result is True, "completed_at": now().isoformat(), "points": TASK_POINTS[task_id]}
    user.setdefault("tasks", {})[task_id] = entry
    await db.x_users.update_one({"x_id": user["x_id"]}, {"$set": {f"tasks.{task_id}": entry, "points": user_points(user), "points_updated_at": entry["completed_at"]}})
    return {"user": public_user(user), "verified": result is True, "points_awarded": TASK_POINTS[task_id]}
