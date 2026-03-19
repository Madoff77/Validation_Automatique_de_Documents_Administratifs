from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# ajouter le dossier parent au PYTHONPATH pour accéder aux modules pipeline

for path in ["/opt/airflow", "/app"]:
    if path not in sys.path:
        sys.path.insert(0, path)

# configurer structlog pour que les logs apparaissent dans les task logs Airflow + exception si jamais 

try:
    from utils.logger import configure_logging
    configure_logging()
except Exception as _log_err:
    print(f"[DAG] structlog config skipped: {_log_err}")

# arguments par defaults

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


# focntions wrapper (appelées par PythonOperator)

def _get_document_id(context: dict) -> str:

    # extraire document_id depuis dag_run.conf.

    conf = context["dag_run"].conf or {}
    document_id = conf.get("document_id")

    if document_id:
        print(f"[DAG] document_id fourni via conf : {document_id}")
        return document_id

    print("[DAG] Aucun document_id dans conf — fallback dev : recherche dans MongoDB")
    try:
        import pymongo

        # lire directement les variables d''env
        mongo_uri = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
        mongo_db = os.environ.get("MONGO_DB", "docplatform")

        client = pymongo.MongoClient(mongo_uri)
        db = client[mongo_db]

        # on donne la priorité aux document pending
        doc = db.documents.find_one(
            {"status": "pending"},
            sort=[("upload_timestamp", pymongo.DESCENDING)],
        )
        # sinon n'importe quel document pour test
        if not doc:
            doc = db.documents.find_one(
                {},
                sort=[("upload_timestamp", pymongo.DESCENDING)],
            )
        client.close()

        if not doc:
            raise ValueError("Fallback dev : aucun document trouvé dans MongoDB")

        document_id = doc["document_id"]
        print(
            f"[DAG] Fallback dev — document_id sélectionné automatiquement : {document_id} "
            f"(status={doc.get('status')}, type={doc.get('doc_type')}, "
            f"fournisseur={doc.get('supplier_id')})"
        )
        return document_id

    except Exception as e:
        raise ValueError(
            f"dag_run.conf doit contenir 'document_id' — fallback dev échoué : {e}"
        ) from e


def fn_preprocess_ocr(**context):
    """Task 1 : Preprocessing image + OCR."""
    document_id = _get_document_id(context)
    print(f"[preprocess_ocr] START document_id={document_id}")
    from pipeline.processor import task_ocr
    result = task_ocr(document_id)
    print(f"[preprocess_ocr] DONE method={result.get('ocr_method')} confidence={result.get('ocr_confidence', 0):.2f} text_length={len(result.get('ocr_text', ''))}")
    context["ti"].xcom_push(key="document_id", value=document_id)
    context["ti"].xcom_push(key="ocr_text", value=result["ocr_text"])
    context["ti"].xcom_push(key="ocr_confidence", value=result["ocr_confidence"])
    return result


def fn_classify(**context):
    """Task 2 : Classification type de document."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")
    ocr_text = ti.xcom_pull(task_ids="preprocess_ocr", key="ocr_text")

    print(f"[classify] START document_id={document_id} text_length={len(ocr_text or '')}")
    from pipeline.processor import task_classify
    result = task_classify(document_id, ocr_text=ocr_text)
    print(f"[classify] DONE doc_type={result['doc_type']} confidence={result['confidence']:.3f}")

    ti.xcom_push(key="doc_type", value=result["doc_type"])
    ti.xcom_push(key="classification_confidence", value=result["confidence"])
    return result


def fn_extract_fields(**context):
    """Task 3 : Extraction des champs métier."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")
    ocr_text = ti.xcom_pull(task_ids="preprocess_ocr", key="ocr_text")
    doc_type = ti.xcom_pull(task_ids="classify", key="doc_type")

    print(f"[extract_fields] START document_id={document_id} doc_type={doc_type}")
    from pipeline.processor import task_extract
    result = task_extract(document_id, doc_type=doc_type, ocr_text=ocr_text)
    print(f"[extract_fields] DONE fields_found={len([v for v in result['extracted'].values() if v is not None])}")

    ti.xcom_push(key="extracted", value=result["extracted"])
    return result


def fn_validate(**context):
    """Task 4 : Validation inter-documents + détection anomalies."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")

    print(f"[validate] START document_id={document_id}")
    from pipeline.processor import task_validate
    result = task_validate(document_id)
    print(f"[validate] DONE status={result['validation_status']} anomalies={result['anomaly_count']}")
    ti.xcom_push(key="validation_status", value=result["validation_status"])
    return result


def fn_finalize(**context):
    """Task 5 : Stockage zone curated + update statut final."""
    ti = context["ti"]
    document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")

    print(f"[finalize] START document_id={document_id}")
    from pipeline.processor import task_finalize
    result = task_finalize(document_id)
    print(f"[finalize] DONE curated_path={result.get('curated_path')}")
    return result


# marquer le document en erreur dans mongo si le DAG ne réussie pas

def on_failure_callback(context):
    try:
        # priorité conf explicite sinon XCom
        conf = context["dag_run"].conf or {}
        document_id = conf.get("document_id")
        if not document_id:
            ti = context.get("ti")
            if ti:
                document_id = ti.xcom_pull(task_ids="preprocess_ocr", key="document_id")
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


#definition de DAG

with DAG(
    dag_id="document_pipeline",
    default_args=DEFAULT_ARGS,
    description="Pipeline de traitement documentaire : OCR → Classification → Extraction → Validation → Curated",
    schedule_interval=None,          
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=20,               # 20 documents max traitée en meme temps
    concurrency=10,
    tags=["docplatform", "ocr", "ml"],
    on_failure_callback=on_failure_callback,
    doc_md="""
## Pipeline de Traitement Documentaire

ce DAG traite un document administratif de bout en bout :

preprocess_ocr - classify - extract_fields - validate - finalize


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
        doc_md="Extraction regex : SIRET, TVA, montants, dates, IBAN, raison sociale",
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

    # chaine linéaire
    preprocess_ocr >> classify >> extract_fields >> validate >> finalize
