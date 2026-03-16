"""
DocPlatform API — Point d'entrée FastAPI

Routes exposées :
  GET  /health                     → healthcheck
  POST /auth/login                 → JWT login
  POST /auth/refresh               → refresh token
  POST /auth/logout                → logout
  GET  /auth/me                    → profil courant
  POST /auth/register              → créer utilisateur (admin)

  GET/POST /suppliers              → liste / créer fournisseur
  GET/PUT/DELETE /suppliers/{id}   → détail / modifier / supprimer
  GET /suppliers/{id}/compliance   → vue conformité fournisseur

  POST /documents/upload           → upload document + déclenchement pipeline
  GET  /documents                  → liste documents (filtrés)
  GET  /documents/{id}             → détail document
  GET  /documents/{id}/download    → télécharger (presigned URL)
  POST /documents/{id}/reprocess   → relancer pipeline
  DELETE /documents/{id}           → supprimer

  GET  /anomalies                  → liste anomalies
  PATCH /anomalies/{id}/resolve    → résoudre anomalie

  GET  /stats/dashboard            → stats globales
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import time

from api.config import settings
from api.routes import auth, documents, suppliers, anomalies, stats
from storage.mongo_client import connect as mongo_connect, disconnect as mongo_disconnect
from storage.minio_client import ensure_buckets
from utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# LIFESPAN (startup / shutdown)
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_startup", version=settings.app_version, env=settings.environment)

    await mongo_connect()

    try:
        ensure_buckets()
    except Exception as e:
        logger.warning("minio_init_failed", error=str(e))

    await _ensure_default_admin()

    logger.info("api_ready")
    yield

    await mongo_disconnect()
    logger.info("api_shutdown")


async def _ensure_default_admin():
    """Créer l'admin par défaut au premier démarrage."""
    from storage.mongo_client import get_db
    from api.auth.password import hash_password
    from datetime import datetime, timezone
    import uuid

    db = await get_db()
    existing = await db.users.find_one({"role": "admin"})
    if existing:
        return

    admin_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.users.insert_one({
        "user_id": admin_id,
        "username": "admin",
        "email": "admin@docplatform.local",
        "password_hash": hash_password("admin123"),
        "role": "admin",
        "full_name": "Administrateur",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })
    logger.info("default_admin_created", username="admin")


# ─────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Plateforme de traitement intelligent de documents administratifs",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Middlewares ────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    t_start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - t_start) * 1000)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


# ── Routes ─────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(suppliers.router)
app.include_router(anomalies.router)
app.include_router(stats.router)


@app.get("/health", tags=["Système"])
async def health_check():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
    }
