"""
Processeur de pipeline principal.

Orchestré par Airflow task par task, mais aussi utilisable en standalone
pour les tests ou le traitement synchrone.

Chaque fonction correspond à une task Airflow.
Les résultats sont persistés en MongoDB après chaque étape.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from storage.mongo_client import get_client
from storage.minio_client import (
    download_file,
    upload_file,
    upload_text,
    upload_json,
    get_minio,
)
from pipeline.ocr.extractor import extract_text
from pipeline.classification.classifier import DocumentClassifier
from pipeline.extraction.field_extractor import extract_fields
from pipeline.validation.validator import validate_document
from api.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_classifier: Optional[DocumentClassifier] = None


def _get_classifier() -> DocumentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = DocumentClassifier()
        _classifier.load()
    return _classifier


def _get_db():
    client = get_client()
    return client[settings.mongo_db]


# ─────────────────────────────────────────────────────────────
# TASK 1 — PREPROCESSING + OCR
# ─────────────────────────────────────────────────────────────

def task_ocr(document_id: str) -> dict:
    """
    Télécharger le fichier brut depuis MinIO raw,
    lancer l'OCR adaptatif, stocker le texte en zone clean.
    Retourne les métadonnées OCR pour XCom Airflow.
    """
    db = _get_db()
    doc = db.documents.find_one({"document_id": document_id})
    if not doc:
        raise ValueError(f"Document {document_id} introuvable en base")

    t_start = time.time()
    logger.info("task_ocr_start", document_id=document_id)

    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"status": "preprocessing"}}
    )

    # Télécharger fichier brut
    raw_path = doc["minio_raw_path"]
    file_bytes = download_file(settings.minio_bucket_raw, raw_path)

    # OCR
    ocr_result = extract_text(file_bytes, doc["mime_type"])

    # Stocker texte OCR en zone clean
    clean_dir = f"{document_id}"
    text_path = f"{clean_dir}/ocr_text.txt"
    meta_path = f"{clean_dir}/ocr_meta.json"

    upload_text(settings.minio_bucket_clean, text_path, ocr_result.text)
    upload_json(
        settings.minio_bucket_clean,
        meta_path,
        json.dumps({
            "method": ocr_result.method,
            "confidence": ocr_result.confidence,
            "page_count": ocr_result.page_count,
            "word_count": ocr_result.word_count,
            "preprocessing_strategy": ocr_result.preprocessing_strategy,
            "ocr_config": ocr_result.ocr_config,
        })
    )

    duration_ms = int((time.time() - t_start) * 1000)

    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {
            "status": "ocr_done",
            "zone": "clean",
            "ocr_text": ocr_result.text,
            "ocr_quality_score": ocr_result.confidence,
            "minio_clean_path": clean_dir,
            "processing_duration_ms": duration_ms,
        }}
    )

    logger.info(
        "task_ocr_done",
        document_id=document_id,
        method=ocr_result.method,
        confidence=round(ocr_result.confidence, 2),
        words=ocr_result.word_count,
        duration_ms=duration_ms,
    )

    return {
        "document_id": document_id,
        "ocr_text": ocr_result.text,
        "ocr_confidence": ocr_result.confidence,
        "ocr_method": ocr_result.method,
    }


# ─────────────────────────────────────────────────────────────
# TASK 2 — CLASSIFICATION
# ─────────────────────────────────────────────────────────────

def task_classify(document_id: str, ocr_text: Optional[str] = None) -> dict:
    """Classifier le type de document."""
    db = _get_db()

    if not ocr_text:
        doc = db.documents.find_one({"document_id": document_id})
        ocr_text = doc.get("ocr_text", "")

    if not ocr_text.strip():
        logger.warning("classify_empty_text", document_id=document_id)
        db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"doc_type": "UNKNOWN", "classification_confidence": 0.0, "status": "classified"}}
        )
        return {"document_id": document_id, "doc_type": "UNKNOWN", "confidence": 0.0}

    classifier = _get_classifier()
    doc_type, confidence, all_probs = classifier.predict(ocr_text)

    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {
            "doc_type": doc_type,
            "classification_confidence": confidence,
            "classification_probabilities": all_probs,
            "status": "classified",
        }}
    )

    logger.info("task_classify_done", document_id=document_id, doc_type=doc_type, confidence=round(confidence, 2))
    return {"document_id": document_id, "doc_type": doc_type, "confidence": confidence}


# ─────────────────────────────────────────────────────────────
# TASK 3 — EXTRACTION CHAMPS
# ─────────────────────────────────────────────────────────────

def task_extract(document_id: str, doc_type: Optional[str] = None, ocr_text: Optional[str] = None) -> dict:
    """Extraire les champs structurés du texte OCR."""
    db = _get_db()
    doc = db.documents.find_one({"document_id": document_id})

    if not ocr_text:
        ocr_text = doc.get("ocr_text", "")
    if not doc_type:
        doc_type = doc.get("doc_type", "UNKNOWN")

    extracted = extract_fields(ocr_text, doc_type)

    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {
            "extracted": extracted,
            "status": "extracted",
        }}
    )

    logger.info(
        "task_extract_done",
        document_id=document_id,
        doc_type=doc_type,
        fields_found=len([v for v in extracted.values() if v is not None]),
    )

    return {"document_id": document_id, "extracted": extracted}


# ─────────────────────────────────────────────────────────────
# TASK 4 — VALIDATION
# ─────────────────────────────────────────────────────────────

def task_validate(document_id: str) -> dict:
    """Valider le document et détecter les anomalies inter-documents."""
    db = _get_db()
    doc = db.documents.find_one({"document_id": document_id})

    supplier_id = doc["supplier_id"]

    # Récupérer les autres documents du même fournisseur (déjà traités)
    sibling_docs = list(db.documents.find({
        "supplier_id": supplier_id,
        "document_id": {"$ne": document_id},
        "status": {"$in": ["extracted", "validated", "processed"]},
    }))

    validation_result, anomalies = validate_document(doc, sibling_docs)

    # Persister anomalies
    for anomaly in anomalies:
        anomaly["anomaly_id"] = str(uuid.uuid4())
        anomaly["detected_at"] = datetime.now(timezone.utc)
        anomaly["resolved"] = False
        db.anomalies.insert_one(anomaly)

    # Mettre à jour statut conformité fournisseur
    unresolved = db.anomalies.count_documents({"supplier_id": supplier_id, "resolved": False})
    critical = db.anomalies.count_documents({"supplier_id": supplier_id, "resolved": False, "severity": "error"})

    if critical > 0:
        compliance_status = "non_compliant"
    elif unresolved > 0:
        compliance_status = "warning"
    else:
        compliance_status = "compliant"

    db.suppliers.update_one(
        {"supplier_id": supplier_id},
        {"$set": {"compliance_status": compliance_status}}
    )

    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {
            "validation": validation_result,
            "status": "validated",
        }}
    )

    logger.info(
        "task_validate_done",
        document_id=document_id,
        validation_status=validation_result["status"],
        anomalies_created=len(anomalies),
    )

    return {
        "document_id": document_id,
        "validation_status": validation_result["status"],
        "anomaly_count": len(anomalies),
    }


# ─────────────────────────────────────────────────────────────
# TASK 5 — FINALISATION (zone curated)
# ─────────────────────────────────────────────────────────────

def task_finalize(document_id: str) -> dict:
    """Stocker les données structurées finales en zone curated."""
    db = _get_db()
    doc = db.documents.find_one({"document_id": document_id})

    curated_path = f"{document_id}/data.json"
    curated_data = {
        "document_id": document_id,
        "supplier_id": doc["supplier_id"],
        "original_filename": doc["original_filename"],
        "doc_type": doc.get("doc_type"),
        "classification_confidence": doc.get("classification_confidence"),
        "extracted": doc.get("extracted", {}),
        "validation": doc.get("validation", {}),
        "ocr_quality_score": doc.get("ocr_quality_score"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    upload_json(
        settings.minio_bucket_curated,
        curated_path,
        json.dumps(curated_data, default=str, ensure_ascii=False, indent=2)
    )

    db.documents.update_one(
        {"document_id": document_id},
        {"$set": {
            "status": "processed",
            "zone": "curated",
            "minio_curated_path": curated_path,
        }}
    )

    logger.info("task_finalize_done", document_id=document_id)
    return {"document_id": document_id, "curated_path": curated_path}


# ─────────────────────────────────────────────────────────────
# PIPELINE COMPLET (hors Airflow — pour tests)
# ─────────────────────────────────────────────────────────────

def run_full_pipeline(document_id: str) -> dict:
    """Exécuter le pipeline complet de façon synchrone (tests, debug)."""
    t_start = time.time()
    logger.info("full_pipeline_start", document_id=document_id)

    try:
        r1 = task_ocr(document_id)
        r2 = task_classify(document_id, ocr_text=r1["ocr_text"])
        r3 = task_extract(document_id, doc_type=r2["doc_type"], ocr_text=r1["ocr_text"])
        r4 = task_validate(document_id)
        r5 = task_finalize(document_id)

        duration = int((time.time() - t_start) * 1000)
        logger.info("full_pipeline_done", document_id=document_id, duration_ms=duration)
        return {"success": True, "document_id": document_id, "duration_ms": duration, **r5}

    except Exception as e:
        db = _get_db()
        db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": "error", "error_message": str(e)}}
        )
        logger.error("full_pipeline_error", document_id=document_id, error=str(e))
        return {"success": False, "document_id": document_id, "error": str(e)}
