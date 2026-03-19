# Évaluation du projet — DocPlatform

> Analyse réalisée le 2026-03-19 sur la base du code source complet.
> Barème total : **20 points**

---

## Score estimé global : 15.5 / 20

| Critère | Pondération | Score estimé | Détail |
|---------|-------------|--------------|--------|
| Architecture | 5 pts | **4.0 / 5** | Solide, quelques lacunes prod |
| Qualité IA | 5 pts | **3.5 / 5** | OCR robuste, extraction regex-only |
| Industrialisation | 4 pts | **3.5 / 4** | Docker complet, logs OK, pas de monitoring |
| Front & UX | 3 pts | **2.0 / 3** | Clean, mais pas de temps réel |
| Cohérence & pitch | 3 pts | **2.5 / 3** | Bien documenté, démo solide |

---

## 1. Architecture — 4.0 / 5

### Points forts

**Séparation des couches : excellente**
- Découpage net entre `api/` (routes, auth), `pipeline/` (OCR, classification, extraction, validation), `storage/` (MongoDB, MinIO), `utils/` (logging)
- Chaque tâche du pipeline est **indépendante et appelable seule** (via Airflow ou directement)
- Pattern data lake cohérent : `raw → clean → curated` dans MinIO — exactement ce qu'un jury technique attend
- Aucune logique métier dans les routes API

**Robustesse : bonne**
- Multi-niveaux OCR : extraction native PDF → Tesseract multi-pass → TrOCR fallback
- Retry Airflow (2 tentatives, backoff exponentiel jusqu'à 10 min)
- Callback d'échec en Airflow qui met à jour le statut document en MongoDB
- 8 stratégies de preprocessing OpenCV avec sélection automatique du meilleur résultat
- Statuts document granulaires (`pending → preprocessing → ocr_done → classified → extracted → validated → processed | error`)

**Scalabilité : correcte**
- FastAPI async (pas de blocage sur les appels I/O longs)
- Airflow `max_active_runs: 20` — traitement parallèle documenté
- MinIO S3-compatible → migration AWS S3 sans refactoring
- MongoDB schéma flexible (différents champs extraits selon le type de document)

### Points faibles

| Faiblesse | Impact | Sévérité |
|-----------|--------|----------|
| `uvicorn --reload` dans le CMD Dockerfile | Mode développement en production | Moyen |
| `./backend:/app` monté en volume — écrase l'image | Risque d'incohérence entre image buildée et runtime | Faible (hackathon) |
| Pas de cache (Redis) — toutes les lectures frappent MongoDB | Goulot d'étranglement sur les endpoints stats/dashboard | Moyen |
| `LocalExecutor` Airflow — limité à 1 machine | Non distribué, pas scalable horizontalement | Faible (acceptable) |
| Pas de rate limiting sur l'API | Upload massif possible, pas de protection | Moyen |
| Pas de circuit breaker pour les appels MinIO/MongoDB | Cascade d'erreurs si une dépendance tombe | Faible |

### Propositions d'amélioration

```
# 1. Retirer --reload en prod
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
#    ↑ workers=4 pour utiliser plusieurs CPU

# 2. Rate limiting (1 ligne avec slowapi)
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
@router.post("/upload")
@limiter.limit("10/minute")
async def upload_document(...): ...

# 3. Cache Redis pour les stats (TTL 30s)
# Les stats dashboard peuvent être cachées — pas besoin de recalculer à chaque requête
```

---

## 2. Qualité IA — 3.5 / 5

### Points forts

**OCR : robuste et bien pensé**
- 3 niveaux : pdfplumber (natif) → Tesseract 4 configs PSM → TrOCR Transformer (fallback)
- 8 stratégies OpenCV avec scoring automatique (`_score_preprocessed` via Laplacian + ratio noir/blanc)
- Early stop Tesseract à 0.65 de confiance — efficace
- Correction post-OCR des artefacts français courants (`§IRET → SIRET`, `TVl → TVA`, etc.)
- Reconstruction de la structure ligne/colonne par regroupement `(block_num, par_num, line_num)` — évite les regex montants sur les mauvaises valeurs

**Classification : méthodologie correcte**
- TF-IDF bigrammes (8000 features) + Random Forest 200 arbres
- Fallback par règles keywords si confiance < 0.6 ou modèle absent
- 5-fold cross-validation, split stratifié 80/20, random_state=42 (reproductible)
- Pipeline de génération réaliste : texte template → image → dégradation → Tesseract → dataset

**Validation : exhaustive**
- Luhn sur SIRET (checksum réel, pas juste 14 chiffres)
- MOD-97 sur IBAN
- Cohérence TVA calculée depuis SIREN
- Cohérence montants HT × (1 + taux) ≈ TTC (tolérance ±1€ ou 0.5%)
- Détection inter-documents : incohérence SIRET, expiration URSSAF/Kbis (<90j), doublons
- 3 niveaux de sévérité (`error / warning / info`)

### Points faibles

| Faiblesse | Impact | Sévérité |
|-----------|--------|----------|
| Extraction uniquement par regex — pas de NLP/NER | Raison sociale et adresse extraites par heuristics fragiles | Élevé |
| Pas de score de confiance par champ extrait | Impossible de savoir si `montant_ttc` est fiable ou incertain | Moyen |
| 150 exemples/classe seulement (900 total) | Dataset très petit, risque de surapprentissage | Moyen |
| Pas de MLflow / experiment tracking | Pas de comparaison de runs, pas de versioning modèle | Faible |
| Détection d'anomalies 100% rule-based | Pas de ML pour détecter des patterns inhabituels | Moyen |
| TrOCR `trocr-base-printed` entraîné majoritairement sur l'anglais | Perte de précision sur les documents administratifs français | Moyen |

### Propositions d'amélioration

**Court terme (avant démo)**
- Ajouter un champ `extraction_confidence` par champ dans `extracted` — même approximatif (ex: nombre de regex qui matchent sur le même texte)
- Utiliser `trocr-base-handwritten` en supplément pour les tampons manuels sur URSSAF/Kbis

**Moyen terme**
```python
# Remplacer l'extraction raison_sociale par spaCy NER
import spacy
nlp = spacy.load("fr_core_news_sm")
doc = nlp(ocr_text)
companies = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
```

**Pour le pitch** — répondre à la question "comment amélioreriez-vous le modèle ?" :
> "Avec plus de temps, on passerait à LayoutLMv3 (Microsoft) qui comprend à la fois le texte ET la mise en page du document — c'est l'état de l'art pour l'extraction structurée de formulaires."

---

## 3. Industrialisation — 3.5 / 4

### Points forts

**Dockerisation : quasi-parfaite**
- 11 services orchestrés, tous containerisés
- Healthchecks sur MongoDB, PostgreSQL, Airflow webserver, API backend
- `depends_on` avec conditions (`service_healthy`) — ordre de démarrage garanti
- Volumes nommés persistants pour toutes les données
- Modèle TrOCR pré-téléchargé au build → pas de réseau au runtime
- Volume `hf_model_cache` partagé → pas de re-téléchargement entre rebuilds
- Makefile avec commandes shortcut (`make up/down/train/seed/logs/clean`)

**Orchestration : bonne**
- Airflow DAG bien structuré, 5 tâches linéaires
- XCom pour passer les données légères entre tâches
- Callback d'échec qui met à jour MongoDB — statut document cohérent
- Mode développement : fallback sur dernier document `pending` si pas de `document_id` en conf

**Logs : structurés et cohérents**
- structlog JSON en production, pretty-print en dev
- Middleware de logging HTTP (method, path, status, duration_ms)
- Événements nommés par contexte (`ocr_done`, `trocr_fallback_triggered`, `anomaly_created`)
- Logs Airflow par tâche, consultables dans l'interface web

### Points faibles

| Faiblesse | Impact | Sévérité |
|-----------|--------|----------|
| Pas de multi-stage build Docker | Image backend ~2GB (prod + dev deps mélangés) | Faible |
| `uvicorn --reload` dans CMD | Surveille les fichiers système → RAM + CPU inutile | Moyen |
| Pas de `.dockerignore` backend | Copie `node_modules`, `.git`, etc. dans l'image si présents | Faible |
| Pas d'agrégation de logs (ELK, Loki) | Logs perdus si conteneur redémarre | Moyen |
| Pas de métriques applicatives (Prometheus/Grafana) | Impossible de voir latence OCR, taux d'erreur, etc. sur un graphe | Moyen |
| Pas d'alerting (email, Slack) sur anomalies critiques | Les erreurs `error` ne notifient personne | Faible |

### Propositions d'amélioration

**Immédiat (5 min)**
```dockerfile
# backend/Dockerfile — retirer --reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Multi-stage build (améliore le score si mentionné au jury)**
```dockerfile
# Stage 1 : dépendances
FROM python:3.11-slim AS builder
RUN pip install --prefix=/install -r requirements.txt

# Stage 2 : runtime (sans pip, sans cache)
FROM python:3.11-slim
COPY --from=builder /install /usr/local
COPY . .
# → image ~40% plus légère
```

**Pour le pitch — répondre à "comment monitorer en prod ?" :**
> "On ajouterait Prometheus + Grafana : un endpoint `/metrics` sur FastAPI (via `prometheus-fastapi-instrumentator`) expose la latence OCR, le taux de succès par méthode OCR, le nombre d'anomalies par sévérité. Airflow expose aussi ses métriques nativement."

---

## 4. Front & UX — 2.0 / 3

### Points forts

**Clarté : bonne**
- Deux interfaces séparées selon le rôle (opérateur CRM vs officier compliance) — bien pensé
- shadcn/ui + Tailwind CSS — design cohérent et professionnel
- Sidebar avec navigation claire, badge de statut document
- `DocumentViewer` : document OCR côté gauche, champs extraits côté droit — très pertinent pour le jury

**Auto-remplissage fluide : présent**
- Champs extraits affichés automatiquement après traitement Airflow
- Niveau de confiance OCR affiché (`ocr_quality_score`)
- Statut document suivi visuellement (`StatusBadge`)

### Points faibles

| Faiblesse | Impact | Sévérité |
|-----------|--------|----------|
| Pas de mise à jour temps réel du statut pipeline | L'opérateur doit rafraîchir manuellement pour voir `processed` | Élevé (UX) |
| Pas de skeleton loading | Écran blanc pendant les fetch TanStack Query | Moyen |
| Vite dev server dans Docker (`--reload`) | Pas de build de production, rechargement lent | Moyen |
| Pas de drag & drop sur l'upload | Moins fluide qu'attendu | Faible |
| Pas d'aperçu du document avant envoi | L'utilisateur ne voit pas ce qu'il upload | Moyen |
| Interface uniquement en français | Pas de i18n (acceptable pour le contexte FR) | Nul |

### Propositions d'amélioration

**Impact maximum avant démo — polling du statut (30 lignes)**
```javascript
// Dans DocumentDetail.jsx
const { data: document } = useQuery({
  queryKey: ['document', id],
  queryFn: () => api.getDocument(id),
  // Refetch toutes les 3s tant que le doc n'est pas traité
  refetchInterval: (data) =>
    ['pending', 'preprocessing', 'ocr_done', 'classified', 'extracted', 'validated']
      .includes(data?.status) ? 3000 : false,
})
```

**Alternative propre : SSE (Server-Sent Events)**
```python
# backend : endpoint de statut en streaming
@router.get("/documents/{doc_id}/status/stream")
async def stream_status(doc_id: str):
    async def generator():
        while True:
            doc = await get_document(doc_id)
            yield f"data: {doc.status}\n\n"
            if doc.status in ("processed", "error"):
                break
            await asyncio.sleep(2)
    return EventSourceResponse(generator())
```

**Pour le pitch — répondre à "comment améliorer l'UX ?" :**
> "Le point le plus impactant serait d'ajouter du Server-Sent Events pour que l'opérateur voie la progression du pipeline en temps réel (OCR → classification → extraction → validation) sans avoir à rafraîchir. Airflow expose aussi une API de statut qu'on peut requêter."

---

## 5. Cohérence globale & pitch — 2.5 / 3

### Points forts

**Documentation : complète**
- `README.md` complet (architecture, installation, URLs, Makefile)
- `JURY_DEFENSE.md` — Q&A anticipées pour la soutenance
- `CONTEXT_MASTER.md` — référence d'architecture centralisée
- `CHANGELOG_IMPLEMENTATION.md` — log des décisions techniques
- `ARCHITECTURE_COMPARAISON.md` — justification des choix technologiques

**Démonstration : bien préparée**
- Script `seed.py` pour charger des données réalistes avec anomalies intentionnelles
- 15 vraies entreprises françaises via INSEE SIRENE si API key disponible
- Cas d'usage complets : upload → pipeline → anomalie → résolution
- Interfaces séparées qui démontrent la séparation des rôles

**Use case : cohérent et compréhensible**
- Problématique claire : conformité documentaire fournisseurs (SIRET, URSSAF, Kbis)
- Valeur métier directe : réduction du temps de traitement des documents fournisseurs

### Points faibles

| Faiblesse | Impact | Sévérité |
|-----------|--------|----------|
| Pas de chiffres de performance dans la démo | "Notre OCR a 87% de confiance" sans données mesurées | Moyen |
| Pas de rapport de classification (`report.json`) disponible en démo | Ne peut pas montrer accuracy/F1 au jury | Moyen |
| Dépendance INSEE API Key pour les vrais fournisseurs | Sans clé, le seed tombe en données faker moins convaincantes | Faible |

### Propositions pour le pitch

**Préparer ces réponses aux questions probables du jury :**

> *"Quelle est la précision de votre OCR ?"*
> → Lancer `make train` avant, récupérer le `report.json` du classifieur. Mesurer la confidence moyenne sur les documents de seed. Avoir des chiffres concrets.

> *"Comment passez-vous en production réelle ?"*
> → Remplacer `LocalExecutor` par `CeleryExecutor` + Redis (1 ligne dans `docker-compose.yml`). Remplacer MinIO par AWS S3. Remplacer MongoDB local par Atlas. Les interfaces ne changent pas.

> *"Pourquoi pas un LLM pour tout faire ?"*
> → "On a évalué l'option : GPT-4o Vision peut extraire des champs, mais à 0.03$/page pour des milliers de documents/mois, ça représente des coûts prohibitifs. Notre pipeline local coûte 0€ variable. Pour l'extraction structurée de documents standardisés (SIRET, TVA, montants), le regex post-OCR est aussi précis et 1000x moins cher."

> *"Votre Random Forest est-il vraiment adapté ?"*
> → "Pour la classification de 6 types de documents courts et structurés, RF est optimal : interprétable (feature importances), robuste au bruit OCR, inférence en 5ms. LayoutLMv3 ferait mieux sur des documents ambigus mais nécessite un GPU et des dizaines de milliers d'exemples labellisés."

---

## Résumé des priorités d'amélioration avant la soutenance

### Impact élevé / effort faible (faire avant la démo)

1. **Polling ou SSE sur le statut document** — l'UX est le critère le plus visible pour le jury
2. **Retirer `--reload`** dans le Dockerfile backend CMD — signal de rigueur
3. **Préparer les métriques de classification** (`report.json`) — avoir des chiffres prêts à citer
4. **Vérifier que `make seed` + `make train` fonctionnent en une commande** — la démo doit être fluide

### Impact moyen / effort moyen (si le temps le permet)

5. **Ajouter un score de confiance par champ extrait** — renforce la crédibilité IA
6. **Multi-stage Dockerfile** — signal de maturité DevOps
7. **Skeleton loading sur les pages** — polish UX
8. **Mentionner LayoutLMv3 comme évolution naturelle** — montre qu'on connaît l'état de l'art

### Ne pas faire avant la démo (risque trop élevé)

- Intégration APIs externes (Chorus Pro, Pappers) — non testée, peut casser la démo
- Migration vers CeleryExecutor — changement d'infrastructure, instable
- Remplacement du classifieur — risque de régression

---

## Points distinctifs à mettre en avant au jury

Ces éléments sont **rares dans les projets étudiants** et méritent d'être explicitement mentionnés :

1. **Pattern data lake raw/clean/curated** — architecture utilisée par les grands groupes (Datalake AWS, Azure Data Factory)
2. **TrOCR comme fallback** — utilisation d'un Transformer Vision-Language, au-delà du simple Tesseract
3. **Reconstruction de la structure ligne/colonne** avant regex — évite les faux matchs sur les factures multi-colonnes
4. **Validation algorithmic SIRET (Luhn) et IBAN (MOD-97)** — pas juste un check de longueur
5. **Deux interfaces séparées selon le rôle** — CRM opérateur vs Compliance officer — cohérence métier forte
6. **Airflow avec callback d'échec mis à jour en MongoDB** — pipeline résilient, pas juste un script
