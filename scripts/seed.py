"""
Script de seed — données de démonstration complètes.

Ce script :
  1. Crée les utilisateurs admin/operator/viewer
  2. Crée des fournisseurs depuis l'API SIRENE (données réelles)
  3. Génère plusieurs documents par fournisseur (FACTURE, KBIS, URSSAF, RIB, DEVIS, SIRET)
  4. Lance le pipeline sur chaque document

Usage : python scripts/seed.py
  Ou via Docker : docker compose exec backend-api sh -c "python /app/scripts/seed.py"
"""

import sys
import os
import asyncio
import uuid
import random
import time
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motor.motor_asyncio import AsyncIOMotorClient
from api.config import settings
from api.auth.password import hash_password
from storage.minio_client import ensure_buckets, upload_file
from utils.logger import configure_logging, get_logger

configure_logging()
logger = get_logger("seed")

try:
    sys.path.insert(0, "/app/data-generator")
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../data-generator"))
    from generator import (
        fetch_sirene_companies,
        _siren_to_tva,
        generate_text,
        _text_to_pdf,
        text_to_image,
        degrade_image,
    )
    import cv2
    has_generator = True
except ImportError as e:
    has_generator = False
    logger.warning(f"Générateur de données non disponible : {e}.")


USERS = [
    {"username": "admin",    "email": "admin@docplatform.local",    "role": "admin",    "password": "admin123",    "full_name": "Admin Système"},
    {"username": "operator", "email": "operator@docplatform.local", "role": "operator", "password": "operator123", "full_name": "Marie Dupont"},
    {"username": "viewer",   "email": "viewer@docplatform.local",   "role": "viewer",   "password": "viewer123",   "full_name": "Jean Martin"},
]

# Schéma de documents à générer par fournisseur.
# Format : (doc_type, anomaly, degradation, severity)
# Les anomalies sont attribuées à certains fournisseurs selon leur index.
DOC_SCHEMAS = [
    ("FACTURE", None,       "high_quality",   0.1),
    # ("FACTURE", None,       "combined",       0.6),
    ("DEVIS",   None,       "noise",          0.3),
    # ("KBIS",    None,       "rotation",       0.2),
    ("URSSAF",  None,       "high_quality",   0.1),
    ("RIB",     None,       "high_quality",   0.1),
]

# Schéma alternatif avec anomalies (pour 1 fournisseur sur 3)
DOC_SCHEMAS_WITH_ANOMALIES = [
    ("FACTURE", "bad_siret", "blur",           0.4),
    # ("DEVIS",   None,        "noise",          0.3),
    ("KBIS",    "expired",   "low_resolution", 0.6),
    ("URSSAF",  "expired",   "blur",           0.5),
    # ("SIRET",   "bad_siret", "combined",       0.5),
    ("RIB",     None,        "high_quality",   0.1),
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
        print(f"  [OK] {u['username']} ({u['role']})")


async def seed_suppliers(db, real_companies: list) -> list:
    """Crée un fournisseur par entreprise SIRENE. Retourne la liste des supplier_ids créés ou existants."""
    print(f"\n── Fournisseurs ({len(real_companies)} entreprises) ────────────")
    supplier_ids = []

    for i, company in enumerate(real_companies):
        siren = company.get("siren", "")
        siret = company.get("siret", "")
        if not siren or not siret:
            continue

        supplier_id = f"sup-{siret}"
        supplier_ids.append(supplier_id)

        existing = await db.suppliers.find_one({"supplier_id": supplier_id})
        if existing:
            print(f"  ↳ {company['name']} déjà présent")
            continue

        now = datetime.now(timezone.utc)
        await db.suppliers.insert_one({
            "supplier_id": supplier_id,
            "name": company["name"],
            "siret": siret,
            "siren": siren,
            "tva_number": _siren_to_tva(siren),
            "address": company.get("address", ""),
            "email": f"contact@{siret[:6].lower()}.fr",
            "phone": "01 00 00 00 00",
            "compliance_status": "pending",
            "notes": "",
            "created_at": now,
            "updated_at": now,
        })
        print(f"  [OK] {company['name']} (SIRET: {siret})")

    return supplier_ids


async def seed_documents(db, supplier_ids: list) -> list:
    """Génère des documents pour chaque fournisseur. Retourne les document_ids créés."""
    print(f"\n── Documents ({len(supplier_ids)} fournisseurs) ──────────────")
    ensure_buckets()
    created = []

    for idx, supplier_id in enumerate(supplier_ids):
        # 1 fournisseur sur 3 reçoit des documents avec anomalies
        schemas = DOC_SCHEMAS_WITH_ANOMALIES if idx % 3 == 2 else DOC_SCHEMAS

        for doc_type, anomaly, degradation, severity in schemas:
            seed_key = f"{supplier_id}:{doc_type}:{anomaly or 'ok'}"
            existing = await db.documents.find_one({"seed_key": seed_key})
            if existing:
                continue

            document_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Générer le contenu du document
            text = generate_text(doc_type, anomaly=anomaly)
            file_bytes = None
            mime_type = "application/pdf"
            ext = "pdf"

            # 30% PDF natif, 70% image dégradée
            if random.random() < 0.30:
                pdf_bytes = _text_to_pdf(text, title=f"{doc_type}")
                if pdf_bytes:
                    file_bytes = pdf_bytes

            if not file_bytes:
                import io
                from PIL import Image as PILImage
                img = text_to_image(text)
                img_degraded = degrade_image(img, degradation, severity)
                pil_img = PILImage.fromarray(cv2.cvtColor(img_degraded, cv2.COLOR_BGR2RGB))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=70)
                file_bytes = buf.getvalue()
                mime_type = "image/jpeg"
                ext = "jpg"

            filename = f"{document_id}.{ext}"
            raw_path = f"{supplier_id}/{filename}"
            upload_file(settings.minio_bucket_raw, raw_path, file_bytes, mime_type)

            label = f"{doc_type.lower()}{'_' + anomaly if anomaly else ''}"
            doc = {
                "document_id": document_id,
                "supplier_id": supplier_id,
                "seed_key": seed_key,
                "filename": filename,
                "original_filename": f"{label}.{ext}",
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
                "ocr_text": text,
                "ocr_quality_score": None,  # sera écrasé par task_ocr lors du pipeline
                "extracted": {},
                "validation": {"status": "pending", "checks": []},
                "airflow_run_id": None,
                "processing_duration_ms": None,
                "error_message": None,
                "uploaded_by": "seed",
            }
            await db.documents.insert_one(doc)
            created.append(document_id)
            anomaly_tag = f" [{anomaly}]" if anomaly else ""
            print(f"  [OK] {supplier_id[:20]}... — {doc_type}{anomaly_tag} ({ext})")

    return created


# ─────────────────────────────────────────────────────────────
# PIPELINE VIA AIRFLOW
# ─────────────────────────────────────────────────────────────

AIRFLOW_URL      = settings.airflow_url
AIRFLOW_AUTH     = (settings.airflow_username, settings.airflow_password)
DAG_ID           = settings.airflow_dag_id
POLL_INTERVAL_S  = 60   # secondes entre chaque vérification de l'état
MAX_WAIT_S       = 900  # timeout global : 15 minutes


def _airflow_ready() -> bool:
    """Vérifier qu'Airflow répond avant de déclencher les DAGs."""
    try:
        r = requests.get(f"{AIRFLOW_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _trigger_dag(document_id: str) -> str | None:
    """Déclencher un DAG run pour un document. Retourne le dag_run_id ou None."""
    try:
        r = requests.post(
            f"{AIRFLOW_URL}/api/v1/dags/{DAG_ID}/dagRuns",
            json={"conf": {"document_id": document_id}},
            auth=AIRFLOW_AUTH,
            timeout=10,
        )
        if r.status_code in (200, 201):
            return r.json().get("dag_run_id")
        logger.warning("airflow_trigger_failed", document_id=document_id, status=r.status_code, body=r.text[:200])
        return None
    except Exception as e:
        logger.warning("airflow_trigger_error", document_id=document_id, error=str(e))
        return None


def _count_dag_states(run_ids: set[str]) -> dict[str, int]:
    """
    Récupérer les états de tous nos DAG runs en 2 requêtes HTTP (pas une par run).
    On interroge l'endpoint liste avec limit=200 et on filtre sur nos run_ids.
    Retourne {success: n, running: n, failed: n, queued: n}.
    """
    counts = {"success": 0, "running": 0, "failed": 0, "queued": 0}
    try:
        r = requests.get(
            f"{AIRFLOW_URL}/api/v1/dags/{DAG_ID}/dagRuns",
            params={"limit": 200, "order_by": "-execution_date"},
            auth=AIRFLOW_AUTH,
            timeout=10,
        )
        if r.status_code != 200:
            return counts
        for run in r.json().get("dag_runs", []):
            if run["dag_run_id"] in run_ids:
                state = run.get("state", "unknown")
                if state in counts:
                    counts[state] += 1
    except Exception:
        pass
    return counts


async def run_pipeline_on_seeds(db, document_ids: list):
    print(f"\n── Pipeline Airflow sur {len(document_ids)} documents ──────────────")

    # Vérifier qu'Airflow est disponible
    print("  Vérification Airflow...", end=" ", flush=True)
    if not _airflow_ready():
        print("✗ Airflow non disponible")
        print("  → Fallback : pipeline direct (sans Airflow)")
        _run_pipeline_direct(document_ids)
        return
    print("✓")

    # Déclencher un DAG run par document
    print(f"  Déclenchement de {len(document_ids)} DAG runs...")
    run_ids: set[str] = set()

    for doc_id in document_ids:
        run_id = _trigger_dag(doc_id)
        if run_id:
            run_ids.add(run_id)
            print(f"  ✓ {doc_id[:8]}...")
        else:
            print(f"  ✗ {doc_id[:8]}... trigger échoué")
        time.sleep(0.3)  # éviter de saturer l'API Airflow

    triggered = len(run_ids)
    print(f"\n  {triggered}/{len(document_ids)} DAG runs déclenchés")
    print(f"  Suivi en temps réel → http://localhost:8080/dags/{DAG_ID}/grid")

    if not run_ids:
        return

    # ── Polling léger : 2 requêtes HTTP par cycle (pas une par DAG) ──
    print(f"\n  Attente de completion (vérification toutes les {POLL_INTERVAL_S}s)...")
    elapsed = 0

    while elapsed < MAX_WAIT_S:
        counts = _count_dag_states(run_ids)
        in_progress = counts["running"] + counts["queued"]
        print(
            f"  [{elapsed:>4}s]  En cours: {in_progress:>2}"
            f"  |  Succès: {counts['success']:>2}"
            f"  |  Échecs: {counts['failed']:>2}",
            flush=True,
        )
        if in_progress == 0:
            break
        time.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S
    else:
        print(f"\n  ⚠ Timeout atteint ({MAX_WAIT_S}s) — certains documents sont encore en cours")
        counts = _count_dag_states(run_ids)

    print(f"\n  Résultat final : {counts['success']} traités ✓  {counts['failed']} échecs")


def _run_pipeline_direct(document_ids: list):
    """Fallback sans Airflow — pipeline synchrone direct."""
    from pipeline.processor import run_full_pipeline
    ok = err = 0
    for doc_id in document_ids:
        try:
            result = run_full_pipeline(doc_id)
            if result["success"]:
                ok += 1
                print(f"  [OK] {doc_id[:8]}... traité en {result.get('duration_ms', 0)}ms")
            else:
                err += 1
                print(f"  [WARN] {doc_id[:8]}... erreur : {result.get('error', 'inconnu')}")
        except Exception as e:
            err += 1
            print(f"  [ERR] {doc_id[:8]}... exception : {e}")
    print(f"\n  Résultat : {ok} traités OK, {err} erreurs")


async def main():
    if not has_generator:
        print("\nGénérateur de données non disponible.")
        return

    print("╔══════════════════════════════════════════════════╗")
    print("║         DocPlatform — Seed de démonstration      ║")
    print("╚══════════════════════════════════════════════════╝")

    # Récupérer les entreprises depuis l'API SIRENE
    print("\nRécupération des entreprises depuis l'API SIRENE...")
    real_companies = fetch_sirene_companies(n_companies=3)
    if not real_companies:
        print("  [ERR] Impossible de récupérer les données SIRENE. Vérifiez INSEE_API_KEY.")
        return
    print(f"  → {len(real_companies)} entreprises récupérées")

    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db]

    await seed_users(db)
    supplier_ids = await seed_suppliers(db, real_companies)
    doc_ids = await seed_documents(db, supplier_ids)

    if doc_ids:
        print(f"\n  {len(doc_ids)} nouveaux documents créés — lancement du pipeline...")
        await run_pipeline_on_seeds(db, doc_ids)
    else:
        print("\n  Aucun nouveau document à traiter (tout est déjà présent)")

    client.close()

    print("\n╔══════════════════════════════════════════════════╗")
    print("║                   Seed terminé OK                  ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Fournisseurs : {len(supplier_ids):<33}║")
    print(f"║  Docs créés   : {len(doc_ids):<33}║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  CRM        : http://localhost:5173               ║")
    print("║  Compliance : http://localhost:5174               ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  admin / admin123                                 ║")
    print("║  operator / operator123                          ║")
    print("║  viewer / viewer123                               ║")
    print("╚══════════════════════════════════════════════════╝\n")


if __name__ == "__main__":
    asyncio.run(main())
