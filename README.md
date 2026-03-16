# DocPlatform — Plateforme de Traitement Intelligent de Documents Administratifs

Projet académique S19 — IPSSI
Pipeline complet d'OCR, classification ML et validation de documents administratifs français (Factures, Devis, Kbis, URSSAF, Attestation SIRET, RIB).

---

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Lancer la stack](#4-lancer-la-stack)
5. [Initialiser les données](#5-initialiser-les-données)
6. [Entraîner le modèle ML](#6-entraîner-le-modèle-ml)
7. [Accéder aux interfaces](#7-accéder-aux-interfaces)
8. [Utilisation pas à pas](#8-utilisation-pas-à-pas)
9. [Commandes utiles](#9-commandes-utiles)
10. [Architecture](#10-architecture)
11. [Pipeline de traitement](#11-pipeline-de-traitement)
12. [Structure du projet](#12-structure-du-projet)
13. [API — Endpoints](#13-api--endpoints)
14. [Dépannage](#14-dépannage)
15. [Technologies](#15-technologies)

---

## 1. Prérequis

Avant de commencer, vérifier que les outils suivants sont installés :

| Outil | Version minimale | Vérification |
|-------|-----------------|--------------|
| Docker Desktop | 24.0 | `docker --version` |
| Docker Compose | 2.20 | `docker compose version` |
| Make | any | `make --version` |

> **RAM Docker** : Allouer **au moins 4 Go** à Docker Desktop.
> Sur Windows/Mac : Docker Desktop → Settings → Resources → Memory → 4096 MB minimum.

**Windows** : S'assurer que WSL2 est activé et que Docker utilise le backend WSL2.

> **Contraintes mémoire** : Si la machine est limitée en RAM, il est possible de démarrer les services par groupe (voir section [Démarrage partiel](#démarrage-partiel)).

---

## 2. Installation

### Cloner le projet

```bash
git clone repo
```

### Vérifier Docker

```bash
docker info
# Doit afficher les informations du daemon sans erreur
```

---

## 3. Configuration

Copier le fichier d'environnement exemple :

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
```

Le fichier `.env` contient toutes les variables de configuration. Les valeurs par défaut fonctionnent pour un environnement local sans modification.

### Variables importantes

```env
# MongoDB
MONGO_ROOT_USER=root
MONGO_ROOT_PASSWORD=rootpassword
MONGO_DB=docplatform

# MinIO (stockage fichiers)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# JWT — CHANGER EN PRODUCTION
JWT_SECRET_KEY=supersecretkey_change_in_production_please

# Airflow
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
```

> Pour générer une vraie clé JWT : `openssl rand -hex 32`

---

## 4. Lancer la stack

```bash
make up
```

### Démarrage complet

Cette commande démarre tous les services Docker :

| Service | Rôle | Port |
|---------|------|------|
| `mongo` | Base de données principale | 27017 |
| `mongo-express` | Interface web MongoDB | 8081 |
| `postgres` | Base Airflow | 5432 |
| `minio` | Stockage objets S3-compatible | 9000 / 9001 |
| `minio-init` | Création des buckets raw/clean/curated | one-shot |
| `airflow-init` | Initialisation DB Airflow + user admin | one-shot |
| `airflow-webserver` | Interface Airflow | 8080 |
| `airflow-scheduler` | Planificateur DAGs | — |
| `backend-api` | API FastAPI | 8000 |
| `frontend-crm` | Interface opérateurs | 5173 |
| `frontend-compliance` | Interface conformité | 5174 |

### Démarrage partiel

Sur les machines avec peu de RAM (< 8 Go), démarrer les services par groupe :

```bash
# Groupe 1 — Socle (obligatoire)
docker compose up -d mongo minio minio-init backend-api

# Groupe 2 — Interfaces (ajouter selon besoin)
docker compose up -d frontend-crm frontend-compliance mongo-express

# Groupe 3 — Airflow (lourd, optionnel pour la démo)
docker compose up -d postgres airflow-init airflow-webserver airflow-scheduler
```

### Vérifier que tout est prêt

```bash
docker compose ps

# Tester le backend
curl http://localhost:8000/health
# Réponse attendue : {"status":"ok"}
```

---

## 5. Initialiser les données

Une fois la stack démarrée, peupler la base avec les données de démonstration :

```bash
make seed
# ou directement :
docker compose exec backend-api python /app/scripts/seed.py
```

Cette commande crée :
- **3 utilisateurs** : admin, operator, viewer (avec rôles distincts)
- **3 fournisseurs** : BTP SOLUTIONS SAS, TECHNO SERVICES EURL, CONSEIL & CO SARL
- **11 documents** traités avec le pipeline complet, incluant des anomalies intentionnelles :
  - SIRET invalide
  - Document expiré (URSSAF)
  - Kbis trop ancien (> 90 jours)
  - Incohérence inter-documents

> Le seed est idempotent : relancer `make seed` ne crée pas de doublons.

---

## 6. Entraîner le modèle ML

```bash
make train
```

Cette commande :
1. Génère des documents synthétiques (par type : FACTURE, DEVIS, KBIS, URSSAF, SIRET, RIB)
2. Entraîne le **TF-IDF + RandomForest** avec validation croisée
3. Sauvegarde `classifier.joblib` et `vectorizer.joblib`

> Si cette étape est sautée, le système utilise automatiquement le **classifieur par mots-clés** (fallback), fonctionnel mais moins précis.

---

## 7. Accéder aux interfaces

| Interface | URL | Identifiants |
|-----------|-----|--------------|
| **Frontend CRM** | http://localhost:5173 | admin / admin123 |
| **Frontend Compliance** | http://localhost:5174 | admin / admin123 |
| **API Swagger** | http://localhost:8000/docs | — |
| **Airflow** | http://localhost:8080 | admin / admin |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **Mongo Express** | http://localhost:8081 | admin / admin |

### Comptes utilisateurs

| Rôle | Utilisateur | Mot de passe | Permissions |
|------|-------------|--------------|-------------|
| Admin | `admin` | `admin123` | Tout + gestion utilisateurs |
| Opérateur | `operator` | `operator123` | Upload, édition, résolution anomalies |
| Viewer | `viewer` | `viewer123` | Lecture seule — aucune action d'écriture |

### Permissions par rôle

| Action | viewer | operator | admin |
|--------|:------:|:--------:|:-----:|
| Consulter documents / fournisseurs / anomalies | ✅ | ✅ | ✅ |
| Uploader un document | ❌ | ✅ | ✅ |
| Créer / modifier un fournisseur | ❌ | ✅ | ✅ |
| Résoudre une anomalie | ❌ | ✅ | ✅ |
| Relancer le pipeline | ❌ | ✅ | ✅ |
| Créer des utilisateurs | ❌ | ❌ | ✅ |

> Le backend valide chaque action. Le frontend masque les boutons non autorisés selon le rôle pour une meilleure expérience utilisateur.

---

## 8. Utilisation

### Scénario 1 — Uploader et traiter un document (Frontend CRM)

1. Ouvrir **http://localhost:5173**
2. Se connecter avec `operator` / `operator123`
3. Cliquer sur **"Upload"** dans le menu gauche
4. Sélectionner un fournisseur dans la liste déroulante
5. Glisser-déposer un fichier PDF ou image (facture, kbis, rib...)
6. Cliquer **"Uploader"** — le pipeline démarre automatiquement
7. Aller dans **"Documents"** pour suivre le statut en temps réel :
   - `pending` → en attente
   - `preprocessing` → OCR en cours
   - `classified` → type détecté
   - `extracted` → champs extraits
   - `validated` → validation terminée
   - `processed` → pipeline complet
   - `error` → erreur (relançable)
8. Cliquer sur le document pour voir les **champs extraits** et les **anomalies détectées**

### Scénario 2 — Surveiller la conformité (Frontend Compliance)

1. Ouvrir **http://localhost:5174**
2. Se connecter avec `admin` / `admin123`
3. **Tableau de bord** : vue globale avec graphique de répartition et anomalies récentes
4. **Anomalies** : liste filtrée par sévérité/type, résolution inline avec notes
5. **Expirations** : documents expirant dans les 30 jours, triés par urgence
6. **Fournisseurs** : statut de conformité par fournisseur, clic pour le détail

### Scénario 3 — Inspecter le pipeline Airflow

1. Ouvrir **http://localhost:8080**
2. Se connecter avec `admin` / `admin`
3. Cliquer sur le DAG **`document_pipeline`**
4. Voir les runs récents, les logs de chaque tâche, les temps d'exécution

### Scénario 4 — Lancer la démo automatique

```bash
make demo
```

---

## 9. Commandes utiles

```bash
# Démarrage / arrêt
make up          # Démarrer tous les services
make down        # Arrêter (sans supprimer les volumes)
make restart     # Redémarrer tous les services
make clean       # Arrêter ET supprimer volumes + données

# Développement
make logs        # Logs en temps réel de tous les services
make build       # Rebuild les images Docker (après modification du code)

# Données
make seed        # Peupler la base avec les données de démo
make train       # Entraîner le modèle ML
make demo        # Scénario de démonstration automatique

# Logs d'un service spécifique
docker compose logs -f backend-api
docker compose logs -f airflow-scheduler

# Accéder au shell d'un container
docker compose exec backend-api bash
docker compose exec mongo mongosh -u root -p rootpassword

# Relancer un seul service
docker compose restart backend-api
```

---

## 10. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose Stack                         │
│                                                                       │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │ frontend-crm │  │ frontend-        │  │     backend-api        │ │
│  │  :5173       │  │ compliance :5174 │  │     FastAPI :8000      │ │
│  │  React/Vite  │  │ React/Vite       │  │     JWT + RBAC         │ │
│  └──────┬───────┘  └────────┬─────────┘  └──────────┬────────────┘ │
│         │                   │                        │               │
│         └───────────────────┴────────────────────────┤              │
│                                                       │              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────▼───────────┐  │
│  │   MongoDB    │  │    MinIO     │  │        Airflow            │  │
│  │   :27017     │  │   :9000      │  │        :8080              │  │
│  │  4 collections│  │  3 buckets  │  │  DAG: document_pipeline   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                  Pipeline OCR → ML → Validation                 │ │
│  │  Upload → OCR (7 stratégies) → TF-IDF+RF → Regex → Rules       │ │
│  │        Tesseract   Laplacian    200 arbres  Luhn/MOD-97         │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Stockage MinIO — 3 buckets

| Bucket | Contenu | Format |
|--------|---------|--------|
| `raw` | Fichiers originaux uploadés | PDF / PNG / JPG / TXT |
| `clean` | Texte extrait par OCR + métadonnées | `.txt`, `.json` |
| `curated` | Données structurées finales | `.json` |

### MongoDB — 4 collections

| Collection | Contenu |
|------------|---------|
| `users` | Comptes utilisateurs + hash bcrypt |
| `suppliers` | Fournisseurs + statut de conformité |
| `documents` | Métadonnées + champs extraits + résultat validation |
| `anomalies` | Anomalies détectées + statut résolution |

---

## 11. Pipeline de traitement

```
┌─────────┐
│  UPLOAD │  Fichier → MinIO bucket "raw"
│         │  Métadonnées → MongoDB (status: pending)
│         │  Déclenchement pipeline (Airflow ou synchrone)
└────┬────┘
     │
┌────▼────┐
│   OCR   │  PDF natif → pdfplumber (rapide, conf. 0.98)
│         │  Scan/Image → OpenCV + Tesseract 5
│         │  Texte brut (.txt) → lecture directe (conf. 1.0)
│         │  7 stratégies adaptatives selon score Laplacien
└────┬────┘
     │
┌────▼──────────┐
│  CLASSIFICATION│  Normalisation texte (SIRET, montants, dates)
│               │  TF-IDF + RandomForest (200 arbres)
│               │  Fallback mots-clés si modèle absent ou confiance < 0.6
└────┬──────────┘
     │
┌────▼────────┐
│  EXTRACTION │  Regex compilées : SIRET, TVA, IBAN, montants, dates
│             │  Heuristique suffixes juridiques : raison sociale
│             │  Déduction croisée : si 2 montants connus → 3e calculé
└────┬────────┘
     │
┌────▼──────────┐
│  VALIDATION   │  SIRET : algorithme de Luhn
│               │  IBAN  : MOD-97
│               │  TVA   : clé = (12 + 3×SIREN%97)%97
│               │  Cohérence : montant_ht × taux ≈ montant_tva (±1€)
│               │  Kbis : âge < 90 jours (obligation légale)
│               │  Expiration : alerte si < 30 jours
│               │  Inter-docs : SIRET cohérent entre docs du fournisseur
│               │  → Création anomalies MongoDB
│               │  → Mise à jour compliance_status fournisseur
└────┬──────────┘
     │
┌────▼──────────┐
│  FINALISATION │  JSON structuré → MinIO bucket "curated"
│               │  document.status = "processed" ou "error"
└───────────────┘
```

---

## 12. Structure du projet

```
S19_Hackathton/
│
├── backend/                        # API FastAPI + Pipeline
│   ├── api/
│   │   ├── main.py                 # Point d'entrée FastAPI
│   │   ├── config.py               # Settings (Pydantic, lecture .env)
│   │   ├── dependencies.py         # get_current_user, require_roles
│   │   ├── auth/
│   │   │   ├── jwt_handler.py      # Création/vérification tokens JWT
│   │   │   └── password.py         # Bcrypt hash/verify
│   │   ├── models/
│   │   │   └── schemas.py          # Schémas Pydantic (request/response)
│   │   └── routes/
│   │       ├── auth.py             # Login, refresh, logout, /me
│   │       ├── documents.py        # Upload, list, get, reprocess
│   │       ├── suppliers.py        # CRUD + compliance
│   │       ├── anomalies.py        # List, resolve, expiring-soon
│   │       └── stats.py            # Dashboard stats
│   │
│   ├── pipeline/
│   │   ├── processor.py            # Orchestrateur sync des 5 tâches
│   │   ├── ocr/
│   │   │   ├── preprocessor.py     # 7 stratégies OpenCV adaptatives
│   │   │   └── extractor.py        # pdfplumber + Tesseract + plain_text
│   │   ├── classification/
│   │   │   ├── classifier.py       # TF-IDF + RF + fallback keywords
│   │   │   └── train.py            # Entraînement + cross-validation
│   │   ├── extraction/
│   │   │   └── field_extractor.py  # Regex + heuristique suffixes juridiques
│   │   └── validation/
│   │       └── validator.py        # Luhn, MOD-97, TVA, cohérence, inter-docs
│   │
│   ├── storage/
│   │   ├── mongo_client.py         # Client async Motor (API) + sync PyMongo (pipeline)
│   │   └── minio_client.py         # Client MinIO (upload/download/presign)
│   │
│   ├── utils/
│   │   └── logger.py               # structlog JSON
│   │
│   ├── requirements.txt
│   └── Dockerfile
│
├── airflow/
│   ├── dags/
│   │   └── document_pipeline_dag.py  # DAG 5 tâches + retry backoff
│   ├── Dockerfile
│   └── requirements.txt
│
├── data-generator/
│   └── generator.py                # Générateur docs synthétiques (optionnel)
│
├── frontend-crm/                   # Interface opérateurs (React + Vite)
│   ├── src/
│   │   ├── api/                    # Axios + intercepteur auto-refresh JWT
│   │   ├── contexts/               # AuthContext (user, login, logout)
│   │   ├── hooks/
│   │   │   └── usePermissions.js   # Permissions UX centralisées par rôle
│   │   ├── components/             # Layout, Sidebar, StatusBadge
│   │   └── pages/
│   │       ├── Dashboard.jsx       # Stats + documents récents
│   │       ├── Upload.jsx          # Dropzone multi-fichiers (operator+)
│   │       ├── Documents.jsx       # Table filtrée
│   │       ├── DocumentDetail.jsx  # Champs extraits + validations
│   │       ├── Suppliers.jsx       # Liste fournisseurs
│   │       └── SupplierDetail.jsx  # Détail + auto-fill depuis docs
│   └── Dockerfile / nginx.conf
│
├── frontend-compliance/            # Interface conformité (React + Vite)
│   ├── src/
│   │   ├── api/
│   │   ├── contexts/               # AuthContext
│   │   ├── hooks/
│   │   │   └── usePermissions.js   # Permissions UX centralisées par rôle
│   │   ├── components/
│   │   └── pages/
│   │       ├── Dashboard.jsx       # PieChart + anomalies récentes
│   │       ├── Anomalies.jsx       # Table filtrée + résolution inline (operator+)
│   │       ├── Expirations.jsx     # Traffic-light par urgence
│   │       ├── Suppliers.jsx       # Conformité globale
│   │       └── SupplierCompliance.jsx  # Drill-down par fournisseur
│   └── Dockerfile / nginx.conf
│
├── scripts/
│   ├── seed.py                     # Données de démonstration (idempotent)
│   └── demo.sh                     # Scénario de démo automatique
│
├── docker/
│   └── mongo-init.js               # Index MongoDB au démarrage
│
├── docs/
│   ├── CONTEXT_MASTER.md           # Architecture et décisions techniques
│   └── CHANGELOG_IMPLEMENTATION.md # Journal des modifications
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── Makefile
└── README.md
```

---

## 13. API — Endpoints

Documentation interactive complète : **http://localhost:8000/docs**

### Authentification

```
POST   /auth/login              { username, password } → { access_token, refresh_token }
POST   /auth/refresh            { refresh_token } → { access_token, refresh_token }
POST   /auth/logout             Invalide le refresh token
GET    /auth/me                 Profil utilisateur courant
POST   /auth/register           Créer un utilisateur (admin only)
```

### Documents

```
POST   /documents/upload        Multipart: file + supplier_id + doc_type  [operator+]
GET    /documents               ?status=&doc_type=&supplier_id=&limit=&skip=
GET    /documents/{id}          Détail complet + extracted_fields + validation
GET    /documents/{id}/download Redirect vers presigned URL MinIO
POST   /documents/{id}/reprocess Relancer le pipeline  [operator+]
DELETE /documents/{id}          Suppression  [admin]
```

### Fournisseurs

```
GET    /suppliers               ?search=&limit=&skip=
POST   /suppliers               Créer { name, siret, ... }  [operator+]
GET    /suppliers/{id}          Détail fournisseur
PUT    /suppliers/{id}          Mettre à jour  [operator+]
DELETE /suppliers/{id}          Supprimer  [admin]
GET    /suppliers/{id}/compliance  Statut conformité détaillé
```

### Anomalies

```
GET    /anomalies               ?severity=&type=&resolved=&supplier_id=&limit=
PATCH  /anomalies/{id}/resolve  { resolution_notes }  [operator+]
GET    /anomalies/expiring-soon Documents expirant dans les 30 prochains jours
```

### Stats

```
GET    /stats/dashboard         { total_suppliers, unresolved_anomalies, ... }
GET    /health                  { status: "ok" }
```

---

## 14. Dépannage

### Les services ne démarrent pas

```bash
# Vérifier que les ports ne sont pas déjà utilisés
netstat -an | grep -E "8000|8080|9000|27017|5432|5173|5174"

# Voir les logs d'un service en erreur
docker compose logs mongo
docker compose logs backend-api
```

### `make seed` échoue

```bash
# Vérifier que le backend est bien démarré
curl http://localhost:8000/health

# Relancer directement
docker compose exec backend-api python /app/scripts/seed.py
```

### Le pipeline reste en `processing`

```bash
# Vérifier les logs Airflow
docker compose logs airflow-scheduler

# Voir dans l'UI : http://localhost:8080 → DAG document_pipeline
```

### Erreur de connexion MongoDB

```bash
# Tester la connexion
docker compose exec mongo mongosh -u root -p rootpassword --eval "db.adminCommand('ping')"

# Recréer les volumes si corrompu
make clean && make up
```

### Modèle ML non chargé (classification par mots-clés utilisée)

```bash
# Entraîner le modèle
make train

# Vérifier la présence des fichiers
docker compose exec backend-api ls /app/models/trained/
```

### Réinitialiser complètement

```bash
make clean      # Supprime tout (volumes, containers, données)
make up         # Repart de zéro
make seed       # Recharge les données
make train      # Réentraîne le modèle
```

---

## 15. Technologies

| Couche | Technologies |
|--------|-------------|
| **API** | Python 3.11, FastAPI-slim, Uvicorn, Pydantic v2 |
| **Auth** | python-jose JWT, bcrypt/passlib, RBAC (admin/operator/viewer) |
| **Base de données** | MongoDB 7 (Motor async + PyMongo sync), Mongo Express |
| **Stockage** | MinIO S3-compatible, 3 buckets (raw/clean/curated) |
| **OCR** | OpenCV 4, Tesseract 5 (fr+eng), pdfplumber, pdf2image |
| **ML** | scikit-learn (TF-IDF + RandomForest), fallback keyword rules |
| **Orchestration** | Apache Airflow 2.8 (LocalExecutor, REST API trigger) |
| **Frontends** | React 18, Vite 5, Tailwind CSS 3, TanStack Query v5 |
| **Permissions UI** | `usePermissions()` hook centralisé (canUpload, canEdit, ...) |
| **UI libs** | Recharts, React Router v6, Lucide React, react-hot-toast |
| **HTTP client** | Axios (intercepteur auto-refresh JWT) |
| **Infra** | Docker Compose, Nginx, structlog (JSON logging) |
| **Dev** | Faker (données synthétiques), python-stdnum (validation SIRET/IBAN) |
