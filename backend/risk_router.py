"""Intelligence (risk) API — wallet early access, queued analyses, history, SSE. Port of serve-app.js + queue runtime."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from core import (OWNER_ADDRESS, RISK_COOKIE, api_error, client_ip, host_of, issue_session, new_id, normalize, now_ms, privacy_hash, recover_signer, require_admin, risk_address, risk_session, set_cookie)
from creator_service import CreatorService
from risk_engine import RiskError, analyse_risk

router = APIRouter(prefix="/api")
logger = logging.getLogger("risk")

ACCESS_LIMIT = 3
ACCESS_WINDOW_MS = 60 * 60 * 1000
REPORT_CACHE_MS = 10 * 60 * 1000
RISK_SESSION_MS = 24 * 60 * 60 * 1000
risk_challenges: dict[str, dict] = {}
running_jobs: dict[str, asyncio.Task] = {}
sse_clients = {"active": 0, "total": 0}


def db_of(request: Request):
    return request.app.state.db


async def body_of(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        raise api_error(400, "Invalid JSON")
    return data if isinstance(data, dict) else {}


def identity_of(request: Request, user):
    return {"wallet": privacy_hash(user["address"]), "ip": privacy_hash(client_ip(request))}


# ─── access limiter (3 analyses / hour per wallet or IP) ──────────────────────
async def inspect_access(db, identity):
    now = now_ms()
    await db.risk_access_events.delete_many({"at": {"$lte": now - ACCESS_WINDOW_MS}})
    matching = await db.risk_access_events.find({"$or": [{"wallet": identity["wallet"]}, {"ip": identity["ip"]}]}, {"_id": 0}).sort("at", 1).to_list(1000)
    reset_at = matching[0]["at"] + ACCESS_WINDOW_MS if matching else None
    used = len(matching)
    return {"allowed": used < ACCESS_LIMIT, "used": used, "limit": ACCESS_LIMIT, "remaining": max(0, ACCESS_LIMIT - used), "resetAt": reset_at}


async def consume_access(db, identity):
    state = await inspect_access(db, identity)
    if not state["allowed"]:
        return state
    now = now_ms()
    await db.risk_access_events.insert_one({**identity, "at": now})
    return {**state, "used": state["used"] + 1, "remaining": state["remaining"] - 1, "resetAt": state["resetAt"] or now + ACCESS_WINDOW_MS}


# ─── wallet early access ──────────────────────────────────────────────────────
@router.get("/risk/access/me")
async def access_me(request: Request):
    db = db_of(request)
    user = await risk_session(db, request)
    if not user:
        return {"connected": False, "access": {"limit": ACCESS_LIMIT, "remaining": ACCESS_LIMIT}}
    return {"connected": True, "address": user["address"], "access": await inspect_access(db, identity_of(request, user))}


@router.post("/risk/access/nonce")
async def access_nonce(request: Request):
    body = await body_of(request)
    try:
        account = normalize(body.get("address"))
    except Exception:
        raise api_error(400, "Connect a valid EVM wallet to continue.")
    challenge_id, nonce = new_id(), new_id()
    issued = datetime.now(timezone.utc).isoformat()
    message = f"Robinity Intelligence Early Access\nDomain: {host_of(request)}\nAddress: {account}\nNonce: {nonce}\nIssued At: {issued}\nPurpose: Connect this wallet for analysis access. This signature does not authorize a transaction."
    risk_challenges[challenge_id] = {"account": account, "message": message, "expires": now_ms() + 5 * 60 * 1000}
    return {"challengeId": challenge_id, "message": message}


@router.post("/risk/access/verify")
async def access_verify(request: Request):
    body = await body_of(request)
    challenge = risk_challenges.pop(body.get("challengeId") or "", None)
    if not challenge or challenge["expires"] < now_ms():
        raise api_error(401, "Connection request expired. Please connect again.")
    try:
        signer = recover_signer(challenge["message"], body.get("signature"))
    except Exception:
        raise api_error(401, "The wallet signature could not be verified.")
    if signer != challenge["account"]:
        raise api_error(401, "The signature does not match the connected wallet.")
    db = db_of(request)
    token = await issue_session(db, "risk_sessions", signer, RISK_SESSION_MS)
    identity = {"wallet": privacy_hash(signer), "ip": privacy_hash(client_ip(request))}
    response = JSONResponse({"connected": True, "address": signer, "access": await inspect_access(db, identity)})
    set_cookie(response, RISK_COOKIE, token, 86400)
    return response


@router.post("/risk/access/logout")
async def access_logout(request: Request):
    token = request.cookies.get(RISK_COOKIE)
    if token:
        await db_of(request).risk_sessions.delete_one({"token": token})
    response = JSONResponse({"ok": True})
    response.delete_cookie(RISK_COOKIE, path="/")
    return response


# ─── legacy endpoints ─────────────────────────────────────────────────────────
@router.post("/risk/creator-analysis")
@router.post("/risk/token-icons")
@router.post("/risk/analyze")
async def legacy_analysis():
    raise api_error(410, "Use the queued analysis endpoint.")


# ─── job runtime ──────────────────────────────────────────────────────────────
def public_job(job, access=None):
    payload = {"jobId": job["id"], "status": job["status"], "progress": job.get("progress", 0), "stage": job.get("stage"), "chain": job["chain"], "address": job["address"], "createdAt": job["createdAt"], "updatedAt": job["updatedAt"]}
    if job["status"] == "completed" and job.get("report"):
        payload["report"] = job["report"]
    if job["status"] == "failed":
        payload["error"] = job.get("error") or "Analysis could not be completed."
    if access is not None:
        payload["access"] = access
    elif job.get("access") is not None:
        payload["access"] = job["access"]
    return payload


async def run_job(app, job_id):
    db, pool, creator = app.state.db, app.state.key_pool, app.state.creator_service
    job = await db.risk_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        return

    async def progress(stage, percent):
        await db.risk_jobs.update_one({"id": job_id}, {"$set": {"status": "running", "stage": stage, "progress": percent, "updatedAt": now_ms()}})

    try:
        await progress("Checking token", 5)
        report = await analyse_risk(pool, job["chain"], job["address"], progress)
        await progress("Creator intelligence", 70)
        insights = None
        try:
            insights = await asyncio.wait_for(creator.enrich(report), timeout=120)
        except Exception as error:
            logger.warning("creator enrichment failed: %s", error)
        report["insights"] = insights
        await db.risk_reports.insert_one({"id": report["id"], "chain": job["chain"], "address": job["address"], "walletHash": job["walletHash"], "analyzedAt": report["analyzedAt"], "report": report})
        await db.risk_jobs.update_one({"id": job_id}, {"$set": {"status": "completed", "stage": "Completed", "progress": 100, "report": report, "completedAt": now_ms(), "updatedAt": now_ms()}})
    except RiskError as error:
        await db.risk_jobs.update_one({"id": job_id}, {"$set": {"status": "failed", "error": str(error), "updatedAt": now_ms()}})
    except Exception as error:
        logger.exception("analysis failed")
        await db.risk_jobs.update_one({"id": job_id}, {"$set": {"status": "failed", "error": "Analysis failed: " + error.__class__.__name__, "updatedAt": now_ms()}})
    finally:
        running_jobs.pop(job_id, None)


async def cached_report(db, chain, asset):
    doc = await db.risk_reports.find_one({"chain": chain, "address": asset, "analyzedAt": {"$gt": now_ms() - REPORT_CACHE_MS}}, {"_id": 0}, sort=[("analyzedAt", -1)])
    return doc["report"] if doc else None


@router.post("/risk/analyses")
async def submit_analysis(request: Request):
    db = db_of(request)
    user = await risk_session(db, request)
    if not user:
        raise api_error(401, "Connect your wallet to use early access.")
    body = await body_of(request)
    chain = body.get("chain")
    asset = risk_address(chain, body.get("address"))
    if not asset:
        raise api_error(400, "Invalid token address or network.")
    identity = identity_of(request, user)
    wallet_hash = identity["wallet"]

    # 1) fresh cached report → no quota consumed
    report = await cached_report(db, chain, asset)
    if report:
        report = {**report, "cached": True, "freshness": "cached"}
        await db.risk_reports.update_one({"id": report["id"], "walletHash": wallet_hash}, {"$setOnInsert": {"id": report["id"], "chain": chain, "address": asset, "walletHash": wallet_hash, "analyzedAt": report["analyzedAt"], "report": report}}, upsert=True)
        return {"status": "completed", "report": report, "access": await inspect_access(db, identity)}

    # 2) active job for the same asset by the same wallet → attach
    active = await db.risk_jobs.find_one({"chain": chain, "address": asset, "walletHash": wallet_hash, "status": {"$in": ["queued", "running"]}}, {"_id": 0})
    if active:
        return JSONResponse(public_job(active), status_code=202)

    # 3) quota check & new job
    access = await inspect_access(db, identity)
    if not access["allowed"]:
        return JSONResponse({"error": "Early access currently allows up to 3 analyses per hour.", "access": access}, status_code=429)
    access = await consume_access(db, identity)
    now = now_ms()
    job = {"id": new_id(), "chain": chain, "address": asset, "walletHash": wallet_hash, "status": "queued", "stage": "Queued", "progress": 0, "access": access, "createdAt": now, "updatedAt": now}
    await db.risk_jobs.insert_one(dict(job))
    running_jobs[job["id"]] = asyncio.get_running_loop().create_task(run_job(request.app, job["id"]))
    return JSONResponse(public_job(job), status_code=202)


@router.get("/risk/analyses/{job_id}")
async def analysis_status(job_id: str, request: Request):
    db = db_of(request)
    user = await risk_session(db, request)
    if not user:
        raise api_error(401, "Connect your wallet to view analysis status.")
    job = await db.risk_jobs.find_one({"id": job_id, "walletHash": privacy_hash(user["address"])}, {"_id": 0})
    if not job:
        raise api_error(404, "Analysis not found.")
    return public_job(job)


@router.get("/risk/analyses/{job_id}/events")
async def analysis_events(job_id: str, request: Request):
    db = db_of(request)
    user = await risk_session(db, request)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    wallet_hash = privacy_hash(user["address"])
    job = await db.risk_jobs.find_one({"id": job_id, "walletHash": wallet_hash}, {"_id": 0})
    if not job:
        return JSONResponse({"error": "Access denied or job not found"}, status_code=403)

    async def stream():
        sse_clients["active"] += 1
        sse_clients["total"] += 1
        try:
            last = None
            for _ in range(600):
                current = await db.risk_jobs.find_one({"id": job_id}, {"_id": 0})
                if not current:
                    break
                snapshot = json.dumps(public_job(current))
                if snapshot != last:
                    yield f"event: progress\ndata: {snapshot}\n\n"
                    last = snapshot
                if current["status"] in ("completed", "failed"):
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(1)
        finally:
            sse_clients["active"] -= 1
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/risk/history")
@router.get("/risk/recent")
async def analysis_history(request: Request):
    db = db_of(request)
    user = await risk_session(db, request)
    if not user:
        raise api_error(401, "Connect your wallet to view analysis history.")
    docs = await db.risk_reports.find({"walletHash": privacy_hash(user["address"])}, {"_id": 0, "report": 1}).sort("analyzedAt", -1).to_list(100)
    return {"reports": [doc["report"] for doc in docs]}


# ─── admin queue operations ───────────────────────────────────────────────────
@router.post("/admin/queue/refresh")
async def queue_refresh(request: Request):
    db = db_of(request)
    user = await require_admin(db, request)
    if user["address"] != OWNER_ADDRESS:
        raise api_error(403, "Only the owner wallet may refresh cache")
    body = await body_of(request)
    chain = body.get("chain")
    asset = risk_address(chain, body.get("address"))
    if not asset:
        raise api_error(400, "Invalid token address or network.")
    await db.risk_reports.update_many({"chain": chain, "address": asset}, {"$set": {"analyzedAt": 0}})
    await db.audit_log.insert_one({"actor": user["address"], "action": "cache_invalidate", "target": f"{chain}:{asset}", "at": now_ms()})
    return {"ok": True, "invalidated": f"{chain}:{asset}"}


@router.get("/admin/queue/stats")
async def queue_stats(request: Request):
    db = db_of(request)
    await require_admin(db, request)
    pool = request.app.state.key_pool
    queues = {status: await db.risk_jobs.count_documents({"status": status}) for status in ("queued", "running", "completed", "failed")}
    jobs = []
    for status, count in queues.items():
        oldest = await db.risk_jobs.find_one({"status": status}, {"_id": 0, "createdAt": 1}, sort=[("createdAt", 1)])
        jobs.append({"status": status, "count": count, "oldest": oldest["createdAt"] if oldest else None})
    since = now_ms() - 60 * 60 * 1000
    metrics = []
    for status in ("completed", "failed"):
        rows = await db.risk_jobs.find({"status": status, "updatedAt": {"$gt": since}}, {"_id": 0, "createdAt": 1, "updatedAt": 1}).to_list(1000)
        if rows:
            durations = sorted((r["updatedAt"] - r["createdAt"]) / 1000 for r in rows)
            metrics.append({"status": status, "stage": None, "count": len(rows), "avg_duration_sec": sum(durations) / len(durations), "p95_duration_sec": durations[min(len(durations) - 1, int(len(durations) * 0.95))]})
    providers = {}
    for provider, pool_entries in pool.pools.items():
        cooldowns = [e.get("cooldownUntil") or 0 for e in pool_entries]
        providers[provider] = {"inFlight": sum(e.get("inFlight") or 0 for e in pool_entries), "concurrency": len(pool_entries), "tokens": sum(1 for e in pool_entries if pool.state(e) == "ready"), "cooldownUntil": max(cooldowns) if cooldowns else 0}
    cached = await db.risk_reports.count_documents({"analyzedAt": {"$gt": now_ms() - REPORT_CACHE_MS}})
    return {"queues": queues, "providers": providers, "jobs": jobs, "metrics": metrics, "sse": {"activeConnections": sse_clients["active"], "totalConnections": sse_clients["total"]}, "cache": {"freshReports": cached, "ttlMs": REPORT_CACHE_MS}, "timestamp": now_ms()}
