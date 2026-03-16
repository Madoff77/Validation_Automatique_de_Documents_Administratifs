"""
Script de seed — données de démonstration complètes.

Ce script :
  1. Crée les utilisateurs admin/operator/viewer
  2. Crée 3 fournisseurs fictifs cohérents
  3. Upload des documents demo avec anomalies volontaires
  4. Lance le pipeline sur chaque document

Usage : python scripts/seed.py
  Ou via Docker : docker compose exec backend-api python /app/scripts/seed.py
"""

import sys
import os
import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient
from api.config import settings
from api.auth.password import hash_password
from storage.minio_client import ensure_buckets, upload_file
from pipeline.processor import run_full_pipeline
from utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("seed")

# ─────────────────────────────────────────────────────────────
# DONNÉES DEMO FIXÉES (reproducible)
# ─────────────────────────────────────────────────────────────

USERS = [
    {"username": "admin",    "email": "admin@docplatform.local",    "role": "admin",    "password": "admin123",    "full_name": "Admin Système"},
    {"username": "operator", "email": "operator@docplatform.local", "role": "operator", "password": "operator123", "full_name": "Marie Dupont"},
    {"username": "viewer",   "email": "viewer@docplatform.local",   "role": "viewer",   "password": "viewer123",   "full_name": "Jean Martin"},
]

SUPPLIERS = [
    {
        "supplier_id": "sup-001-btp",
        "name": "BTP SOLUTIONS SAS",
        "siret": "73282932000074",
        "siren": "732829320",
        "tva_number": "FR58732829320",
        "address": "15 rue du Bâtiment, 75015 Paris",
        "email": "contact@btp-solutions.fr",
        "phone": "01 23 45 67 89",
    },
    {
        "supplier_id": "sup-002-tech",
        "name": "TECHNO SERVICES EURL",
        "siret": "41816609600069",
        "siren": "418166096",
        "tva_number": "FR22418166096",
        "address": "8 avenue de l'Innovation, 69003 Lyon",
        "email": "admin@techno-services.fr",
        "phone": "04 56 78 90 12",
    },
    {
        "supplier_id": "sup-003-consult",
        "name": "CONSEIL & CO SARL",
        "siret": "55208131766522",
        "siren": "552081317",
        "tva_number": "FR33552081317",
        "address": "22 boulevard des Affaires, 33000 Bordeaux",
        "email": "direction@conseil-co.fr",
        "phone": "05 67 89 01 23",
    },
]


async def seed_users(db):
    print("\n── Utilisateurs ──────────────────────────────")
    for u in USERS:
        existing = await db.users.find_one({"username": u["username"]})
        if existing:
            print(f"  ↳ {u['username']} déjà présent")
            continue
        now = datetime.now(timezone.utc)
        await db.users.insert_one({
            "user_id": str(uuid.uuid4()),
            "username": u["username"],
            "email": u["email"],
            "password_hash": hash_password(u["password"]),
            "role": u["role"],
            "full_name": u["full_name"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        print(f"  ✓ {u['username']} ({u['role']}) — mot de passe: {u['password']}")


async def seed_suppliers(db):
    print("\n── Fournisseurs ──────────────────────────────")
    for s in SUPPLIERS:
        existing = await db.suppliers.find_one({"supplier_id": s["supplier_id"]})
        if existing:
            print(f"  ↳ {s['name']} déjà présent")
            continue
        now = datetime.now(timezone.utc)
        await db.suppliers.insert_one({
            **s,
            "created_at": now,
            "updated_at": now,
            "compliance_status": "pending",
            "notes": "",
        })
        print(f"  ✓ {s['name']} (SIRET: {s['siret']})")


async def seed_documents(db):
    """Créer des documents avec données réalistes et anomalies volontaires."""
    print("\n── Documents de démonstration ────────────────")

    # Importer le générateur
    try:
        sys.path.insert(0, "/app/../data-generator")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../data-generator"))
        from generator import generate_text, _text_to_pdf, text_to_image, degrade_image
        import cv2
        has_generator = True
    except ImportError:
        has_generator = False
        print("  [WARN] Générateur non disponible, seed textuel seulement")

    # Scénarios de documents à créer
    scenarios = [
        # (supplier_id, doc_type, label, anomaly, dégradation, sévérité)
        ("sup-001-btp",    "FACTURE", "Facture BTP normale",          None,       "high_quality", 0.1),
        ("sup-001-btp",    "URSSAF",  "URSSAF BTP expirée",           "expired",  "blur",         0.5),
        ("sup-001-btp",    "KBIS",    "Kbis BTP récent",              None,       "rotation",     0.2),
        ("sup-001-btp",    "RIB",     "RIB BTP",                      None,       "high_quality", 0.1),
        ("sup-002-tech",   "FACTURE", "Facture Tech scan dégradé",    None,       "combined",     0.7),
        ("sup-002-tech",   "DEVIS",   "Devis Tech",                   None,       "noise",        0.3),
        ("sup-002-tech",   "SIRET",   "Attestation SIRET bad",        "bad_siret","blur",         0.4),
        ("sup-002-tech",   "URSSAF",  "URSSAF Tech valide",           None,       "high_quality", 0.1),
        ("sup-003-consult","FACTURE", "Facture Conseil photo mobile", None,       "combined",     0.8),
        ("sup-003-consult","KBIS",    "Kbis Conseil expiré",          "expired",  "low_resolution",0.6),
        ("sup-003-consult","RIB",     "RIB Conseil",                  None,       "high_quality", 0.1),
    ]

    ensure_buckets()
    created = []

    for supplier_id, doc_type, label, anomaly, degradation, severity in scenarios:
        document_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        existing = await db.documents.find_one({
            "supplier_id": supplier_id,
            "doc_type": doc_type,
        })
        if existing:
            print(f"  ↳ {label} déjà présent")
            continue

        # Générer le contenu
        if has_generator:
            text = generate_text(doc_type, anomaly=anomaly)
            file_bytes = None
            mime_type = "application/pdf"
            ext = "pdf"

            # Essayer PDF
            pdf_bytes = _text_to_pdf(text, title=f"{doc_type} — {label}")
            if pdf_bytes:
                file_bytes = pdf_bytes
            else:
                # Fallback image
                img = text_to_image(text)
                img_degraded = degrade_image(img, degradation, severity)
                import io
                from PIL import Image as PILImage
                pil_img = PILImage.fromarray(cv2.cvtColor(img_degraded, cv2.COLOR_BGR2RGB))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=70)
                file_bytes = buf.getvalue()
                mime_type = "image/jpeg"
                ext = "jpg"
        else:
            text = f"Document de type {doc_type} pour fournisseur {supplier_id}"
            file_bytes = text.encode("utf-8")
            mime_type = "text/plain"
            ext = "txt"

        if not file_bytes:
            file_bytes = text.encode("utf-8")
            mime_type = "text/plain"
            ext = "txt"

        filename = f"{document_id}.{ext}"
        raw_path = f"{supplier_id}/{filename}"
        upload_file(settings.minio_bucket_raw, raw_path, file_bytes, mime_type)

        doc = {
            "document_id": document_id,
            "supplier_id": supplier_id,
            "filename": filename,
            "original_filename": f"{label.lower().replace(' ', '_')}.{ext}",
            "mime_type": mime_type,
            "file_size_bytes": len(file_bytes),
            "upload_timestamp": now,
            "status": "pending",
            "zone": "raw",
            "minio_raw_path": raw_path,
            "minio_clean_path": None,
            "minio_curated_path": None,
            "doc_type": None,
            "classification_confidence": None,
            "ocr_text": text,  # Pré-remplir pour accélérer le seed
            "ocr_quality_score": 0.9,
            "extracted": {},
            "validation": {"status": "pending", "checks": []},
            "airflow_run_id": None,
            "processing_duration_ms": None,
            "error_message": None,
            "uploaded_by": "seed",
        }
        await db.documents.insert_one(doc)
        print(f"  ✓ {label} ({doc_type}) → document_id={document_id}")
        created.append(document_id)

    return created


async def run_pipeline_on_seeds(db, document_ids: list):
    """Lancer le pipeline de traitement sur les documents seedés."""
    if not document_ids:
        return

    print(f"\n── Pipeline sur {len(document_ids)} documents ──────────────")
    for doc_id in document_ids:
        try:
            result = run_full_pipeline(doc_id)
            if result["success"]:
                print(f"  ✓ {doc_id[:8]}... traité en {result.get('duration_ms', 0)}ms")
            else:
                print(f"  ⚠ {doc_id[:8]}... erreur : {result.get('error', 'inconnu')}")
        except Exception as e:
            print(f"  ✗ {doc_id[:8]}... exception : {e}")


async def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║         DocPlatform — Seed de démonstration      ║")
    print("╚══════════════════════════════════════════════════╝")

    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db]

    await seed_users(db)
    await seed_suppliers(db)
    doc_ids = await seed_documents(db)
    await run_pipeline_on_seeds(db, doc_ids)

    client.close()

    print("\n╔══════════════════════════════════════════════════╗")
    print("║                   Seed terminé ✓                 ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  URL          : http://localhost:8000/docs        ║")
    print("║  CRM          : http://localhost:5173             ║")
    print("║  Compliance   : http://localhost:5174             ║")
    print("║  Airflow      : http://localhost:8080             ║")
    print("║  MinIO        : http://localhost:9001             ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  admin / admin123      (rôle admin)               ║")
    print("║  operator / operator123 (rôle opérateur)         ║")
    print("║  viewer / viewer123    (rôle lecture seule)       ║")
    print("╚══════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    asyncio.run(main())
