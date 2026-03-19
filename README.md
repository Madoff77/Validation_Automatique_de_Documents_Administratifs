# DocPlatform

Plateforme de traitement intelligent de documents administratifs français.
Pipeline complet : **OCR adaptatif → Classification ML → Extraction → Validation → Conformité**.

> Projet académique S19 — IPSSI 2026

---

## Sommaire

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Démarrage](#démarrage)
4. [Données de démo](#données-de-démo)
5. [Modèle ML](#modèle-ml)
6. [Interfaces](#interfaces)
7. [Commandes](#commandes)
8. [Architecture](#architecture)
9. [Pipeline](#pipeline)
10. [API](#api)
11. [Dépannage](#dépannage)

---

## Prérequis

| Outil | Version minimale |
|-------|-----------------|
| Docker Desktop | 24.0 |
| Docker Compose | 2.20 |
| Make | any |

> Allouer **au moins 4 Go de RAM** à Docker Desktop (Settings → Resources → Memory).

---

## Installation

```bash
git clone <repo>
cp .env.example .env
```

Le fichier `.env` fonctionne tel quel en local. Les seules valeurs à changer en production :

```env
JWT_SECRET_KEY=supersecretkey_change_in_production_please
# Générer une vraie clé : openssl rand -hex 32
```

---

## Démarrage

```bash
make up
```

| Service | Rôle | Port |
|---------|------|------|
| `backend-api` | API FastAPI | 8000 |
| `frontend-crm` | Interface opérateurs | 5173 |
| `frontend-compliance` | Interface conformité | 5174 |
| `airflow-webserver` | Orchestration pipeline | 8080 |
| `mongo` | Base de données | 27017 |
| `minio` | Stockage fichiers | 9000 / 9001 |

**Sur une machine avec peu de RAM (< 8 Go)**, démarrer par groupe :

```bash
# Socle minimal
docker compose up -d mongo minio minio-init backend-api frontend-crm frontend-compliance

# Airflow (optionnel pour la démo)
docker compose up -d postgres airflow-init airflow-webserver airflow-scheduler
```

---

## Données de démo

```bash
make seed
```

Crée en base :
- **3 utilisateurs** : admin, operator, viewer
- **3 fournisseurs** : BTP SOLUTIONS SAS, TECHNO SERVICES EURL, CONSEIL & CO SARL
- **11 documents** traités avec le pipeline complet, incluant des anomalies intentionnelles :
  - SIRET invalide (attestation SIRET TECHNO SERVICES)
  - Attestation URSSAF expirée (BTP)
  - Kbis trop ancien > 90 jours (CONSEIL & CO)
  - Scan fortement dégradé (facture CONSEIL, combined sévérité 0.8)

> Le seed est **idempotent** — relancer `make seed` ne crée pas de doublons.

---

## Modèle ML

```bash
make train
```

Entraîne un **TF-IDF (1-2 grams, 8000 features) + Random Forest (200 arbres)** sur 900 documents synthétiques (150 × 6 classes), avec validation croisée 5 folds.

> Sans cette étape, le système bascule automatiquement sur un classifieur par mots-clés (fallback fonctionnel, moins précis).

**Types de documents reconnus** : `FACTURE` · `DEVIS` · `KBIS` · `URSSAF` · `SIRET` · `RIB`

---

## Interfaces

| Interface | URL | Identifiants |
|-----------|-----|--------------|
| Frontend CRM | http://localhost:5173 | admin / admin123 |
| Frontend Compliance | http://localhost:5174 | admin / admin123 |
| API Swagger | http://localhost:8000/docs | — |
| Airflow | http://localhost:8080 | admin / admin |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |

### Rôles utilisateurs

| Action | viewer | operator | admin |
|--------|:------:|:--------:|:-----:|
| Consulter documents / fournisseurs / anomalies | Oui | Oui | Oui |
| Uploader un document | Non | Oui | Oui |
| Créer / modifier un fournisseur | Non | Oui | Oui |
| Résoudre une anomalie | Non | Oui | Oui |
| Relancer le pipeline | Non | Oui | Oui |
| Gérer les utilisateurs | Non | Non | Oui |

---

## Commandes

```bash
make up          # Démarrer tous les services
make down        # Arrêter (volumes conservés)
make restart     # Redémarrer
make clean       # Arrêter + supprimer volumes et données
make build       # Rebuilder les images Docker

make seed        # Charger les données de démo
make train       # Entraîner le modèle ML

# Logs
make logs
docker compose logs -f backend-api
docker compose logs -f airflow-scheduler

# Shell
docker compose exec backend-api bash
docker compose exec mongo mongosh -u root -p rootpassword
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                       │
│                                                                    │
│  ┌─────────────┐  ┌──────────────────┐                           │
│  │ frontend-   │  │ frontend-        │                           │
│  │ crm :5173   │  │ compliance :5174 │                           │
│  └──────┬──────┘  └────────┬─────────┘                           │
│         └─────────────┬────┘                                      │
│                        │                                           │
│               ┌────────▼────────┐                                 │
│               │   backend-api   │   FastAPI :8000 · JWT · RBAC   │
│               └──┬──────┬───┬───┘                                 │
│                  │      │   │                                      │
│          ┌───────┘  ┌───┘   └──────────────┐                     │
│          │          │                       │                      │
│  ┌───────▼──┐  ┌────▼──────┐  ┌────────────▼──────────────────┐  │
│  │ MongoDB  │  │   MinIO   │  │           Airflow :8080        │  │
│  │ :27017   │  │ :9000     │  │   DAG : document_pipeline      │  │
│  │ 4 collec.│  │ 3 buckets │  │   OCR → ML → Extract → Valid.  │  │
│  └──────────┘  └───────────┘  └───────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Stockage (MinIO)

| Bucket | Contenu |
|--------|---------|
| `raw` | Fichiers originaux uploadés |
| `clean` | Texte OCR extrait + métadonnées |
| `curated` | Données structurées finales (JSON) |

### Base de données (MongoDB)

| Collection | Contenu |
|------------|---------|
| `users` | Comptes + hash bcrypt |
| `suppliers` | Fournisseurs + statut conformité |
| `documents` | Métadonnées + champs extraits + validation |
| `anomalies` | Anomalies + statut résolution |

---

## Pipeline

```
UPLOAD
  Fichier → MinIO (raw)  ·  Métadonnées → MongoDB (status: pending)
  └─ Déclenchement Airflow via REST API
       │
       ▼
OCR
  PDF natif   → pdfplumber             (conf. ~0.98)
  Scan/Image  → OpenCV + Tesseract 5   (7 stratégies adaptatives)
  Texte brut  → lecture directe        (conf. 1.0)
       │
       ▼
CLASSIFICATION
  Normalisation : SIRET · montants · dates → tokens neutres
  TF-IDF (1-2 grams, 8000 features) + RandomForest (200 arbres)
  Fallback mots-clés si modèle absent ou confiance < 0.6
       │
       ▼
EXTRACTION
  Regex : SIRET · TVA · IBAN · montants · dates · n° document
  Heuristique : raison sociale (suffixes juridiques SAS/SARL/EURL...)
  Déduction croisée : 2 montants connus → 3e calculé
       │
       ▼
VALIDATION
  SIRET     : algorithme de Luhn
  IBAN      : MOD-97
  TVA intra : clé = (12 + 3×SIREN%97) % 97
  Montants  : montant_ht × taux ≈ montant_tva (tolérance ±1€)
  Kbis      : âge < 90 jours (obligation légale)
  Expiration : alerte si < 30 jours
  Inter-docs : cohérence SIRET entre tous les docs d'un fournisseur
  └─ Anomalies → MongoDB  ·  compliance_status fournisseur mis à jour
       │
       ▼
FINALISATION
  JSON structuré → MinIO (curated)  ·  status: "processed" | "error"
```

---

## API

Documentation interactive : **http://localhost:8000/docs**

```
# Auth
POST   /auth/login              → { access_token, refresh_token }
POST   /auth/refresh            → { access_token, refresh_token }
POST   /auth/logout
GET    /auth/me
POST   /auth/register           [admin]

# Documents
POST   /documents/upload        [operator+]
GET    /documents               ?status= &doc_type= &supplier_id=
GET    /documents/{id}
GET    /documents/{id}/download
POST   /documents/{id}/reprocess  [operator+]
DELETE /documents/{id}          [admin]

# Fournisseurs
GET    /suppliers
POST   /suppliers               [operator+]
GET    /suppliers/{id}
PUT    /suppliers/{id}          [operator+]
DELETE /suppliers/{id}          [admin]
GET    /suppliers/{id}/compliance

# Anomalies
GET    /anomalies               ?severity= &type= &resolved= &supplier_id=
PATCH  /anomalies/{id}/resolve  [operator+]
GET    /anomalies/expiring-soon

# Stats
GET    /stats/dashboard
GET    /health
```

---

## Dépannage

**Les services ne démarrent pas**
```bash
docker compose logs <service>
# Vérifier les ports occupés : 8000, 8080, 9000, 27017, 5432, 5173, 5174
```

**`make seed` échoue**
```bash
# Vérifier que le backend répond
curl http://localhost:8000/health

# Relancer directement
docker compose exec backend-api sh -c "python /app/scripts/seed.py"
```

**Pipeline bloqué en `preprocessing`**
```bash
docker compose logs airflow-scheduler
# Puis inspecter le run dans http://localhost:8080
```

**Modèle ML non chargé (classification par mots-clés utilisée)**
```bash
make train
docker compose exec backend-api ls /app/models/trained/
```

**Réinitialisation complète**
```bash
make clean && make up && make seed && make train
```

---

## Stack technique

| Couche | Technologies |
|--------|-------------|
| API | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| Auth | JWT (python-jose), bcrypt, RBAC 3 niveaux |
| Base de données | MongoDB 7 (Motor async + PyMongo sync) |
| Stockage | MinIO S3-compatible |
| OCR | Tesseract 5, OpenCV 4, pdfplumber |
| ML | scikit-learn — TF-IDF + RandomForest |
| Orchestration | Apache Airflow 2.8 |
| Frontends | React 18, Vite 5, Tailwind CSS, TanStack Query v5 |
| Infra | Docker Compose, Nginx, structlog |
