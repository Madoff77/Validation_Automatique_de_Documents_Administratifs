# DocPlatform — Plateforme de Traitement Intelligent de Documents Administratifs

Projet académique S19 — IPSSI
Pipeline complet d'OCR, classification ML et validation de documents administratifs français.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose Stack                         │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ frontend-crm │  │  frontend-   │  │      backend-api         │   │
│  │  :3000       │  │  compliance  │  │      FastAPI :8000        │   │
│  │  React/Vite  │  │  :3001       │  │      JWT + RBAC           │   │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬─────────────┘   │
│         │                  │                       │                  │
│         └──────────────────┴───────────────────────┤                 │
│                                                     │                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────▼─────────────┐  │
│  │   MongoDB    │  │    MinIO     │  │        Airflow            │  │
│  │   :27017     │  │   :9000      │  │        :8080              │  │
│  │  4 collections│  │  3 buckets  │  │  DAG: document_pipeline   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Pipeline OCR→ML→Validation                   │  │
│  │  Upload → OCR (7 stratégies) → TF-IDF+RF → Regex/spaCy → SIRET│  │
│  │          Tesseract   Laplacian   200 arbres   NER    Luhn/MOD97 │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Services

| Service            | URL                    | Description                          |
|--------------------|------------------------|--------------------------------------|
| Frontend CRM       | http://localhost:3000  | Interface opérateurs (upload, suivi) |
| Frontend Compliance| http://localhost:3001  | Interface conformité (anomalies)     |
| API Backend        | http://localhost:8000  | FastAPI + Swagger docs               |
| Airflow            | http://localhost:8080  | Orchestration pipeline               |
| MinIO Console      | http://localhost:9001  | Stockage objets                      |
| Mongo Express      | http://localhost:8081  | Explorateur MongoDB                  |

---

## Démarrage rapide

### Prérequis
- Docker Desktop ≥ 24 (avec au moins 4 Go RAM alloués)
- GNU Make

### 1. Configuration
```bash
cp .env.example .env
# Optionnel: modifier les mots de passe dans .env
```

### 2. Lancer la stack
```bash
make up
```
Attendre ~2 minutes que tous les services démarrent (healthchecks).

### 3. Peupler la base de démonstration
```bash
make seed
```
Crée : 3 utilisateurs, 3 fournisseurs, 11 documents traités avec anomalies intentionnelles.

### 4. Entraîner le modèle ML
```bash
make train
```
Génère ~1200 documents synthétiques, entraîne TF-IDF + RandomForest, sauvegarde les artefacts.

### 5. Lancer le scénario de démo
```bash
make demo
```

---

## Accès par défaut

| Rôle     | Utilisateur | Mot de passe   | Permissions              |
|----------|-------------|----------------|--------------------------|
| Admin    | admin       | admin123       | CRUD complet             |
| Opérateur| operator    | operator123    | Upload, lecture          |
| Viewer   | viewer      | viewer123      | Lecture seule            |

---

## Documents supportés

| Type          | Extraction                           | Validations                        |
|---------------|--------------------------------------|-------------------------------------|
| Facture       | Montants HT/TTC/TVA, SIRET, dates   | Cohérence TVA (±1€), SIRET Luhn    |
| Devis         | Montants, SIRET, validité           | Cohérence montants, SIRET          |
| Kbis          | SIRET, raison sociale, date         | Âge <90j (obligation légale)       |
| URSSAF        | SIRET, période, montant             | Expiration, SIRET Luhn             |
| Attestation SIRET | SIRET, raison sociale            | Validité SIRET (Luhn + La Poste)   |
| RIB           | IBAN, BIC, titulaire                | MOD-97 IBAN, format BIC            |

---

## Pipeline de traitement

```
1. UPLOAD      → MinIO bucket "raw" + document MongoDB (status: pending)
2. TRIGGER     → Airflow REST API → DAG document_pipeline
3. OCR         → pdfplumber (PDF natif) OU OpenCV+Tesseract (scan/image)
                 7 stratégies adaptatives sélectionnées par score Laplacien
4. CLASSIFY    → TF-IDF (8000 features, 1-2grams) + RandomForest (200 trees)
                 Fallback keyword si confiance < 0.6
5. EXTRACT     → Regex compilées + spaCy NER (raison sociale)
                 Déduction croisée montants manquants
6. VALIDATE    → Luhn SIRET, MOD-97 IBAN, clé TVA, cohérence inter-docs
                 Création anomalies MongoDB, mise à jour compliance fournisseur
7. FINALIZE    → JSON structuré → MinIO bucket "curated"
                 Document status: processed/failed
```

---

## Commandes utiles

```bash
make up        # Démarrer tous les services
make down      # Arrêter les services
make seed      # Peupler la base de données
make train     # Entraîner le modèle ML
make demo      # Scénario de démonstration
make clean     # Tout supprimer (volumes inclus)
make logs      # Voir les logs en temps réel
```

---

## Structure du projet

```
.
├── backend/
│   ├── api/                  # FastAPI (routes, auth, schemas)
│   ├── pipeline/
│   │   ├── ocr/             # Préprocesseur + extracteur Tesseract
│   │   ├── classification/  # TF-IDF + RandomForest
│   │   ├── extraction/      # Regex + spaCy NER
│   │   └── validation/      # Luhn, MOD-97, cohérence TVA
│   ├── storage/             # MongoDB + MinIO clients
│   └── utils/               # Logger structlog
├── airflow/dags/            # DAG document_pipeline
├── data-generator/          # Générateur de documents synthétiques
├── frontend-crm/            # Interface opérateurs (React)
├── frontend-compliance/     # Interface conformité (React)
├── scripts/                 # seed.py, demo.sh
├── docker/                  # mongo-init.js
├── docs/                    # JURY_DEFENSE.md
└── docker-compose.yml
```

---

## API — Endpoints principaux

```
POST   /auth/login              Authentification → JWT
POST   /auth/refresh            Renouvellement token
GET    /auth/me                 Utilisateur courant

GET    /documents               Liste avec filtres
POST   /documents/upload        Upload multipart
GET    /documents/{id}          Détail + champs extraits
POST   /documents/{id}/reprocess Relancer le pipeline

GET    /suppliers               Liste fournisseurs
POST   /suppliers               Créer fournisseur
GET    /suppliers/{id}/compliance Métriques conformité

GET    /anomalies               Liste avec filtres
PATCH  /anomalies/{id}/resolve  Marquer résolue
GET    /anomalies/expiring-soon Documents expirant <30j

GET    /stats/dashboard         Statistiques agrégées
```

Documentation interactive : http://localhost:8000/docs

---

## Technologies

**Backend**: Python 3.11, FastAPI, Motor (async MongoDB), MinIO SDK, python-jose JWT, bcrypt, httpx
**OCR**: OpenCV 4, Tesseract 5, pdf2image, pdfplumber
**ML**: scikit-learn (TF-IDF + RandomForest), spaCy fr_core_news_sm, joblib
**Orchestration**: Apache Airflow 2.8 LocalExecutor
**Stockage**: MongoDB 7, MinIO (S3-compatible)
**Frontends**: React 18, Vite 5, Tailwind CSS 3, TanStack Query v5, Recharts, React Router v6
**Infra**: Docker Compose, Nginx (frontends), structlog (JSON logging)
