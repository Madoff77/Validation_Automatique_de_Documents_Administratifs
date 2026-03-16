from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta

from api.models.schemas import DashboardStats
from api.dependencies import require_viewer
from storage.mongo_client import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/stats", tags=["Statistiques"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: dict = Depends(require_viewer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    total_docs = await db.documents.count_documents({})
    processed = await db.documents.count_documents({"status": "processed"})
    pending = await db.documents.count_documents({"status": {"$in": ["pending", "preprocessing", "ocr_done", "classified", "extracted", "validated"]}})
    errors = await db.documents.count_documents({"status": "error"})

    total_suppliers = await db.suppliers.count_documents({})
    active_suppliers = await db.suppliers.count_documents({"compliance_status": {"$ne": "pending"}})

    total_anomalies = await db.anomalies.count_documents({})
    unresolved = await db.anomalies.count_documents({"resolved": False})
    critical = await db.anomalies.count_documents({"resolved": False, "severity": "error"})

    # Documents expirant dans 30 jours (estimation depuis anomalies)
    expiring_soon = await db.anomalies.count_documents({
        "type": {"$in": ["DATE_EXPIRED", "KBIS_EXPIRED", "URSSAF_EXPIRED"]},
        "resolved": False,
    })

    return DashboardStats(
        total_documents=total_docs,
        documents_processed=processed,
        documents_pending=pending,
        documents_error=errors,
        total_suppliers=total_suppliers,
        active_suppliers=active_suppliers,
        total_anomalies=total_anomalies,
        unresolved_anomalies=unresolved,
        critical_anomalies=critical,
        documents_expiring_soon=expiring_soon,
    )
