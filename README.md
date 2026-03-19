# DocPlatform

Plateforme de traitement intelligent de documents administratifs français.
Pipeline complet : OCR adaptatif — Classification ML — Extraction — Validation — Conformité.

Projet académique S19 — IPSSI 2026

---

## Sommaire

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Démarrage](#démarrage)
4. [Première utilisation](#première-utilisation)
5. [Interfaces](#interfaces)
6. [Commandes](#commandes)
7. [Architecture](#architecture)
8. [Pipeline](#pipeline)
9. [API](#api)
10. [Dépannage](#dépannage)
11. [Stack technique](#stack-technique)

---

## Prérequis

| Outil | Version minimale |
|-------|-----------------|
| Docker Desktop | 24.0 |
| Docker Compose | 2.20 |
| Make | any |

Allouer au moins 6 Go de RAM à Docker Desktop (Settings → Resources → Memory). Airflow et les conteneurs OCR sont gourmands.

---

## Installation

```bash
git clone <repo>
cp .env.example .env
```

Le fichier `.env` fonctionne tel quel en local. Seule valeur à changer en production :

```env
JWT_SECRET_KEY=supersecretkey_change_in_production_please
# Générer une vraie clé : openssl rand -hex 32
```

---

## Démarrage

Le démarrage se fait par étapes pour éviter les problèmes de dépendances entre services.

**Étape 1 — Infrastructure de base**
```bash
docker compose up -d mongo postgres minio
# Attendre que mongo et postgres soient healthy
docker compose ps
```

**Étape 2 — Initialisations**
```bash
docker compose up -d minio-init airflow-init
# Attendre que airflow-init termine avec Exited (0)
docker compose ps airflow-init
```

**Étape 3 — Backend**
```bash
docker compose up -d backend-api mongo-express
# Attendre le healthcheck (~60 secondes)
docker compose ps backend-api
```

**Étape 4 — Airflow et frontends**
```bash
docker compose up -d airflow-webserver airflow-scheduler frontend-crm frontend-compliance
```

| Service | URL | Role |
|---------|-----|------|
| `backend-api` | http://localhost:8000 | API FastAPI |
| `frontend-crm` | http://localhost:5173 | Interface opérateurs |
| `frontend-compliance` | http://localhost:5174 | Interface conformité |
| `airflow-webserver` | http://localhost:8080 | Orchestration pipeline |
| `minio` | http://localhost:9001 | Console stockage |
| `mongo-express` | http://localhost:8081 | Console MongoDB |

---

## Première utilisation

L'ordre est important : le modèle ML doit exister avant que le seed traite les documents.

**Étape 1 — Entraîner le modèle**
```bash
make train
```

Génère 900 documents synthétiques (150 par classe), les OCR avec Tesseract, entraîne un Random Forest et sauvegarde le modèle dans le volume Docker partagé. Durée : 5 à 15 minutes selon la machine.

**Étape 2 — Charger les données de démo**
```bash
make seed
```

Le seed :
- Récupère 15 vraies entreprises françaises depuis l'API SIRENE (données INSEE réelles)
- Crée les 3 comptes utilisateurs (admin, operator, viewer)
- Génère environ 90 documents par fournisseur (FACTURE, DEVIS, KBIS, URSSAF, RIB, SIRET), avec différents niveaux de dégradation (flou, bruit, rotation, basse résolution)
- Déclenche un DAG Airflow par document — le traitement est visible en temps réel sur http://localhost:8080

Un tiers des fournisseurs reçoit intentionnellement des documents avec anomalies (SIRET invalide, URSSAF expirée, Kbis trop ancien) pour illustrer la détection de non-conformité.

Le seed est idempotent : le relancer ne crée pas de doublons.

---

## Interfaces

| Interface | URL | Identifiants |
|-----------|-----|--------------|
| Frontend CRM | http://localhost:5173 | admin / admin123 |
| Frontend Compliance | http://localhost:5174 | admin / admin123 |
| API Swagger | http://localhost:8000/docs | — |
| Airflow | http://localhost:8080 | admin / admin |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Mongo Express | http://localhost:8081 | admin / admin |

### Rôles utilisateurs

| Action | viewer | operator | admin |
|--------|--------|----------|-------|
| Consulter documents / fournisseurs / anomalies | oui | oui | oui |
| Uploader un document | non | oui | oui |
| Créer / modifier un fournisseur | non | oui | oui |
| Résoudre une anomalie | non | oui | oui |
| Relancer le pipeline | non | oui | oui |
| Gérer les utilisateurs | non | non | oui |

---

## Commandes

**Linux / macOS**
```bash
# Services
docker compose up -d                        # Démarrer tous les services
docker compose down                         # Arrêter (volumes conservés)
docker compose restart                      # Redémarrer
docker compose down -v --remove-orphans     # Arrêter + supprimer volumes et données
docker compose build --no-cache            # Rebuilder les images Docker

# ML et données
docker compose exec backend-api python /app/pipeline/classification/train.py
docker compose exec backend-api python /app/scripts/seed.py

# Logs
docker compose logs -f
docker compose logs -f backend-api
docker compose logs -f airflow-scheduler

# Shell
docker compose exec backend-api bash
docker compose exec mongo mongosh -u root -p rootpassword

# Remettre tous les documents en pending (pour re-tester le pipeline Airflow)
docker compose exec -T mongo mongosh "mongodb://root:rootpassword@localhost:27017/docplatform?authSource=admin" \
  --eval "db.documents.updateMany({}, {\$set: {status: 'pending', error_message: null}})"
```

**Windows (PowerShell)**
```powershell
# Services
docker compose up -d
docker compose down
docker compose restart
docker compose down -v --remove-orphans
docker compose build --no-cache

# ML et données
docker compose exec backend-api python /app/pipeline/classification/train.py
docker compose exec backend-api python /app/scripts/seed.py

# Logs
docker compose logs -f
docker compose logs -f backend-api
docker compose logs -f airflow-scheduler

# Shell
docker compose exec backend-api bash
docker compose exec mongo mongosh -u root -p rootpassword

# Remettre tous les documents en pending
docker compose exec mongo mongosh "mongodb://root:rootpassword@localhost:27017/docplatform?authSource=admin" `
  --eval "db.documents.updateMany({}, {`$set: {status: 'pending', error_message: null}})"
```

---

## Architecture

```
+------------------------------------------------------------------+
|                        Docker Compose Stack                       |
|                                                                    |
|  +--------------+  +-------------------+                          |
|  | frontend-crm |  | frontend-         |                          |
|  | :5173        |  | compliance :5174  |                          |
|  +------+-------+  +--------+----------+                          |
|         +-------------------+                                      |
|                     |                                              |
|            +--------v--------+                                     |
|            |   backend-api   |   FastAPI :8000 — JWT — RBAC       |
|            +--+----------+---+                                     |
|               |          |                                         |
|       +-------+    +-----+--------+    +------------------------+  |
|       |            |              |    |      Airflow :8080      |  |
|  +----v----+  +----v----+         |    |  DAG : document_pipeline|  |
|  | MongoDB |  |  MinIO  |         +---->  OCR → ML → Extract     |  |
|  | :27017  |  | :9000   |              |  → Validate → Finalize  |  |
|  | 4 coll. |  | 3 buck. |              +------------------------+  |
|  +---------+  +---------+                                          |
|                                                                    |
|  PostgreSQL :5432  (base interne Airflow uniquement)               |
+------------------------------------------------------------------+
```

### Stockage (MinIO)

| Bucket | Contenu |
|--------|---------|
| `raw` | Fichiers originaux uploadés (PDF, JPEG) |
| `clean` | Texte OCR extrait + métadonnées JSON |
| `curated` | Données structurées finales (JSON) |

### Base de données (MongoDB)

| Collection | Contenu |
|------------|---------|
| `users` | Comptes + hash bcrypt |
| `suppliers` | Fournisseurs + statut conformité |
| `documents` | Métadonnées, texte OCR, champs extraits, validation |
| `anomalies` | Anomalies détectées + statut de résolution |

---

## Pipeline

```
UPLOAD
  Fichier → MinIO (raw)  ·  Métadonnées → MongoDB (status: pending)
  Déclenchement d'un DAG Airflow via REST API
       |
       v
OCR
  PDF natif   → pdfplumber             (score qualite ~0.98)
  Scan/Image  → OpenCV + Tesseract 5   (8 strategies adaptatives)
  Texte brut  → lecture directe        (score qualite 1.0)

  Le score de qualite OCR (0-1) mesure la confiance moyenne de Tesseract
  par mot lus (filtrage des mots en dessous de 40/100).
       |
       v
CLASSIFICATION
  Normalisation : SIRET, montants, dates → tokens neutres
  TF-IDF (1-2 grams, 8000 features) + RandomForest (200 arbres)
  Fallback mots-cles si modele absent ou confiance < 0.6
  Le score de confiance de classification (0-1) est la probabilite
  de la classe gagnante selon le vote des 200 arbres.
       |
       v
EXTRACTION
  Regex : SIRET, TVA, IBAN, montants, dates, numero de document
  Heuristique : raison sociale (suffixes SAS / SARL / EURL...)
  Deduction croisee : 2 montants connus → 3e calcule
       |
       v
VALIDATION
  Pre-check OCR  : texte vide → erreur bloquante
                   score < 25% → avertissement
  SIRET          : algorithme de Luhn
  IBAN           : MOD-97
  TVA intra      : cle = (12 + 3 × SIREN%97) % 97
  Montants       : montant_ht × taux ≈ montant_tva (tolerance ±1€)
  Kbis           : age < 90 jours (obligation legale)
  Expiration     : alerte si < 30 jours
  Inter-docs     : coherence SIRET entre tous les docs d'un fournisseur
  Anomalies → MongoDB  ·  compliance_status fournisseur mis a jour
       |
       v
FINALISATION
  JSON structure → MinIO (curated)  ·  status: "processed" | "error"
```

---

## API

Documentation interactive : http://localhost:8000/docs

```
Auth
  POST   /auth/login              → { access_token, refresh_token }
  POST   /auth/refresh            → { access_token, refresh_token }
  POST   /auth/logout
  GET    /auth/me
  POST   /auth/register           [admin]

Documents
  POST   /documents/upload        [operator+]
  GET    /documents               ?status= &doc_type= &supplier_id=
  GET    /documents/{id}
  GET    /documents/{id}/download
  POST   /documents/{id}/reprocess  [operator+]
  DELETE /documents/{id}          [admin]

Fournisseurs
  GET    /suppliers
  POST   /suppliers               [operator+]
  GET    /suppliers/{id}
  PUT    /suppliers/{id}          [operator+]
  DELETE /suppliers/{id}          [admin]
  GET    /suppliers/{id}/compliance

Anomalies
  GET    /anomalies               ?severity= &type= &resolved= &supplier_id=
  PATCH  /anomalies/{id}/resolve  [operator+]
  GET    /anomalies/expiring-soon

Stats
  GET    /stats/dashboard
  GET    /health
```

---

## Dépannage

**Les services ne démarrent pas**
```bash
docker compose logs <nom-du-service>
# Verifier les ports utilises : 8000, 8080, 9000, 9001, 27017, 5432, 5173, 5174
docker compose ps
```

**Le train plante (generateur non trouve)**
```bash
# Verifier que le volume data-generator est bien monte
docker compose exec backend-api ls /app/data-generator/
```

**Le seed plante ou les documents ne passent pas par Airflow**
```bash
# Verifier que le backend repond (ouvrir dans un navigateur ou tester depuis le container)
docker compose exec backend-api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"

# Verifier qu'Airflow est healthy
docker compose exec backend-api python -c "import urllib.request; print(urllib.request.urlopen('http://airflow-webserver:8080/health').read())"

# Lancer le seed manuellement
docker compose exec backend-api python /app/scripts/seed.py
```

**Pipeline bloque en `preprocessing`**
```bash
docker compose logs airflow-scheduler
# Puis inspecter le run dans http://localhost:8080
```

**Modele ML non charge (classification par mots-cles utilisee)**
```bash
docker compose exec backend-api python /app/pipeline/classification/train.py
docker compose exec backend-api ls /app/models/trained/
```

**Reinitialisation complete**
```bash
docker compose down -v --remove-orphans
docker compose up -d mongo postgres minio
# Attendre que mongo et postgres soient healthy, puis continuer le demarrage par etapes
# (voir section Demarrage), puis :
docker compose exec backend-api python /app/pipeline/classification/train.py
docker compose exec backend-api python /app/scripts/seed.py
```

---

## Stack technique

| Couche | Technologies |
|--------|-------------|
| API | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| Auth | JWT (python-jose), bcrypt, RBAC 3 niveaux |
| Base de donnees | MongoDB 7 (Motor async + PyMongo sync) |
| Stockage fichiers | MinIO S3-compatible (3 zones : raw / clean / curated) |
| OCR | Tesseract 5, OpenCV 4, pdfplumber, pdf2image |
| ML | scikit-learn — TF-IDF + Random Forest |
| Orchestration | Apache Airflow 2.8 (DAG par document, jusqu'a 20 en parallele) |
| Frontends | React 18, Vite 5, Tailwind CSS v4, TanStack Query v5 |
| Infra | Docker Compose, Nginx, structlog |
