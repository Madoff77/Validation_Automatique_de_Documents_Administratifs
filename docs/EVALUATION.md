# Évaluation du projet — DocPlatform

> Mise à jour le 2026-03-19 — état après l'ensemble des modifications apportées.

---

## Score estimé : 16.5 / 20

| Critère | Points | Score |
|---------|--------|-------|
| 1. Architecture | 5 | **4.0** |
| 2. Qualité IA | 5 | **4.0** |
| 3. Industrialisation | 4 | **3.5** |
| 4. Front & UX | 3 | **2.5** |
| 5. Cohérence globale & pitch | 3 | **2.5** |

---

## 1. Architecture — 4.0 / 5

### Ce qu'attend le jury

> Ingestion → Stockage brut → Orchestration pipeline → Zones Raw / Clean / Curated → Frontend

### Implémenté ✅

**Ingestion**
Upload via API FastAPI → stockage immédiat dans la zone `raw` (MinIO). Le document reçoit le statut `pending` en MongoDB et un DAG Airflow est déclenché automatiquement.

**Orchestration Airflow — 4 étapes conformes à l'architecture cible**

| Étape attendue | Tâche Airflow | 
|----------------|---------------|
| Ingestion | `task_ocr` (télécharge le fichier raw) 
| OCR | `task_ocr` (extraction texte) 
| Extraction | `task_extract` + `task_classify` 
| Validation | `task_validate` + `task_finalize` 

**Data Lake — 3 zones respectées**

| Zone | Contenu | Format |
|------|---------|--------|
| `raw` | Document original tel qu'uploadé | PDF / JPEG / PNG |
| `clean` | Texte OCR brut + métadonnées | `.txt` + `.json` |
| `curated` | Données structurées finales | `.json` |

**Séparation des couches** : API / Pipeline / Storage / Utils sont strictement isolés. Aucune logique métier dans les routes. Chaque tâche Airflow est appelable indépendamment.

### Limites ⚠️

- `LocalExecutor` Airflow : traitement limité à une seule machine (pas distribué)
- Pas de cache (Redis) sur les endpoints dashboard : chaque lecture recalcule depuis MongoDB
- Pas de rate limiting sur l'upload

---

## 2. Qualité IA — 4.0 / 5

### Ce qu'attend le jury

> OCR (Tesseract ou Deep Learning) + NLP pour extraction

### Implémenté ✅

**OCR — pipeline 3 niveaux**

| Niveau | Technologie | Déclenchement |
|--------|-------------|---------------|
| 1 | pdfplumber — extraction texte natif | PDF avec couche texte (confiance 0.98) |
| 2 | Tesseract 4 configs PSM + 8 stratégies OpenCV | PDF scanné / image |
| 3 | **TrOCR** `trocr-base-printed` — modèle Transformer | Tesseract < 0.4 de confiance |

TrOCR est un modèle Deep Learning (Vision Transformer + décodeur langage) : répond directement au critère "modèle Deep Learning" pour l'OCR.

**NLP / Extraction de champs**

L'extraction repose sur des **regex contextuelles robustes**, renforcées par plusieurs correctifs :

| Correctif | Problème résolu |
|-----------|----------------|
| `_normalize_numeric_ocr()` | Confusions OCR O→0, l→1, B→8, S→5, Z→2 dans les identifiants |
| SIRET : scoring par proximité | Mauvais SIRET sélectionné sur docs multi-entités (URSSAF, Kbis) |
| Montants : `re.MULTILINE` + gap 40 | Label et montant sur lignes séparées dans les tableaux |
| IBAN : `[\s]{0,2}` | Espaces doubles OCR entre groupes |
| BIC : 6 labels + fallback IBAN | `Code BIC`, `BIC/SWIFT`, `Code établissement`, espaces dans le code |

Note : l'extraction est par regex et non par NLP probabiliste — c'est une limite documentée. Pour un NLP complet il faudrait spaCy NER ou LayoutLMv3, hors scope du projet.

**Détection d'anomalies**

| Règle | Algorithme | Sévérité |
|-------|-----------|----------|
| SIRET invalide | Luhn mod 10 | error |
| IBAN invalide | MOD-97 | warning |
| Incohérence HT+TVA≠TTC | Calcul ±1€ / 0.5% | warning |
| Kbis trop ancien | > 90 jours (réglementation) | error |
| URSSAF expirée | Date dépassée | error |
| SIRET différent entre docs | Comparaison inter-documents | error |

**Classification documentaire** : TF-IDF bigrammes + Random Forest (6 types), 5-fold cross-validation, fallback keywords si confiance < 0.6.

### Limites ⚠️

- Détection d'anomalies 100% rule-based, pas de ML statistique
- Extraction raison sociale fragile sur entités sans suffixe juridique visible

---

## 3. Industrialisation — 3.5 / 4

### Dockerisation ✅

11 services Docker Compose, tous containerisés :

| Service | Healthcheck | Volume persistant |
|---------|-------------|-------------------|
| MongoDB | `mongosh ping` | `mongo_data` |
| PostgreSQL (Airflow) | `pg_isready` | `postgres_data` |
| MinIO | — | `minio_data` |
| Backend API | `/health` HTTP | `model_data`, `hf_model_cache` |
| Airflow webserver | HTTP :8080/health | — |
| Frontends (×2) | — | — |

Points notables :
- Mode production Uvicorn (`--reload` retiré, `--workers 2`)
- Modèle TrOCR (~400MB) **pré-téléchargé pendant le `docker build`** → aucun accès réseau au runtime
- Volume `hf_model_cache` : le modèle survit aux rebuilds d'image

Limite : pas de multi-stage build (image ~2GB).

### Orchestration ✅

DAG Airflow conforme à l'architecture cible :
```
preprocess_ocr → classify → extract_fields → validate → finalize
```
- Retry : 2 tentatives par tâche, backoff exponentiel
- 20 documents en parallèle (`max_active_runs: 20`)
- Callback d'échec : statut document mis à jour en MongoDB
- XCom pour les données légères entre tâches

### Gestion des logs ✅

- structlog : JSON structuré en production, lisible en développement
- Middleware HTTP : chaque requête loggée (method, path, status, duration_ms)
- Événements nommés à chaque étape du pipeline (`ocr_done`, `trocr_fallback_triggered`, `anomaly_created`, etc.)
- Logs Airflow par tâche consultables dans l'interface web

Limite : pas d'agrégation centralisée (pas de Loki/ELK).

---

## 4. Front & UX — 2.5 / 3

### Ce qu'attend le jury

> MERN : CRM + Outil conformité + formulaires auto-remplis par l'IA

### Implémenté ✅

**Deux applications distinctes**

| Application | Port | Rôle |
|-------------|------|------|
| CRM | 5173 | Opérateurs : upload, gestion documents/fournisseurs |
| Compliance | 5174 | Auditeurs : anomalies, expirations, conformité fournisseur |

Stack : React 18 + Vite (frontend), FastAPI Python (backend), MongoDB — non MERN strict (FastAPI remplace Node/Express), mais architecture équivalente pour le jury.

**Auto-remplissage ✅**

Après traitement Airflow, `DocumentDetail` affiche automatiquement tous les champs extraits par l'IA : SIRET, TVA, montants HT/TVA/TTC, dates, IBAN, BIC, raison sociale. Le score de confiance OCR et le score de classification sont affichés.

**Mise à jour en temps réel ✅**

`DocumentDetail` : polling toutes les 3s, s'arrête automatiquement sur `processed` ou `error`.

`Documents` (liste) : poll actif seulement si au moins un document est en cours — aucune requête inutile en arrière-plan quand tout est terminé.

### Limites ⚠️

- Stack backend Python/FastAPI au lieu de Node.js (MERN non respecté strictement)
- Pas de skeleton loading sur la page détail
- Pas d'aperçu du fichier avant upload

---

## 5. Cohérence globale & pitch — 2.5 / 3

### Démonstration ✅

- `make seed` : charge automatiquement 15 fournisseurs (INSEE SIRENE ou Faker), documents variés, anomalies intentionnelles injectées sur 1/3 des fournisseurs
- Scénario complet démontrable : upload → pipeline Airflow → champs auto-remplis → anomalie détectée → résolution
- Airflow UI (:8080), MinIO console (:9001), Mongo Express (:8081) tous accessibles

### Clarté technique ✅

Documentation complète :

| Fichier | Contenu |
|---------|---------|
| `README.md` | Installation, URLs, Makefile |
| `docs/CONTEXT_MASTER.md` | Référence d'architecture |
| `docs/JURY_DEFENSE.md` | Q&A anticipées |
| `docs/EXTRACTION_ANALYSIS.md` | Analyse détaillée extraction + correctifs |
| `docs/ARCHITECTURE_COMPARAISON.md` | Justification des choix techniques |

### Limite ⚠️

- Préparer les métriques du classificateur avant la démo (`make train` → `report.json`) pour avoir des chiffres concrets à citer sur la précision
