from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, timezone

from api.models.schemas import AnomalyResponse, AnomalySeverity, AnomalyType, AnomalyResolve
from api.dependencies import require_operator, require_viewer
from storage.mongo_client import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase
from utils.logger import get_logger

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])
logger = get_logger(__name__)


@router.get("", response_model=List[AnomalyResponse])
async def list_anomalies(
    supplier_id: Optional[str] = Query(None),
    severity: Optional[AnomalySeverity] = Query(None),
    anomaly_type: Optional[AnomalyType] = Query(None),
    resolved: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(require_viewer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query = {}
    if supplier_id:
        query["supplier_id"] = supplier_id
    if severity:
        query["severity"] = severity.value
    if anomaly_type:
        query["type"] = anomaly_type.value
    if resolved is not None:
        query["resolved"] = resolved

    anomalies = (
        await db.anomalies.find(query)
        .sort("detected_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    # Enrichir avec le nom du fournisseur
    result = []
    supplier_cache = {}
    for a in anomalies:
        sid = a.get("supplier_id")
        if sid and sid not in supplier_cache:
            s = await db.suppliers.find_one({"supplier_id": sid})
            supplier_cache[sid] = s["name"] if s else None

        result.append(AnomalyResponse(
            anomaly_id=a["anomaly_id"],
            supplier_id=a.get("supplier_id", ""),
            document_id=a.get("document_id"),
            related_document_id=a.get("related_document_id"),
            type=a["type"],
            severity=a["severity"],
            message=a["message"],
            details=a.get("details"),
            detected_at=a["detected_at"],
            resolved=a["resolved"],
            resolved_at=a.get("resolved_at"),
            supplier_name=supplier_cache.get(sid),
        ))

    return result


@router.patch("/{anomaly_id}/resolve", response_model=AnomalyResponse)
async def resolve_anomaly(
    anomaly_id: str,
    body: AnomalyResolve,
    current_user: dict = Depends(require_operator),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    a = await db.anomalies.find_one({"anomaly_id": anomaly_id})
    if not a:
        raise HTTPException(status_code=404, detail="Anomalie introuvable")

    update = {"resolved": body.resolved}
    if body.resolved:
        update["resolved_at"] = datetime.now(timezone.utc)
    else:
        update["resolved_at"] = None

    await db.anomalies.update_one({"anomaly_id": anomaly_id}, {"$set": update})

    # Recalculer le statut conformité du fournisseur
    supplier_id = a.get("supplier_id")
    if supplier_id:
        critical = await db.anomalies.count_documents(
            {"supplier_id": supplier_id, "resolved": False, "severity": "error"}
        )
        warnings = await db.anomalies.count_documents(
            {"supplier_id": supplier_id, "resolved": False, "severity": "warning"}
        )
        if critical > 0:
            cs = "non_compliant"
        elif warnings > 0:
            cs = "warning"
        else:
            cs = "compliant"
        await db.suppliers.update_one({"supplier_id": supplier_id}, {"$set": {"compliance_status": cs}})

    updated = await db.anomalies.find_one({"anomaly_id": anomaly_id})
    logger.info("anomaly_resolved", anomaly_id=anomaly_id, resolved=body.resolved, by=current_user["username"])

    return AnomalyResponse(
        anomaly_id=updated["anomaly_id"],
        supplier_id=updated.get("supplier_id", ""),
        document_id=updated.get("document_id"),
        related_document_id=updated.get("related_document_id"),
        type=updated["type"],
        severity=updated["severity"],
        message=updated["message"],
        details=updated.get("details"),
        detected_at=updated["detected_at"],
        resolved=updated["resolved"],
        resolved_at=updated.get("resolved_at"),
    )


@router.get("/expiring-soon", response_model=List[AnomalyResponse])
async def get_expiring_soon(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(require_viewer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Documents avec date d'expiration dans les N prochains jours."""
    anomalies = await db.anomalies.find({
        "type": {"$in": ["DATE_EXPIRED", "KBIS_EXPIRED", "URSSAF_EXPIRED"]},
        "resolved": False,
    }).sort("detected_at", -1).to_list(500)

    return [
        AnomalyResponse(
            anomaly_id=a["anomaly_id"],
            supplier_id=a.get("supplier_id", ""),
            document_id=a.get("document_id"),
            related_document_id=a.get("related_document_id"),
            type=a["type"],
            severity=a["severity"],
            message=a["message"],
            details=a.get("details"),
            detected_at=a["detected_at"],
            resolved=a["resolved"],
            resolved_at=a.get("resolved_at"),
        )
        for a in anomalies
    ]
