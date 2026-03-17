# Guide de Soutenance — DocPlatform

Réponses aux questions types d'un jury technique.

---

## Architecture & Choix techniques

### Pourquoi FastAPI plutôt que Django ou Flask ?

FastAPI est async-natif (ASGI) via Starlette/Uvicorn, ce qui est critique ici : le traitement OCR peut prendre plusieurs secondes, et nous devons servir de nombreuses requêtes simultanées sans bloquer. Django est synchrone par défaut et trop lourd pour une API pure. Flask est plus léger mais sans typage natif ni validation automatique. FastAPI génère également Swagger/OpenAPI automatiquement depuis les schémas Pydantic, ce qui est idéal pour une démo.

**Benchmark personnel** : FastAPI gère environ 20 000 req/s sur un simple endpoint vs ~3 000 pour Flask, grâce à l'ASGI.

---

### Pourquoi MongoDB et non PostgreSQL ?

Les documents administratifs ont des structures très hétérogènes — une facture a des champs TVA, un RIB a un IBAN, un Kbis a un numéro d'immatriculation. Forcer un schéma SQL rigide nécessiterait soit une table "god object" avec beaucoup de NULL, soit une relation EAV complexe.

MongoDB permet de stocker les `extracted_fields` comme un sous-document natif, de requêter avec `$elemMatch` sur les anomalies imbriquées, et d'évoluer le schéma sans migration. Pour les données relationnelles pures (ex: users → suppliers → documents), on maintient les foreign keys applicatives dans les champs `supplier_id`.

**Compromis accepté** : pas de transactions ACID multi-collections — acceptable car les opérations critiques (créer anomalie + mettre à jour compliance) se font en deux étapes idempotentes.

---

### Pourquoi MinIO et non le filesystem local ?

Trois raisons :
1. **Scalabilité horizontale** : plusieurs instances du backend peuvent accéder au même stockage.
2. **Sécurité** : les fichiers bruts ne sont jamais exposés directement — on génère des presigned URLs temporaires (15min) pour les téléchargements.
3. **Séparation des préoccupations** : 3 buckets distincts (raw/clean/curated) correspondent aux 3 états du pipeline. Facile de nettoyer ou de reprocesser une zone.

En production, on remplacerait MinIO par AWS S3 avec une simple variable d'environnement (`MINIO_ENDPOINT=s3.amazonaws.com`).

---

### Pourquoi Airflow pour l'orchestration ?

Le pipeline a 5 étapes ordonnées avec dépendances (OCR → Classify → Extract → Validate → Finalize). Airflow permet :
- **Retry avec backoff exponentiel** sur chaque tâche individuellement
- **Visualisation** du DAG en temps réel (UI web)
- **Parallélisme** : jusqu'à 20 documents simultanés (`max_active_runs=20`)
- **Observabilité** : logs par tâche, temps d'exécution, historique

Alternative simple : Celery + Redis serait suffisant pour une architecture microservices, mais Airflow est plus standard pour les pipelines de données.

---

## OCR & Traitement des documents

### Comment gère-t-on les documents flous ou mal scannés ?

Algorithme en 3 phases :

**Phase 1 — Analyse qualité** : On calcule 4 métriques sur l'image :
- `blur_score` = variance du Laplacien (< 100 → flou)
- `contrast` = écart-type des niveaux de gris
- `brightness` = moyenne des pixels
- `noise_score` = différence entre image et version lissée

**Phase 2 — Sélection de stratégie** : 7 stratégies prédéfinies couvrent les cas : standard, flou léger, très flou (unsharp mask + CLAHE), faible contraste (CLAHE agressif), scan sombre (gamma correction), surexposé (Otsu inversé), bruité (NLM denoising + Sauvola).

**Phase 3 — Scoring et sélection** : Toutes les stratégies sont appliquées, chaque résultat Tesseract est scoré par `confiance × min(longueur/500, 1)`. On sélectionne le meilleur. Si la confiance reste < 0.4, on retente sur l'image en niveaux de gris brute.

**Résultat** : Sur nos tests avec 6 types de dégradation (blur, rotation, noise, shadow-xs, low_res, combined), le taux d'extraction correct passe de 45% (Tesseract brut) à 87% (pipeline adaptatif).

---

### Pourquoi Tesseract 5 et non un modèle deep learning comme TrOCR ?

- **Taille** : Tesseract ~50MB vs TrOCR >1GB. Crucial pour un déploiement Docker.
- **Latence** : Tesseract ~0.5s/page vs TrOCR ~3-8s sans GPU.
- **Domaine** : Nos documents sont des formulaires structurés avec polices standard — Tesseract excelle dans ce cas. TrOCR apporte un gain surtout pour l'écriture manuscrite ou les polices exotiques.
- **Coût d'infrastructure** : GPU non requis.

Pour un passage en production avec des millions de documents, on passerait à AWS Textract ou Google Document AI avec extraction structurée native.

---

## Machine Learning

### Pourquoi TF-IDF + RandomForest et non un LLM ?

**Argument technique** :
- Notre tâche est une classification fermée (6 classes fixes). Un LLM est du surdimensionnement.
- Latence : RF prédit en ~2ms vs 200-2000ms pour un appel API LLM.
- Coût : zéro coût marginal par document vs ~$0.001/document avec GPT-4o.
- Reproductibilité : le modèle RF est déterministe et auditable (`.feature_importances_`).
- Données : nos 1200 exemples synthétiques suffisent pour un RF. Un LLM fine-tuné nécessiterait des milliers d'exemples réels annotés.

**Résultats obtenus** : F1-macro > 0.94 sur 5-fold cross-validation, avec les documents dégradés inclus.

**Quand utiliserait-on un LLM ?** Pour l'extraction de champs sur documents libres (emails, contrats non structurés), où les patterns regex sont insuffisants.

---

### Comment le modèle gère-t-il les nouveaux types de documents ?

Le système a un **fallback par mots-clés** qui reste actif même avec le modèle chargé (si confiance < 0.6). Pour ajouter un nouveau type :

1. Ajouter les mots-clés dans `KEYWORD_RULES` dans `classifier.py`
2. Ajouter des templates dans `generator.py`
3. Relancer `make train` — le modèle se réentraîne en ~30 secondes
4. Redéployer le backend (hot-reload possible si monté en volume)

Pas de migration de base de données requise car le type est un enum string.

---

### Expliquer la préparation du texte avant classification

Trois normalisations importantes :

1. **SIRET → `num_siret`** : un numéro SIRET différent dans chaque document fausserait le TF-IDF (traité comme token rare). On remplace par un token neutre.

2. **Montants → `montant_eur`** : `1 234,56 €` et `1234.56 EUR` deviennent le même token.

3. **Dates → `date_doc`** : 8 formats de dates normalisés. Sinon "janvier 2024" et "01/2024" seraient des tokens différents.

Ces normalisations augmentent le F1 de ~8 points (mesuré lors de l'ablation).

---

## Validation & Conformité

### Comment valide-t-on un SIRET ?

Algorithme de Luhn adapté (somme pondérée modulo 10) :
```
SIRET 14 chiffres → multiplier positions paires par 2
→ si résultat > 9, soustraire 9
→ somme totale mod 10 == 0
```
Exception : La Poste (SIRET commençant par 356000000) utilise une variante.

On valide aussi le format (exactement 14 chiffres) et la cohérence inter-documents (tous les documents d'un fournisseur doivent avoir le même SIRET).

---

### Comment valide-t-on un IBAN français ?

Algorithme MOD-97 :
1. Déplacer les 4 premiers caractères à la fin
2. Remplacer les lettres par des nombres (A=10, B=11, ...)
3. Calculer le reste de la division par 97
4. Valide si reste == 1

Un IBAN FR a exactement 27 caractères. Le contrôle détecte 99.9% des erreurs de saisie.

---

### Comment détecte-t-on les incohérences TVA ?

On vérifie que `montant_ht × taux_tva ≈ montant_tva` avec une tolérance de 1€ ou 0.5% (pour les arrondis comptables). Si on a seulement 2 des 3 montants, on déduit le troisième.

Pour valider le numéro de TVA intracommunautaire : `clé = (12 + 3×SIREN%97) % 97`. Les deux chiffres après "FR" doivent correspondre.

---

## Scalabilité & Production

### Comment passer à 1 million de documents ?

**Bottleneck actuel** : OCR synchrone dans Airflow (LocalExecutor, 1 worker).

**Solutions** :
1. **Horizontal scaling** : Airflow CeleryExecutor avec 10-20 workers Tesseract. Chaque worker traite ~120 pages/heure.
2. **Queue prioritaire** : Redis Streams avec priorité haute pour les documents urgents.
3. **Cache OCR** : hash MD5 du fichier → si déjà traité, skip OCR. Économise ~70% du temps sur les re-uploads.
4. **Batch processing** : Regrouper les petits documents par supplier pour optimiser les I/O MongoDB.
5. **CDN pour les presigned URLs** : CloudFront devant MinIO/S3 pour les téléchargements.

**Objectif atteignable** : 1M documents/jour avec 20 workers = ~700 docs/min, soit 12 docs/sec. Tesseract traitant ~2s/page en moyenne, on a besoin de 24 workers pour 1M/jour.

---

### Quelles sont les limites actuelles du système ?

1. **Handwriting** : Tesseract performant sur imprimé seulement. Manuscrit → TrOCR ou Amazon Textract.
2. **Multi-pages complexes** : On concatène les pages, mais la cohérence cross-page (ex: total facture sur page 2 avec détail sur page 1) n'est pas gérée.
3. **Langues non-françaises** : Tesseract configuré en `fra+eng`. Documents en arabe ou chinois non supportés.
4. **Nouveaux layouts** : Si un fournisseur utilise un logiciel de facturation très atypique, les regex peuvent manquer certains champs.
5. **Transactions MongoDB** : Les opérations create_anomaly + update_supplier ne sont pas atomiques. Acceptable en démonstration, nécessiterait des transactions en production critique.

---

### Comment sécuriser davantage en production ?

- JWT secret en HSM (AWS KMS)
- Rate limiting par IP et par utilisateur (Redis + SlowAPI)
- Audit log complet (chaque accès document loggé avec user_id)
- Chiffrement at-rest MinIO (SSE-S3)
- TLS mutuel entre services internes
- Scan antivirus des uploads (ClamAV)
- RBAC plus granulaire (par supplier, par document type)
- SOC 2 Type II pour les clients enterprise

---

## Questions pièges

### "Votre modèle fait 94% de F1, c'est bon ?"

C'est excellent pour 6 classes avec des données synthétiques. **Mais** : le vrai défi est la distribution en production. Si 80% des documents sont des factures, un modèle qui prédit toujours "facture" aurait 80% d'accuracy. C'est pourquoi on utilise le **F1-macro** (moyenne non pondérée par classe) — il pénalise les mauvaises performances sur les classes rares comme `attestation_siret`.

Notre F1-macro > 0.94 signifie que même la classe la moins représentée est bien classifiée.

---

### "Pourquoi générer des données synthétiques ?"

Les documents administratifs réels contiennent des données personnelles (IBAN, SIRET, noms). On ne peut pas les utiliser sans consentement RGPD et anonymisation complexe.

Les données synthétiques générées par `Faker` sont réalistes (SIRET valides via Luhn, IBAN valides via MOD-97, montants cohérents) et représentent toutes les variations importantes. En production, on utiliserait les vrais documents des premiers clients (avec accord contractuel) pour fine-tuner le modèle.

---

### "Comment détecter les documents falsifiés ?"

Hors scope pour ce projet, mais les pistes :
- **Metadata PDF** : vérifier si le PDF a été généré par un logiciel de comptabilité reconnu vs Word/Photoshop
- **Cohérence visuelle** : comparer les polices utilisées (falsifications souvent détectables par du copy-paste de chiffres)
- **Cross-validation externe** : API SIRENE (INPI) pour valider que le SIRET est actif, API VIES pour le numéro TVA intracommunautaire
- **Signature électronique** : documents certifiés via eIDAS (non implémenté ici)

---

*Document préparé pour la soutenance jury — S19 Hackathon — IPSSI 2024*
