from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from api.models.schemas import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    ComplianceStatus, ComplianceOverview
)
from api.dependencies import get_current_user, require_operator, require_viewer
from storage.mongo_client import get_db
from motor.motor_asyncio import AsyncIOMotorDatabase
from utils.logger import get_logger

router = APIRouter(prefix="/suppliers", tags=["Fournisseurs"])
logger = get_logger(__name__)


def _compute_compliance(supplier: dict, anomaly_counts: dict) -> ComplianceStatus:
    total_errors = anomaly_counts.get("error", 0)
    total_warnings = anomaly_counts.get("warning", 0)
    if total_errors > 0:
        return ComplianceStatus.NON_COMPLIANT
    if total_warnings > 0:
        return ComplianceStatus.WARNING
    return ComplianceStatus.COMPLIANT


@router.get("", response_model=List[SupplierResponse])
async def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    compliance_status: Optional[ComplianceStatus] = None,
    current_user: dict = Depends(require_viewer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"siret": {"$regex": search}},
        ]
    if compliance_status:
        query["compliance_status"] = compliance_status.value

    suppliers = await db.suppliers.find(query).skip(skip).limit(limit).to_list(limit)
    result = []
    for s in suppliers:
        doc_count = await db.documents.count_documents({"supplier_id": s["supplier_id"]})
        result.append(SupplierResponse(
            supplier_id=s["supplier_id"],
            name=s["name"],
            siret=s.get("siret"),
            siren=s.get("siren"),
            tva_number=s.get("tva_number"),
            address=s.get("address"),
            email=s.get("email"),
            phone=s.get("phone"),
            notes=s.get("notes"),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            document_count=doc_count,
            compliance_status=ComplianceStatus(s.get("compliance_status", "pending")),
        ))
    return result


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SupplierCreate,
    current_user: dict = Depends(require_operator),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if body.siret:
        existing = await db.suppliers.find_one({"siret": body.siret})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SIRET déjà enregistré")

    supplier_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        "supplier_id": supplier_id,
        "name": body.name,
        "siret": body.siret,
        "siren": body.siren or (body.siret[:9] if body.siret else None),
        "tva_number": body.tva_number,
        "address": body.address,
        "email": body.email,
        "phone": body.phone,
        "notes": body.notes,
        "created_at": now,
        "updated_at": now,
        "compliance_status": ComplianceStatus.PENDING.value,
    }
    await db.suppliers.insert_one(doc)
    logger.info("supplier_created", supplier_id=supplier_id, name=body.name)

    return SupplierResponse(
        supplier_id=supplier_id,
        name=body.name,
        siret=body.siret,
        siren=doc["siren"],
        tva_number=body.tva_number,
        address=body.address,
        email=body.email,
        phone=body.phone,
        notes=body.notes,
        created_at=now,
        updated_at=now,
        document_count=0,
        compliance_status=ComplianceStatus.PENDING,
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: str,
    current_user: dict = Depends(require_viewer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    s = await db.suppliers.find_one({"supplier_id": supplier_id})
    if not s:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")

    doc_count = await db.documents.count_documents({"supplier_id": supplier_id})
    return SupplierResponse(
        supplier_id=s["supplier_id"],
        name=s["name"],
        siret=s.get("siret"),
        siren=s.get("siren"),
        tva_number=s.get("tva_number"),
        address=s.get("address"),
        email=s.get("email"),
        phone=s.get("phone"),
        notes=s.get("notes"),
        created_at=s["created_at"],
        updated_at=s["updated_at"],
        document_count=doc_count,
        compliance_status=ComplianceStatus(s.get("compliance_status", "pending")),
    )


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: str,
    body: SupplierUpdate,
    current_user: dict = Depends(require_operator),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    s = await db.suppliers.find_one({"supplier_id": supplier_id})
    if not s:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await db.suppliers.update_one({"supplier_id": supplier_id}, {"$set": update_data})

    updated = await db.suppliers.find_one({"supplier_id": supplier_id})
    doc_count = await db.documents.count_documents({"supplier_id": supplier_id})
    return SupplierResponse(
        supplier_id=updated["supplier_id"],
        name=updated["name"],
        siret=updated.get("siret"),
        siren=updated.get("siren"),
        tva_number=updated.get("tva_number"),
        address=updated.get("address"),
        email=updated.get("email"),
        phone=updated.get("phone"),
        notes=updated.get("notes"),
        created_at=updated["created_at"],
        updated_at=updated["updated_at"],
        document_count=doc_count,
        compliance_status=ComplianceStatus(updated.get("compliance_status", "pending")),
    )


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: str,
    current_user: dict = Depends(require_operator),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    result = await db.suppliers.delete_one({"supplier_id": supplier_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    logger.info("supplier_deleted", supplier_id=supplier_id)


@router.get("/{supplier_id}/compliance", response_model=ComplianceOverview)
async def get_supplier_compliance(
    supplier_id: str,
    current_user: dict = Depends(require_viewer),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    s = await db.suppliers.find_one({"supplier_id": supplier_id})
    if not s:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")

    from datetime import date
    today = datetime.now(timezone.utc)

    anomalies = await db.anomalies.find({"supplier_id": supplier_id, "resolved": False}).to_list(1000)
    critical = sum(1 for a in anomalies if a["severity"] == "error")

    # Documents expirés ou expirant dans 30 jours
    docs = await db.documents.find({"supplier_id": supplier_id}).to_list(1000)
    expired = 0
    expiring_soon = 0
    for doc in docs:
        exp = doc.get("extracted", {})
        if isinstance(exp, dict):
            exp_date = exp.get("date_expiration")
            if exp_date:
                try:
                    from dateutil.parser import parse
                    d = parse(exp_date)
                    if d < today:
                        expired += 1
                    elif (d - today).days <= 30:
                        expiring_soon += 1
                except Exception:
                    pass

    return ComplianceOverview(
        supplier_id=supplier_id,
        supplier_name=s["name"],
        compliance_status=ComplianceStatus(s.get("compliance_status", "pending")),
        anomaly_count=len(anomalies),
        critical_anomalies=critical,
        expired_documents=expired,
        expiring_soon=expiring_soon,
        last_check=today,
    )
