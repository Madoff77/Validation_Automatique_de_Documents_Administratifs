"""
DAG Airflow : document_pipeline

Orchestration du pipeline de traitement documentaire.
Déclenché via REST API avec conf = {"document_id": "uuid"}.

Graphe des tâches :
    preprocess_ocr → classify → extract_fields → validate → finalize

Chaque tâche :
- lit l'état depuis MongoDB (résistance aux redémarrages)
- passe les résultats via XCom (léger, texte OCR max ~100KB)
- met à jour le statut MongoDB en temps réel
- loggue en JSON structuré

Retry : 2 tentatives avec délai exponentiel.
Timeout : 10 min par tâche (suffisant même pour gros PDF scanné).
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# Ajouter le dossier parent au PYTHONPATH pour accéder aux modules pipeline
# (volumes montés dans docker-compose : ./backend/pipeline → /opt/airflow/pipeline)
for path in ["/opt/airflow", "/app"]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ─────────────────────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────────────────────

DEFAULT_ARGS = {
    "owner": "docplatform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=10),
    "email_on_failure": False,
    "email_on_retry": False,
}


# ─────────────────────────────────────────────────────────────
# FONCTIONS WRAPPER (appelées par PythonOperator)
# ─────────────────────────────────────────────────────────────

def _get_document_id(context: dict) -> str:
    """Extraire document_id depuis dag_run.conf."""
    conf = context["dag_run"].conf or {}
    document_id = conf.get("document_id")
    if not document_id:
        raise ValueError("dag_run.conf doit contenir 'document_id'")
    return document_id


def fn_preprocess_ocr(**context):
    """Task 1 : Preprocessing image + OCR."""
    document_id = _get_document_id(context)
    from pipeline.processor import task_ocr
    result = task_ocr(document_id)
    # Pousser dans XCom pour les tâches suivantes
    context["ti"].xcom_push(key="document_id", value=document_id)
    context["ti"].xcom_push(key="ocr_text", value=result["ocr_text"])
    context["ti"].xcom_push(key="ocr_confidence", value=result["ocr_confidence"])
    return result


def fn_classify(**context):
    """Task 2 : Classification type de document."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")
    ocr_text = ti.xcom_pull(task_ids="preprocess_ocr", key="ocr_text")

    from pipeline.processor import task_classify
    result = task_classify(document_id, ocr_text=ocr_text)

    ti.xcom_push(key="doc_type", value=result["doc_type"])
    ti.xcom_push(key="classification_confidence", value=result["confidence"])
    return result


def fn_extract_fields(**context):
    """Task 3 : Extraction des champs métier."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")
    ocr_text = ti.xcom_pull(task_ids="preprocess_ocr", key="ocr_text")
    doc_type = ti.xcom_pull(task_ids="classify", key="doc_type")

    from pipeline.processor import task_extract
    result = task_extract(document_id, doc_type=doc_type, ocr_text=ocr_text)

    ti.xcom_push(key="extracted", value=result["extracted"])
    return result


def fn_validate(**context):
    """Task 4 : Validation inter-documents + détection anomalies."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")

    from pipeline.processor import task_validate
    result = task_validate(document_id)
    ti.xcom_push(key="validation_status", value=result["validation_status"])
    return result


def fn_finalize(**context):
    """Task 5 : Stockage zone curated + update statut final."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")

    from pipeline.processor import task_finalize
    return task_finalize(document_id)


# ─────────────────────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────────────────────

def on_failure_callback(context):
    """Marquer le document en erreur dans MongoDB si le DAG échoue."""
    try:
        conf = context["dag_run"].conf or {}
        document_id = conf.get("document_id")
        if not document_id:
            return

        error_msg = str(context.get("exception", "Unknown error"))

        for path in ["/opt/airflow", "/app"]:
            if path not in sys.path:
                sys.path.insert(0, path)

        from pipeline.processor import _get_db
        db = _get_db()
        db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": "error", "error_message": error_msg}}
        )
    except Exception as e:
        print(f"on_failure_callback error: {e}")


# ─────────────────────────────────────────────────────────────
# DAG DEFINITION
# ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="document_pipeline",
    default_args=DEFAULT_ARGS,
    description="Pipeline de traitement documentaire : OCR → Classification → Extraction → Validation → Curated",
    schedule_interval=None,           # Déclenché uniquement via API (trigger)
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=20,               # Jusqu'à 20 documents en parallèle
    concurrency=10,
    tags=["docplatform", "ocr", "ml"],
    on_failure_callback=on_failure_callback,
    doc_md="""
## Pipeline de Traitement Documentaire

Ce DAG traite un document administratif de bout en bout :

1. **preprocess_ocr** : Preprocessing OpenCV adaptatif (7 stratégies) + OCR Tesseract multi-pass
2. **classify** : Classification TF-IDF + Random Forest (6 types : FACTURE, DEVIS, SIRET, URSSAF, KBIS, RIB)
3. **extract_fields** : Extraction regex + spaCy (SIRET, TVA, montants, dates, IBAN...)
4. **validate** : Validation inter-documents, détection anomalies (expiration, incohérences SIRET, TVA)
5. **finalize** : Stockage JSON structuré en zone curated MinIO

**Déclenchement** : `POST /api/v1/dags/document_pipeline/dagRuns` avec `conf = {"document_id": "uuid"}`
    """,
) as dag:

    preprocess_ocr = PythonOperator(
        task_id="preprocess_ocr",
        python_callable=fn_preprocess_ocr,
        doc_md="Preprocessing adaptatif (flou/bruit/rotation) + OCR Tesseract multi-pass",
    )

    classify = PythonOperator(
        task_id="classify",
        python_callable=fn_classify,
        doc_md="Classification TF-IDF + Random Forest → type document + confiance",
    )

    extract_fields = PythonOperator(
        task_id="extract_fields",
        python_callable=fn_extract_fields,
        doc_md="Extraction regex + spaCy : SIRET, TVA, montants, dates, IBAN",
    )

    validate = PythonOperator(
        task_id="validate",
        python_callable=fn_validate,
        doc_md="Validation inter-documents + création anomalies MongoDB",
    )

    finalize = PythonOperator(
        task_id="finalize",
        python_callable=fn_finalize,
        doc_md="Stockage JSON structuré zone curated + update statut final",
    )

    # Chaîne linéaire
    preprocess_ocr >> classify >> extract_fields >> validate >> finalize
