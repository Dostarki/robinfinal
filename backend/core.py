"""Shared helpers for the Robinity Intelligence backend (port of scripts/serve-app.js)."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address
from fastapi import HTTPException, Request

OWNER_ADDRESS = os.environ.get("ADMIN_OWNER_ADDRESS", "0xb2F6409cF259B8820a733548f575D5B217ea4cCE").lower()
RISK_CHAINS = {"solana": None, "ethereum": "1", "bsc": "56", "base": "8453", "arbitrum": "42161", "optimism": "10", "polygon": "137"}
ADMIN_COOKIE = "admin_session"
RISK_COOKIE = "risk_session"

_http: Optional[httpx.AsyncClient] = None


def http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=False, headers={"User-Agent": "Robinity-Risk/1.0"})
    return _http


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return secrets.token_urlsafe(32)


def env(name, default=None):
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


# ─── master key & encryption ────────────────────────────────────────────────
_master_key: Optional[bytes] = None


def master_key() -> bytes:
    global _master_key
    if _master_key is None:
        configured = env("ADMIN_AUTH_MASTER_KEY")
        if configured:
            _master_key = hashlib.sha256(configured.encode()).digest()
        else:
            path = os.path.join(os.path.dirname(__file__), "data", "admin-auth.key")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path):
                with open(path, "wb") as handle:
                    handle.write(secrets.token_bytes(32))
                os.chmod(path, 0o600)
            with open(path, "rb") as handle:
                _master_key = handle.read()
    return _master_key


def encrypt(value: str) -> dict:
    iv = secrets.token_bytes(12)
    sealed = AESGCM(master_key()).encrypt(iv, value.encode(), None)
    ciphertext, tag = sealed[:-16], sealed[-16:]
    return {"iv": base64.b64encode(iv).decode(), "tag": base64.b64encode(tag).decode(), "ciphertext": base64.b64encode(ciphertext).decode()}


def decrypt(value: dict) -> str:
    iv = base64.b64decode(value["iv"])
    sealed = base64.b64decode(value["ciphertext"]) + base64.b64decode(value["tag"])
    return AESGCM(master_key()).decrypt(iv, sealed, None).decode()


def privacy_hash(value: str) -> str:
    digest = hmac.new(master_key(), str(value).encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ─── addresses & signatures ─────────────────────────────────────────────────
def normalize(address) -> str:
    """Validate an EVM address and return it lower-cased. Raises ValueError."""
    if not isinstance(address, str):
        raise ValueError("Invalid address")
    return to_checksum_address(address.strip()).lower()


def recover_signer(message: str, signature: str) -> str:
    return Account.recover_message(encode_defunct(text=message), signature=signature).lower()


def risk_address(chain, address):
    import re
    if chain not in RISK_CHAINS or not isinstance(address, str):
        return None
    value = address.strip()
    if chain == "solana":
        return value if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", value) else None
    try:
        return normalize(value)
    except Exception:
        return None


def short_text(value, limit):
    if isinstance(value, str) and 0 < len(value.strip()) <= limit:
        return value.strip()
    return None


def valid_network(value):
    return value in ("mainnet", "testnet")


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def host_of(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host") or "robinity"


# ─── sessions (Mongo-backed) ────────────────────────────────────────────────
async def issue_session(db, collection: str, address: str, ttl_ms: int) -> str:
    token = new_id()
    await db[collection].insert_one({"token": token, "address": address, "expires": now_ms() + ttl_ms})
    return token


async def read_session(db, collection: str, request: Request, cookie: str):
    token = request.cookies.get(cookie)
    if not token:
        return None
    item = await db[collection].find_one({"token": token}, {"_id": 0})
    if not item or item["expires"] < now_ms():
        if item:
            await db[collection].delete_one({"token": token})
        return None
    return item


async def admin_session(db, request: Request):
    return await read_session(db, "admin_sessions", request, ADMIN_COOKIE)


async def require_admin(db, request: Request):
    item = await admin_session(db, request)
    if not item:
        raise HTTPException(401, "Authentication required")
    return item


async def risk_session(db, request: Request):
    return await read_session(db, "risk_sessions", request, RISK_COOKIE)


def set_cookie(response, name, token, max_age):
    response.set_cookie(name, token, max_age=max_age, httponly=True, secure=True, samesite="lax", path="/")


def api_error(status: int, message: str) -> HTTPException:
    """Errors in the original server are `{ error: "..." }` – frontend reads `data.error`."""
    return HTTPException(status_code=status, detail={"error": message})
