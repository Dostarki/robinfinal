from fastapi import FastAPI, APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()
app.state.db = db

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


@api_router.get("/")
async def root():
    return {"message": "Robinity Intelligence API"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.model_dump())
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    return status_checks


# ─── Routers ──────────────────────────────────────────────────────────────────
from x_router import router as x_router          # noqa: E402  (landing page X plugin)
from admin_router import router as admin_router  # noqa: E402  (wallet+TOTP admin, vault, deployments)
from risk_router import router as risk_router    # noqa: E402  (Intelligence analyses)
from key_pool import KeyPool                     # noqa: E402
from creator_service import CreatorService       # noqa: E402

app.include_router(api_router)
app.include_router(x_router)
app.include_router(admin_router)
app.include_router(risk_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """The original Node server answered `{ error }`; the X router uses `{ detail }`. Serve both keys."""
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        payload = {"error": detail["error"], "detail": detail["error"], **{k: v for k, v in detail.items() if k not in ("error",)}}
    else:
        payload = {"error": str(detail), "detail": detail}
    return JSONResponse(payload, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"error": "Invalid request", "detail": exc.errors()}, status_code=422)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    app.state.key_pool = KeyPool(db)
    await app.state.key_pool.load()
    app.state.creator_service = CreatorService(db, app.state.key_pool)
    await app.state.creator_service.load()
    # Mark jobs that were interrupted by a restart as failed so clients stop polling forever.
    await db.risk_jobs.update_many({"status": {"$in": ["queued", "running"]}}, {"$set": {"status": "failed", "error": "The analysis service restarted. Please try again."}})
    for name, keys in [("risk_jobs", [("id", 1)]), ("risk_reports", [("chain", 1), ("address", 1), ("analyzedAt", -1)]), ("risk_access_events", [("at", 1)]), ("admin_sessions", [("token", 1)]), ("risk_sessions", [("token", 1)]), ("api_keys", [("id", 1)])]:
        try:
            await db[name].create_index(keys)
        except Exception:
            pass
    logger.info("Robinity Intelligence backend ready (owner %s)", os.environ.get("ADMIN_OWNER_ADDRESS"))


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
