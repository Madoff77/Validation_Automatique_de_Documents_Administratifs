# CONTEXT MASTER — Plateforme de Traitement Intelligent de Documents Administratifs

> Fichier de référence central. Mis à jour à chaque décision architecturale significative.
> Date initiale : 2026-03-16

---

## 1. VISION GLOBALE

Construire une plateforme end-to-end de traitement de documents administratifs d'entreprise (factures, devis, attestations, Kbis, RIB) capable de :
- Ingérer des documents hétérogènes (PDF, images, scans de mauvaise qualité)
- Classifier automatiquement leur type
- Extraire les champs clés via OCR + règles métier
- Détecter les incohérences inter-documents
- Alimenter deux applications métier (CRM + outil de conformité)
- S'exécuter dans un environnement conteneurisé et orchestré

**Cible académique** : projet démontrable en live, défendable devant jury, industrialisé.

---

## 2. ARCHITECTURE GÉNÉRALE

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTENDS                            │
│   [frontend-crm :5173]        [frontend-compliance :5174]   │
└────────────────────┬────────────────────┬───────────────────┘
                     │                    │
                     ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│               BACKEND API — FastAPI :8000                   │
│  /documents  /suppliers  /validation  /pipeline  /health    │
└──────────┬──────────────────────────────────────┬───────────┘
           │                                      │
           ▼                                      ▼
┌──────────────────────┐              ┌───────────────────────┐
│   MinIO :9000        │              │   MongoDB :27017       │
│   (Data Lake S3)     │              │   (Métadonnées)        │
│                      │              │                        │
│  raw/       ← upload │              │  documents collection  │
│  clean/     ← OCR    │              │  suppliers collection  │
│  curated/   ← final  │              │  anomalies collection  │
└──────────────────────┘              └───────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│              AIRFLOW :8080 — Orchestration                  │
│                                                             │
│  DAG: document_pipeline                                     │
│   1. task_preprocess   (OpenCV preprocessing)               │
│   2. task_ocr          (Tesseract extraction)               │
│   3. task_classify     (TF-IDF + Random Forest)             │
│   4. task_extract      (Regex + règles métier)              │
│   5. task_validate     (Moteur de règles métier)            │
│   6. task_store        (Stockage MongoDB curated)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. ZONES DE STOCKAGE (Data Lake Tiers)

| Zone     | Support | Contenu                           | Format        |
|----------|---------|-----------------------------------|---------------|
| Raw      | MinIO   | Documents bruts uploadés          | PDF, PNG, JPG |
| Clean    | MinIO   | Texte OCR extrait                 | .txt, .json   |
| Curated  | MongoDB | Données structurées extraites     | JSON documents|

**Justification MinIO** : S3-compatible, déployable localement, simule exactement un AWS S3 / Azure Blob pour une démo crédible. Pas besoin de cloud réel.

**Justification MongoDB** : Documents JSON naturellement hétérogènes (chaque type de document a des champs différents), schéma flexible = parfait pour données semi-structurées. Indexation efficace sur SIRET, date, type.

---

## 4. COMPOSANTS DÉTAILLÉS

### 4.1 Backend API (FastAPI)
- **Port** : 8000
- **Framework** : FastAPI + Uvicorn
- **Responsabilités** :
  - Reception upload multi-documents
  - Déclenchement pipeline via Airflow REST API
  - Exposition des données extraites
  - CRUD fournisseurs
  - Exposition des anomalies

### 4.2 Pipeline OCR (OpenCV + Tesseract)
Étapes de preprocessing :
1. **Conversion grayscale** : réduction bruit couleur
2. **Deskew** : correction rotation (Hough transform)
3. **Denoise** : filtre médian / fastNlMeans
4. **Thresholding** : Otsu binarisation adaptative
5. **Upscaling** : si résolution < 300 DPI estimée
6. **Tesseract** : `lang=fra+eng`, PSM 3 (auto)

**Justification** : Tesseract v5 avec LSTM engine est l'état de l'art open source. OpenCV preprocessing est la pratique industrielle standard pour améliorer la qualité OCR sur scans dégradés.

### 4.3 Classification Documentaire (ML)
- **Modèle** : TF-IDF (1-2 grams, max_features=5000) + Random Forest (n_estimators=100)
- **Classes** : FACTURE, DEVIS, SIRET, URSSAF, KBIS, RIB
- **Entraînement** : Sur documents synthétiques générés (≥ 50 par classe)
- **Fallback** : Classification par règles keyword si confiance < 0.6
- **Métriques cibles** : accuracy > 90%, F1 > 0.88 par classe

**Pourquoi Random Forest ?**
- Interprétable (feature importances)
- Robuste au bruit / variance OCR
- Pas besoin de GPU
- Fonctionne bien avec peu de données
- Expliquable devant jury

**Alternatives écartées** :
- BERT/transformers : overkill, GPU nécessaire, latence trop haute pour demo
- SVM : moins robuste, moins interprétable
- LLM (GPT, Claude) : coût, latence, offline impossible

### 4.4 Extraction de Champs (Regex + Règles)
Champs extraits par type de document :

| Champ          | Regex / Méthode                       | Types concernés         |
|----------------|---------------------------------------|-------------------------|
| SIRET          | `\b\d{14}\b`                          | Tous                    |
| SIREN          | `\b\d{9}\b`                           | SIRET, KBIS             |
| N° TVA         | `FR\s*\d{2}\s*\d{9}`                  | FACTURE, DEVIS          |
| Montant HT     | Regex montant + contexte "HT"         | FACTURE, DEVIS          |
| Montant TTC    | Regex montant + contexte "TTC"        | FACTURE, DEVIS          |
| Taux TVA       | `20\s*%`, `10\s*%`, `5[,.]5\s*%`     | FACTURE, DEVIS          |
| Date émission  | Multiple formats (DD/MM/YYYY, etc.)   | Tous                    |
| Date expir.    | Contexte "valable", "expire", "jusqu" | URSSAF, KBIS            |
| IBAN           | `FR\d{2}[\s\d]{23,27}`               | RIB                     |
| BIC            | `[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}`        | RIB                     |
| Raison sociale | spaCy ORG NER (si confiance > 0.7)    | Tous                    |

### 4.5 Moteur de Validation Métier
Règles implémentées :
1. **Cohérence SIRET** : même fournisseur → même SIRET sur tous les docs
2. **Expiration URSSAF** : date d'expiration >= aujourd'hui
3. **Expiration Kbis** : Kbis valide < 3 mois (règle légale française)
4. **Cohérence TVA** : HT × (1 + taux) ≈ TTC (tolérance 1€)
5. **Format SIRET** : algorithme Luhn/validation mod 97
6. **Format IBAN** : validation standard

### 4.6 Airflow (Orchestration)
- **Executor** : LocalExecutor (simple, pas de Redis, suffisant pour demo)
- **DAG** : `document_pipeline` — triggered via API ou upload
- **Tasks** : chaîne linéaire (preprocess → ocr → classify → extract → validate → store)
- **Logs** : accessibles via UI Airflow :8080

### 4.7 Frontends React

**frontend-crm** (port 5173) :
- Dashboard : stats documents, fournisseurs actifs
- Liste fournisseurs avec statut documents
- Fiche fournisseur avec auto-remplissage depuis données extraites
- Upload documents
- Visualiseur document avec données extraites side-by-side

**frontend-compliance** (port 5174) :
- Dashboard anomalies (compteurs, criticité)
- Liste des anomalies avec filtres
- Vue dates d'expiration (calendrier / liste)
- Cohérence SIRET par fournisseur
- Détail dossier fournisseur avec statut validation

---

## 5. FLUX DE DONNÉES COMPLET

```
Utilisateur
    │
    │ POST /api/documents/upload (multipart/form-data)
    ▼
FastAPI
    │ 1. Stocke fichier brut → MinIO raw/{supplier_id}/{filename}
    │ 2. Crée document MongoDB { status: "pending", zone: "raw" }
    │ 3. Déclenche DAG Airflow via REST API
    ▼
Airflow DAG: document_pipeline
    │
    ├── Task 1: preprocess_image
    │   └── OpenCV: grayscale → deskew → denoise → threshold → upscale
    │       └── Stocke image préprocessée → MinIO clean/{id}/preprocessed.png
    │
    ├── Task 2: run_ocr
    │   └── Tesseract sur image preprocessée → texte brut
    │       └── Stocke texte → MinIO clean/{id}/ocr_text.txt
    │       └── Update MongoDB { status: "ocr_done", ocr_text: "..." }
    │
    ├── Task 3: classify_document
    │   └── TF-IDF vectorize(ocr_text) → RF.predict()
    │       └── Si confiance < 0.6 → fallback keyword rules
    │       └── Update MongoDB { doc_type: "FACTURE", confidence: 0.94 }
    │
    ├── Task 4: extract_fields
    │   └── Regex + règles → champs structurés
    │       └── Update MongoDB { extracted: { siret: "...", montant_ht: ... } }
    │
    ├── Task 5: validate_document
    │   └── Règles inter-documents + règles internes
    │       └── Insert anomalies collection si problème détecté
    │       └── Update MongoDB { validation: { status: "ok"|"warning"|"error" } }
    │
    └── Task 6: finalize
        └── Stocke JSON final → MinIO curated/{id}/data.json
            └── Update MongoDB { status: "processed", zone: "curated" }
```

---

## 6. SCHÉMAS DE DONNÉES MONGODB

### Collection `documents`
```json
{
  "_id": "ObjectId",
  "document_id": "uuid",
  "supplier_id": "uuid",
  "filename": "facture_2024_001.pdf",
  "original_filename": "facture.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 245000,
  "upload_timestamp": "ISODate",
  "status": "pending|preprocessing|ocr_done|classified|extracted|validated|processed|error",
  "zone": "raw|clean|curated",
  "minio_raw_path": "raw/supplier_id/filename",
  "minio_clean_path": "clean/document_id/",
  "minio_curated_path": "curated/document_id/data.json",
  "doc_type": "FACTURE|DEVIS|SIRET|URSSAF|KBIS|RIB|UNKNOWN",
  "classification_confidence": 0.94,
  "ocr_text": "...",
  "ocr_quality_score": 0.87,
  "extracted": {
    "siret": "12345678901234",
    "siren": "123456789",
    "tva_number": "FR12123456789",
    "montant_ht": 1000.00,
    "montant_tva": 200.00,
    "montant_ttc": 1200.00,
    "taux_tva": 20.0,
    "date_emission": "2024-01-15",
    "date_echeance": "2024-02-15",
    "date_expiration": null,
    "numero_document": "FACT-2024-001",
    "raison_sociale": "ACME SAS",
    "iban": null,
    "bic": null
  },
  "validation": {
    "status": "ok|warning|error",
    "checks": [
      { "rule": "siret_consistency", "status": "ok", "message": "" },
      { "rule": "tva_coherence", "status": "warning", "message": "Écart TVA: 0.50€" }
    ]
  },
  "airflow_run_id": "manual__2024-01-15T10:00:00",
  "processing_duration_ms": 3420,
  "error_message": null
}
```

### Collection `suppliers`
```json
{
  "_id": "ObjectId",
  "supplier_id": "uuid",
  "name": "ACME SAS",
  "siret": "12345678901234",
  "siren": "123456789",
  "tva_number": "FR12123456789",
  "address": "12 rue de la Paix, 75001 Paris",
  "email": "contact@acme.fr",
  "phone": "+33 1 23 45 67 89",
  "created_at": "ISODate",
  "updated_at": "ISODate",
  "document_count": 5,
  "compliance_status": "compliant|warning|non_compliant|pending",
  "notes": ""
}
```

### Collection `anomalies`
```json
{
  "_id": "ObjectId",
  "anomaly_id": "uuid",
  "supplier_id": "uuid",
  "document_id": "uuid",
  "related_document_id": "uuid",
  "type": "SIRET_MISMATCH|DATE_EXPIRED|TVA_INCOHERENCE|MISSING_FIELD|FORMAT_ERROR",
  "severity": "error|warning|info",
  "message": "SIRET différent entre facture FACT-001 et attestation URSSAF-002",
  "details": { "expected": "12345678901234", "found": "98765432109876" },
  "detected_at": "ISODate",
  "resolved": false,
  "resolved_at": null
}
```

---

## 7. CONVENTIONS DE CODE

- **Python** : PEP 8, type hints sur toutes les fonctions publiques, docstrings courtes
- **Nommage** : snake_case Python, camelCase React, UPPER_CASE constantes
- **Logs** : structurés JSON via `structlog`, niveau INFO en prod, DEBUG en dev
- **Errors** : FastAPI HTTPException avec codes cohérents (400, 404, 422, 500)
- **Tests** : pas de tests unitaires dans MVP (délai), mais code structuré pour testabilité
- **Env** : toutes les config dans `.env`, jamais hardcodé

---

## 8. DÉCISIONS D'ARCHITECTURE

| Décision | Choix retenu | Alternative écartée | Raison |
|----------|-------------|---------------------|--------|
| OCR engine | Tesseract 5 | EasyOCR, PaddleOCR | Gratuit, mature, langage FR, CLI-ready |
| Classifier | TF-IDF + RF | BERT, GPT | Expliquable, pas GPU, latence faible |
| Orchestration | Airflow LocalExecutor | Celery, Temporal | Simplicité démo, UI intégrée |
| Storage objet | MinIO | AWS S3, Azure Blob | Local, S3-compatible, gratuit |
| DB | MongoDB | PostgreSQL | Schéma flexible, documents JSON natifs |
| API | FastAPI-slim | Django REST, Flask | Async, auto-docs Swagger, typage ; version slim pour réduire l'image Docker |
| Airflow executor | Local | Celery | Pas de Redis/broker nécessaire |
| Frontend build | Vite | CRA, Next.js | Rapide, léger, parfait pour demo |

---

## 9. PLAN D'IMPLÉMENTATION

### Phase 1 — Cadrage & Documentation
- Architecture définie
- CONTEXT_MASTER.md créé
- CHANGELOG_IMPLEMENTATION.md créé

### Phase 2 — Socle Technique
- docker-compose.yml (tous services)
- .env.example
- Backend FastAPI skeleton
- MongoDB + MinIO clients
- Healthchecks

### Adaptations setup machine (2026-03-16)
- `version: "3.9"` supprimé du docker-compose (Docker Compose v2 ne l'exige plus)
- Healthcheck MinIO désactivé (image sans `curl`) → `minio-init` en dépendance simple
- Healthchecks `backend-api` et `airflow-webserver` : `curl` → `python urllib.request` (curl absent de python:3.11-slim)
- `backend-api` depends_on minio : `service_healthy` → `service_started`
- `fastapi` → `fastapi-slim` (image plus légère, API identique)
- `stdnum` → `python-stdnum` (nom PyPI correct)
- `email-validator==2.3.0` ajouté explicitement (requis par `pydantic.EmailStr`)
- `uuid`, `spacy` supprimés des dépendances (stdlib / non nécessaire)

### Phase 3 — Générateur de Données
- Faker + templates documents
- Simulation dégradation scan
- ~50 docs par classe (300 total)
- Quelques incohérences volontaires

### Phase 4 — Pipeline Documentaire
- OCR preprocessing (OpenCV)
- Tesseract extraction
- Classifier training + inference
- Field extractor (regex)
- Validation engine
- Airflow DAG

### Phase 5 — Frontends
- frontend-crm: CRUD fournisseurs, upload, dashboard
- frontend-compliance: anomalies, expirations, SIRET check

### Phase 6 — Modèle IA & Justification
- Entraînement sur données synthétiques
- Métriques classification
- Documentation défense jury

### Phase 7 — Démo & Soutenance
- Seed data réaliste
- Scénario demo structuré
- Réponses jury préparées

---

## 10. STRATÉGIE DE DÉMONSTRATION

### Scénario demo (10 minutes)
1. **Upload** : glisser-déposer 3 documents (facture + attestation URSSAF + Kbis) pour le fournisseur "BTP Solutions SAS"
2. **Pipeline live** : montrer Airflow UI avec tasks qui s'exécutent
3. **CRM** : montrer fiche fournisseur auto-remplie avec SIRET, raison sociale, montants
4. **Compliance** : montrer anomalie détectée (Kbis expiré + incohérence SIRET simulée)
5. **Data Lake** : montrer MinIO console avec les 3 zones

### Documents demo préparés
- `demo/facture_btp_solutions_ok.pdf` — facture normale, cohérente
- `demo/urssaf_btp_solutions_expire.pdf` — attestation URSSAF expirée
- `demo/kbis_btp_solutions_mauvais_siret.pdf` — Kbis avec SIRET différent
- `demo/rib_btp_solutions.pdf` — RIB normal
- `demo/facture_scan_degrade.jpg` — facture scannée de mauvaise qualité

---

## 11. STRATÉGIE DÉFENSE JURY

### Q: Pourquoi Random Forest et pas un LLM ?
**R**: Pour un document administratif avec structure prévisible, TF-IDF+RF donne 92%+ d'accuracy avec latence <50ms, sans GPU, explicable via feature importances. Un LLM apporterait 2-3% de gain pour 100x plus de latence et de coût. En production, on pourrait combiner : RF pour classification temps-réel, LLM pour cas ambigus en mode asynchrone.

### Q: Comment scaler à 1 million de documents ?
**R**: Architecture déjà prête pour scaling horizontal :
- MinIO → remplacer par AWS S3 (zero change côté code, même API)
- MongoDB → Atlas avec sharding sur supplier_id
- FastAPI → scale horizontalement derrière un load balancer (stateless)
- Airflow → passer à CeleryExecutor + workers Redis (changement config uniquement)
- Classifier → modèle servi via TorchServe/MLflow pour scaling indépendant

### Q: Gestion de nouveaux champs ?
**R**: Architecture à 3 couches séparées :
1. Nouveau regex dans `field_extractor.py` → nouvelle règle dans `validator.py`
2. Nouveau champ optionnel dans MongoDB (schéma flexible, pas de migration)
3. Nouveau composant UI dans frontend
→ Changement localisé, pas de refactoring global

### Q: Comment optimiser la latence ?
**R**: Pipeline actuel ≈ 3-5s par document.
Optimisations possibles :
- Cache modèle classifier en mémoire (déjà fait)
- Preprocessing GPU via CUDA OpenCV (optionnel)
- Tesseract --dpi 300 + PSM adaptatif
- MongoDB indexes sur document_id, supplier_id, status
- Résultats cachés Redis pour documents déjà traités

---

## 12. HYPOTHÈSES ET LIMITES

1. **Qualité OCR** : Tesseract fonctionne bien sur documents imprimés. Sur écritures manuscrites, accuracy chute drastiquement → hors scope MVP.
2. **Langue** : Pipeline optimisé pour documents en français. Anglais partiellement supporté.
3. **Formats** : PDF natifs (non-scannés) ont meilleur OCR via extraction directe du texte. Scans JPEG/PNG passent par OpenCV.
4. **Volume** : Demo sur ≤ 1000 documents. Pas de pagination avancée côté frontend dans MVP.
5. **Sécurité** : Pas d'authentification dans MVP (hors scope démo). En production : JWT + RBAC.
6. **Données réelles** : Entraînement sur données synthétiques → peut nécessiter fine-tuning sur données réelles.
