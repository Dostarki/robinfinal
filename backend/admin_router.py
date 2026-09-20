"""Admin authentication (wallet + TOTP), API key vault, deployments/activity, public state. Port of serve-app.js."""
import base64
import io
from datetime import datetime, timezone

import pyotp
import qrcode
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from core import (ADMIN_COOKIE, OWNER_ADDRESS, api_error, admin_session, decrypt, encrypt, host_of, issue_session, new_id, normalize, now_ms, recover_signer, require_admin, set_cookie, short_text, valid_network)

router = APIRouter(prefix="/api")

challenges: dict[str, dict] = {}
tickets: dict[str, dict] = {}
ADMIN_SESSION_MS = 30 * 60 * 1000


def db_of(request: Request):
    return request.app.state.db


def pool_of(request: Request):
    return request.app.state.key_pool


def creator_of(request: Request):
    return request.app.state.creator_service


async def body_of(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise api_error(400, "Invalid JSON")
    return data if isinstance(data, dict) else {}


async def ensure_owner(db):
    await db.admins.update_one({"address": OWNER_ADDRESS}, {"$setOnInsert": {"address": OWNER_ADDRESS, "role": "owner", "totp": None, "createdAt": now_ms()}}, upsert=True)


async def get_admin(db, address):
    await ensure_owner(db)
    return await db.admins.find_one({"address": address}, {"_id": 0})


def create_ticket(address, phase):
    token = new_id()
    tickets[token] = {"address": address, "phase": phase, "expires": now_ms() + 5 * 60 * 1000}
    return token


def get_ticket(token, phase):
    item = tickets.get(token)
    return item if item and item["phase"] == phase and item["expires"] >= now_ms() else None


def parse_expiry(value):
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(str(value)).replace(hour=23, minute=59, second=59, microsecond=999000, tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:
        raise api_error(400, "Invalid expiry date")


# ─── Auth ──────────────────────────────────────────────────────────────────────
@router.post("/auth/nonce")
async def auth_nonce(request: Request):
    body = await body_of(request)
    try:
        account = normalize(body.get("address"))
    except Exception:
        raise api_error(400, "Invalid wallet address")
    challenge_id, nonce = new_id(), new_id()
    issued = datetime.now(timezone.utc).isoformat()
    message = f"Robinity Intelligence Admin Access\nDomain: {host_of(request)}\nAddress: {account}\nNonce: {nonce}\nIssued At: {issued}\nPurpose: Sign in to the Robinity Intelligence admin panel."
    challenges[challenge_id] = {"account": account, "message": message, "expires": now_ms() + 5 * 60 * 1000}
    return {"challengeId": challenge_id, "message": message}


@router.post("/auth/verify-wallet")
async def auth_verify_wallet(request: Request):
    body = await body_of(request)
    challenge = challenges.pop(body.get("challengeId") or "", None)
    if not challenge or challenge["expires"] < now_ms():
        raise api_error(401, "Sign-in request expired. Start again.")
    try:
        signer = recover_signer(challenge["message"], body.get("signature"))
    except Exception:
        raise api_error(401, "Invalid wallet signature")
    if signer != challenge["account"]:
        raise api_error(401, "Signature does not match the connected wallet")
    admin = await get_admin(db_of(request), signer)
    if not admin:
        raise api_error(403, "This wallet is not an admin wallet")
    phase = "totp" if admin.get("totp") else "enroll"
    return {"phase": phase, "ticket": create_ticket(signer, phase)}


@router.post("/auth/totp-setup")
async def auth_totp_setup(request: Request):
    body = await body_of(request)
    item = get_ticket(body.get("ticket") or "", "enroll")
    if not item:
        raise api_error(401, "A valid administrator enrollment is required")
    admin = await get_admin(db_of(request), item["address"])
    if not admin:
        raise api_error(403, "This wallet is not an admin wallet")
    if admin.get("totp"):
        raise api_error(409, "Authenticator is already enrolled")
    secret = pyotp.random_base32(32)
    uri = pyotp.TOTP(secret).provisioning_uri(name=item["address"], issuer_name="Robinity Intelligence Admin")
    item["secret"], item["phase"] = secret, "setup"
    image = qrcode.make(uri, box_size=6, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"qrDataUrl": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}


@router.post("/auth/verify-totp")
async def auth_verify_totp(request: Request):
    body = await body_of(request)
    token = body.get("ticket") or ""
    item = get_ticket(token, "totp") or get_ticket(token, "setup")
    if not item:
        raise api_error(401, "Authenticator request expired. Start again.")
    db = db_of(request)
    admin = await get_admin(db, item["address"])
    secret = item.get("secret") if item["phase"] == "setup" else (decrypt(admin["totp"]) if admin and admin.get("totp") else None)
    code = str(body.get("code") or "").strip()
    if not admin or not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise api_error(401, "Invalid authenticator code")
    if item["phase"] == "setup":
        await db.admins.update_one({"address": admin["address"]}, {"$set": {"totp": encrypt(secret)}})
    tickets.pop(token, None)
    session_token = await issue_session(db, "admin_sessions", item["address"], ADMIN_SESSION_MS)
    response = JSONResponse({"address": item["address"], "role": admin["role"]})
    set_cookie(response, ADMIN_COOKIE, session_token, 1800)
    return response


@router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get(ADMIN_COOKIE)
    if token:
        await db_of(request).admin_sessions.delete_one({"token": token})
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/admin/me")
async def admin_me(request: Request):
    user = await require_admin(db_of(request), request)
    admin = await get_admin(db_of(request), user["address"])
    return {"address": user["address"], "role": admin["role"] if admin else "admin"}


# ─── Administrators ───────────────────────────────────────────────────────────
@router.get("/admins")
async def list_admins(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    await ensure_owner(db)
    admins = await db.admins.find({}, {"_id": 0}).to_list(500)
    return {"admins": [{"address": a["address"], "role": a["role"], "authenticatorEnrolled": bool(a.get("totp"))} for a in admins]}


@router.post("/admins", status_code=201)
async def add_admin(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may add administrators")
    body = await body_of(request)
    try:
        account = normalize(body.get("address"))
    except Exception:
        raise api_error(400, "Invalid wallet address")
    if await db.admins.find_one({"address": account}):
        raise api_error(409, "Wallet is already an admin")
    await db.admins.insert_one({"address": account, "role": "admin", "totp": None, "createdAt": now_ms(), "createdBy": user["address"]})
    return {"address": account}


# ─── API key vault ─────────────────────────────────────────────────────────────
@router.get("/admin/api-keys")
async def list_api_keys(request: Request):
    await require_admin(db_of(request), request)
    pool, creator = pool_of(request), creator_of(request)
    return {"keys": pool.snapshot(), "poolStatus": pool.status(), "dailyBudgets": creator.usage_snapshot(), "observedAt": now_ms(), "usageBasis": "Local UTC calendar-month requests, not provider credits", "publicProviders": ["RugCheck", "Honeypot.is"]}


@router.post("/admin/api-keys/settings")
async def api_key_settings(request: Request):
    user = await require_admin(db_of(request), request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may change API key settings")
    body = await body_of(request)
    try:
        limit = int(body.get("monthlyLimit"))
    except (TypeError, ValueError):
        raise api_error(400, "Invalid request budget or expiry date")
    if limit < 0 or limit > 100_000_000:
        raise api_error(400, "Invalid request budget or expiry date")
    expiry = parse_expiry(body.get("expiresAt"))
    if not pool_of(request).configure(body.get("id"), limit, expiry):
        raise api_error(404, "Key not found")
    await db_of(request).api_keys.update_one({"id": body.get("id")}, {"$set": {"monthlyLimit": limit, "expiresAt": expiry, "updatedAt": now_ms()}})
    return {"ok": True}


@router.post("/admin/api-keys", status_code=201)
async def add_api_key(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may add API keys")
    body = await body_of(request)
    provider = next((p for p in ["GoPlus", "Helius", "Etherscan", "Bitquery"] if p.lower() == str(body.get("provider") or "").strip().lower()), None)
    label = short_text(body.get("label"), 80)
    secret = body.get("secret").strip() if isinstance(body.get("secret"), str) else ""
    try:
        monthly_limit = max(0, min(100_000_000, int(body.get("monthlyLimit") or 0)))
    except (TypeError, ValueError):
        monthly_limit = -1
    if not provider or not label or len(secret) < 8 or len(secret) > 2048 or monthly_limit < 0:
        raise api_error(400, "Provider, label and a valid API key are required")
    expires_at = parse_expiry(body.get("expiresAt"))
    now = now_ms()
    entry = {"id": new_id(), "provider": provider, "label": label, "monthlyLimit": monthly_limit, "expiresAt": expires_at, "masked": "••••" + secret[-4:], "encrypted": encrypt(secret), "active": True, "requestCount": 0, "successCount": 0, "createdAt": now, "updatedAt": now, "createdBy": user["address"]}
    await db.api_keys.insert_one(dict(entry))
    await pool_of(request).reload()
    return {"key": {"id": entry["id"], "provider": provider, "label": label, "masked": entry["masked"], "active": True, "monthlyLimit": monthly_limit, "requestCount": 0, "createdAt": now}}


@router.post("/admin/api-keys/rotate")
async def rotate_api_key(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may rotate API keys")
    body = await body_of(request)
    secret = body.get("secret").strip() if isinstance(body.get("secret"), str) else ""
    entry = await db.api_keys.find_one({"id": body.get("id")})
    if not entry or len(secret) < 8 or len(secret) > 2048:
        raise api_error(400, "Invalid key or API key id")
    masked = "••••" + secret[-4:]
    await db.api_keys.update_one({"id": entry["id"]}, {"$set": {"encrypted": encrypt(secret), "masked": masked, "requestCount": 0, "successCount": 0, "lastUsedAt": None, "updatedAt": now_ms()}})
    await pool_of(request).reload()
    return {"ok": True, "masked": masked}


@router.post("/admin/api-keys/toggle")
async def toggle_api_key(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may change API key state")
    body = await body_of(request)
    entry = await db.api_keys.find_one({"id": body.get("id")})
    if not entry:
        raise api_error(404, "API key not found")
    active = not bool(entry.get("active", True))
    await db.api_keys.update_one({"id": entry["id"]}, {"$set": {"active": active, "updatedAt": now_ms()}})
    await pool_of(request).reload()
    return {"active": active}


@router.delete("/admin/api-keys/{key_id}")
async def delete_api_key(key_id: str, request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may remove API keys")
    result = await db.api_keys.delete_one({"id": key_id})
    if not result.deleted_count:
        raise api_error(404, "API key not found")
    await pool_of(request).reload()
    return {"ok": True}


# ─── Deployments & activity ───────────────────────────────────────────────────
@router.get("/admin/state")
async def admin_state(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    deployments = await db.deployments.find({}, {"_id": 0}).sort("createdAt", -1).to_list(500)
    activity = await db.activity.find({}, {"_id": 0}).sort("at", -1).to_list(2000)
    return {"deployments": deployments, "activity": activity}


@router.post("/admin/deployments")
async def save_deployment(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    body = await body_of(request)
    label, token_symbol, network = short_text(body.get("label"), 80), short_text(body.get("tokenSymbol"), 24), body.get("network")
    try:
        token_address, curve_address = normalize(body.get("tokenAddress")), normalize(body.get("curveAddress"))
    except Exception:
        raise api_error(400, "Invalid token or curve address")
    if not label or not token_symbol or not valid_network(network):
        raise api_error(400, "Invalid deployment data")
    existing = await db.deployments.find_one({"id": body.get("id")}, {"_id": 0}) if isinstance(body.get("id"), str) else None
    now = now_ms()
    entry = {"id": existing["id"] if existing else new_id(), "label": label, "tokenSymbol": token_symbol, "network": network, "tokenAddress": token_address, "curveAddress": curve_address, "createdAt": existing["createdAt"] if existing else now, "createdBy": existing["createdBy"] if existing else user["address"], "updatedAt": now}
    await db.deployments.update_one({"id": entry["id"]}, {"$set": entry}, upsert=True)
    return JSONResponse({"deployment": entry}, status_code=200 if existing else 201)


@router.post("/admin/activity")
async def save_activity(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    body = await body_of(request)
    action, state_name, network = short_text(body.get("action"), 120), body.get("state"), body.get("network")
    tx_hash = body.get("hash").strip() if isinstance(body.get("hash"), str) else ""
    deployment_id = body.get("deploymentId") if isinstance(body.get("deploymentId"), str) else ""
    if not action or state_name not in ("pending", "confirmed", "failed") or not valid_network(network) or len(tx_hash) > 132:
        raise api_error(400, "Invalid activity data")
    existing = await db.activity.find_one({"id": body.get("id"), "actor": user["address"]}, {"_id": 0}) if isinstance(body.get("id"), str) else None
    now = now_ms()
    entry = {"id": existing["id"] if existing else new_id(), "action": action, "state": state_name, "network": network, "hash": tx_hash, "deploymentId": deployment_id, "actor": user["address"], "at": existing["at"] if existing else now, "updatedAt": now}
    await db.activity.update_one({"id": entry["id"]}, {"$set": entry}, upsert=True)
    return JSONResponse({"activity": entry}, status_code=200 if existing else 201)


# ─── Public state ─────────────────────────────────────────────────────────────
@router.get("/public/tape")
async def public_tape(request: Request):
    db = db_of(request)
    deployments = {d["id"]: d for d in await db.deployments.find({}, {"_id": 0}).to_list(500)}
    activity = await db.activity.find({"state": "confirmed"}, {"_id": 0}).sort("at", -1).to_list(50)
    result = []
    for item in activity:
        deployment = deployments.get(item.get("deploymentId"))
        result.append({"id": item["id"], "action": item["action"], "network": item["network"], "hash": item.get("hash") or None, "at": item["at"], "deployment": {"label": deployment["label"], "tokenSymbol": deployment["tokenSymbol"], "tokenAddress": deployment["tokenAddress"], "curveAddress": deployment["curveAddress"]} if deployment else None})
    return {"activity": result}


@router.get("/public/state")
async def public_state(request: Request):
    db = db_of(request)
    deployments = await db.deployments.find({"network": "mainnet"}, {"_id": 0}).to_list(500)
    confirmed = await db.activity.count_documents({"state": "confirmed"}) > 0
    return {"sale": {"live": False, "source": "admin-verified-deployments"}, "deployments": [{"id": d["id"], "label": d["label"], "tokenSymbol": d["tokenSymbol"], "network": d["network"], "tokenAddress": d["tokenAddress"], "curveAddress": d["curveAddress"], "updatedAt": d["updatedAt"]} for d in deployments], "activity": {"confirmed": confirmed}}
