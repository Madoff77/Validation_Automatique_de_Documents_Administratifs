from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import io

from api.models.schemas import (
    DocumentResponse, DocumentListItem, DocumentStatus, PipelineTriggerResponse
)
from api.dependencies import get_current_user, require_admin, require_operator, require_viewer
from storage.mongo_client import get_db
from storage.minio_client import get_minio, upload_file, get_presigned_url
from api.config import settings
from utils.logger import get_logger
import httpx

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=PipelineTriggerResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    supplier_id: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(require_operator),
    db = Depends(get_db),
):
    # Validation type MIME
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Type de fichier non supporté: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Fichier trop grand (max 50MB)")

    # Vérifier que le fournisseur existe
    supplier = await db.suppliers.find_one({"supplier_id": supplier_id})
    if not supplier:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")

    document_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    stored_filename = f"{document_id}.{ext}"
    raw_path = f"{supplier_id}/{stored_filename}"

    # Upload vers MinIO raw zone
    upload_file(settings.minio_bucket_raw, raw_path, content, file.content_type)

    # Créer document MongoDB
    doc = {
        "document_id": document_id,
        "supplier_id": supplier_id,
        "filename": stored_filename,
        "original_filename": file.filename,
        "mime_type": file.content_type,
        "file_size_bytes": len(content),
        "upload_timestamp": now,
        "status": DocumentStatus.PENDING.value,
        "zone": "raw",
        "minio_raw_path": raw_path,
        "minio_clean_path": None,
        "minio_curated_path": None,
        "doc_type": None,
        "classification_confidence": None,
        "ocr_text": None,
        "ocr_quality_score": None,
        "extracted": {},
        "validation": {"status": "pending", "checks": []},
        "airflow_run_id": None,
        "processing_duration_ms": None,
        "error_message": None,
        "uploaded_by": current_user["user_id"],
    }
    await db.documents.insert_one(doc)
    logger.info("document_uploaded", document_id=document_id, filename=file.filename, supplier_id=supplier_id)

    # Déclencher pipeline Airflow
    run_id = await _trigger_airflow_pipeline(document_id)
    if run_id:
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"airflow_run_id": run_id, "status": DocumentStatus.PREPROCESSING.value}}
        )

    return PipelineTriggerResponse(
        document_id=document_id,
        airflow_run_id=run_id or "manual",
        message="Document uploadé et pipeline déclenché",
    )


async def _trigger_airflow_pipeline(document_id: str) -> Optional[str]:
    """Déclenche le DAG Airflow via REST API."""
    run_id = f"doc_{document_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.airflow_url}/api/v1/dags/{settings.airflow_dag_id}/dagRuns",
                auth=(settings.airflow_username, settings.airflow_password),
                json={"dag_run_id": run_id, "conf": {"document_id": document_id}},
                headers={"Content-Type": "application/json"},
            )
            if response.status_code in (200, 409):  # 409 = run_id déjà existant
                logger.info("airflow_triggered", document_id=document_id, run_id=run_id)
                return run_id
            else:
                logger.warning("airflow_trigger_failed", status=response.status_code, body=response.text)
    except Exception as e:
        logger.error("airflow_trigger_error", document_id=document_id, error=str(e))
    return None


@router.get("", response_model=List[DocumentListItem])
async def list_documents(
    supplier_id: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_viewer),
    db = Depends(get_db),
):
    query = {}
    if supplier_id:
        query["supplier_id"] = supplier_id
    if doc_type:
        query["doc_type"] = doc_type
    if status:
        query["status"] = status

    docs = await db.documents.find(query).sort("upload_timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return [
        DocumentListItem(
            document_id=d["document_id"],
            supplier_id=d["supplier_id"],
            original_filename=d["original_filename"],
            doc_type=d.get("doc_type"),
            status=d["status"],
            upload_timestamp=d["upload_timestamp"],
            classification_confidence=d.get("classification_confidence"),
            validation_status=d.get("validation", {}).get("status"),
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(require_viewer),
    db = Depends(get_db),
):
    d = await db.documents.find_one({"document_id": document_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return _doc_to_response(d)


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    zone: str = Query("raw", pattern="^(raw|clean|curated)$"),
    current_user: dict = Depends(require_viewer),
    db = Depends(get_db),
):
    d = await db.documents.find_one({"document_id": document_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document introuvable")

    path_key = f"minio_{zone}_path"
    path = d.get(path_key)
    if not path:
        raise HTTPException(status_code=404, detail=f"Document non disponible en zone {zone}")

    url = get_presigned_url(zone, path.replace(f"{zone}/", "", 1), expires_hours=1)
    if not url:
        raise HTTPException(status_code=500, detail="Impossible de générer l'URL de téléchargement")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(require_admin),
    db = Depends(get_db),
):
    result = await db.documents.delete_one({"document_id": document_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document introuvable")
    await db.anomalies.delete_many({"document_id": document_id})
    logger.info("document_deleted", document_id=document_id)


@router.post("/{document_id}/reprocess", response_model=PipelineTriggerResponse)
async def reprocess_document(
    document_id: str,
    current_user: dict = Depends(require_operator),
    db = Depends(get_db),
):
    d = await db.documents.find_one({"document_id": document_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document introuvable")

    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"status": DocumentStatus.PENDING.value, "error_message": None}}
    )
    run_id = await _trigger_airflow_pipeline(document_id)
    if run_id:
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"airflow_run_id": run_id, "status": DocumentStatus.PREPROCESSING.value}}
        )

    return PipelineTriggerResponse(
        document_id=document_id,
        airflow_run_id=run_id or "manual",
        message="Retraitement déclenché",
    )


def _doc_to_response(d: dict) -> DocumentResponse:
    from api.models.schemas import ExtractedFields, DocumentValidation, ValidationCheck, ValidationStatus
    extracted = d.get("extracted") or {}
    validation = d.get("validation") or {}

    return DocumentResponse(
        document_id=d["document_id"],
        supplier_id=d["supplier_id"],
        filename=d["filename"],
        original_filename=d["original_filename"],
        mime_type=d["mime_type"],
        file_size_bytes=d["file_size_bytes"],
        upload_timestamp=d["upload_timestamp"],
        status=d["status"],
        zone=d.get("zone", "raw"),
        doc_type=d.get("doc_type"),
        classification_confidence=d.get("classification_confidence"),
        ocr_quality_score=d.get("ocr_quality_score"),
        extracted=ExtractedFields(**{k: v for k, v in extracted.items() if k in ExtractedFields.model_fields}) if extracted else None,
        validation=DocumentValidation(
            status=ValidationStatus(validation.get("status", "pending")),
            checks=[ValidationCheck(**c) for c in validation.get("checks", [])],
        ) if validation else None,
        processing_duration_ms=d.get("processing_duration_ms"),
        error_message=d.get("error_message"),
        airflow_run_id=d.get("airflow_run_id"),
    )
