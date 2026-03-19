# Architecture cible vs implémentation réelle

Ce document compare point par point l'architecture cible attendue avec ce qui a été réellement construit, explique les écarts et les choix qui les justifient, et liste les optimisations envisageables.

---

## Vue d'ensemble rapide

| Point de l'architecture cible | Statut | Résumé |
|-------------------------------|--------|--------|
| Upload vers Data Lake (stockage brut) | Conforme | MinIO joue le rôle du Data Lake |
| Airflow pour orchestration | Conforme | DAG à 5 étapes, jusqu'à 20 runs en parallèle |
| Zones Raw / Clean / Curated | Conforme | 3 buckets MinIO distincts |
| Frontend CRM + Conformité | Partiellement conforme | React/Vite au lieu de MERN |
| Formulaires remplis automatiquement par l'IA | Partiellement conforme | Champs extraits et affichés, pas injectés dans des formulaires éditables |
| OCR Tesseract | Conforme | Tesseract 5 avec preprocessing adaptatif |
| NLP / NER pour extraction d'entités | Non conforme | Regex + heuristiques à la place d'un vrai modèle NER |
| Étape de classification | Ajout | Non prévu dans la cible, ajouté pour la robustesse |

---

## Détail par point

---

### Ingestion — Upload vers Data Lake

**Cible** : upload d'un document vers un stockage brut de type Data Lake.

**Ce qui a été fait** : conforme. Quand un document est uploadé via le CRM, il est immédiatement stocké dans le bucket `raw` de MinIO. MinIO est un stockage objet S3-compatible, ce qui correspond exactement à la définition d'un Data Lake — stockage de fichiers bruts dans leur format d'origine, sans transformation préalable. Les métadonnées du document (fournisseur, statut, timestamps) sont simultanément enregistrées dans MongoDB avec le statut `pending`.

**Ecart** : aucun sur ce point.

---

### Orchestration Airflow

**Cible** : Airflow pour orchestrer le pipeline en 4 étapes (Ingestion, OCR, Extraction, Validation).

**Ce qui a été fait** : conforme sur le principe, avec deux différences mineures.

La première différence est le découpage des étapes. Le pipeline implémenté en comporte 5 au lieu de 4 :

```
preprocess_ocr → classify → extract_fields → validate → finalize
```

L'étape `classify` (classification du type de document) n'était pas dans la cible. Elle a été ajoutée car l'extraction des champs dépend du type de document — on n'extrait pas les mêmes informations d'une facture et d'un RIB. Sans classification préalable, l'extraction serait aveugle.

L'étape `finalize` a également été ajoutée pour écrire le JSON structuré final dans la zone curated de MinIO, ce qui n'était pas explicitement prévu mais découle logiquement de la zone Curated.

La deuxième différence concerne le seed. Initialement le script de seed court-circuitait Airflow et appelait le pipeline directement. Ce problème a été corrigé : le seed déclenche maintenant un DAG Airflow par document via l'API REST, exactement comme un upload depuis le CRM.

**Configuration Airflow** : le DAG est configuré avec `max_active_runs=20` (20 documents traités en parallèle), `retries=2` avec backoff exponentiel, et un timeout de 10 minutes par tâche.

---

### Stockage — Zones Raw / Clean / Curated

**Cible** : trois zones de stockage distinctes pour les documents bruts, le texte OCR, et les données structurées.

**Ce qui a été fait** : conforme, et implémenté avec une séparation stricte.

| Zone | Bucket MinIO | Contenu |
|------|-------------|---------|
| Raw | `raw` | Fichier original uploadé (PDF ou JPEG), jamais modifié |
| Clean | `clean` | Texte OCR extrait en `.txt` + métadonnées OCR en JSON |
| Curated | `curated` | JSON structuré final avec tous les champs extraits et le résultat de validation |

La progression d'un document dans ces zones est tracée dans MongoDB via le champ `zone` (`raw` → `clean` → `curated`) et le champ `status`.

**Ecart** : aucun sur ce point.

---

### Frontend — MERN, CRM et outil de conformité

**Cible** : deux applications frontend développées en MERN (MongoDB, Express, React, Node.js), avec des formulaires remplis automatiquement par l'IA.

**Ce qui a été fait** : partiellement conforme.

Les deux frontends existent (CRM et Conformité) et sont développés en React 18 avec Vite, Tailwind CSS v4 et TanStack Query. Sur ce point, pas d'écart.

L'écart se situe sur deux aspects :

**Stack backend** : la cible prévoyait Express/Node.js. L'implémentation utilise FastAPI (Python). Ce choix a été fait parce que le pipeline OCR, le modèle ML et les bibliothèques de traitement d'image (OpenCV, Tesseract, scikit-learn, pdfplumber) sont tous des écosystèmes Python. Avoir un backend Node.js aurait obligé soit à appeler des scripts Python en sous-processus, soit à maintenir deux langages de backend distincts. FastAPI offre les mêmes capacités qu'Express (REST, JWT, middleware, CORS) avec la stack Python unifiée. La lettre M-E-R-N est donc partiellement respectée : MongoDB (M) et React (R) sont là, Express/Node ont été remplacés par FastAPI.

**Formulaires automatiquement remplis** : les champs extraits par le pipeline (SIRET, montant TTC, raison sociale, IBAN, dates...) sont affichés dans les interfaces, mais ils ne sont pas injectés dans des formulaires éditables pré-remplis. Les données sont visibles dans les vues de détail des documents, ce qui couvre l'objectif fonctionnel de consultation, mais pas celui de saisie assistée.

---

### OCR

**Cible** : Tesseract ou équivalent, ou modèle Deep Learning.

**Ce qui a été fait** : conforme. Tesseract 5 est utilisé avec un pipeline de preprocessing adaptatif développé sur OpenCV. Ce preprocessing sélectionne automatiquement parmi 8 stratégies selon les caractéristiques de l'image (flou, contraste, luminosité, bruit, rotation) :

- Standard : grayscale + deskew + Otsu
- Adaptive standard : grayscale + deskew + seuillage adaptatif (toujours testée en parallèle)
- Blurry : unsharp mask + CLAHE + Sauvola
- Very blurry : débruitage NLM + unsharp + adaptive threshold
- Low contrast : CLAHE agressif + Otsu
- Dark scan : correction gamma + CLAHE + adaptive threshold
- Overexposed : correction gamma inverse + Sauvola
- Noisy : filtre bilatéral + médian + CLAHE + Otsu + cleanup morphologique

Pour les PDF natifs (texte embarqué), pdfplumber est utilisé à la place de Tesseract, ce qui donne un score de qualité OCR de 0.98 sans perte d'information.

4 configurations PSM de Tesseract sont testées avec early stop : PSM 3 (auto), PSM 6 (bloc uniforme), PSM 4 (colonne unique), PSM 11 (texte sparse).

**Ecart** : aucun sur le choix technologique. L'implémentation est même plus avancée que la cible sur ce point.

---

### NLP / NER pour extraction d'entités

**Cible** : NLP pour extraction d'entités nommées (NER).

**Ce qui a été fait** : non conforme. L'extraction des champs utilise des expressions régulières et des heuristiques, pas un modèle NER.

Ce choix a été fait pour des raisons pratiques :

- Les documents traités (factures, KBIS, URSSAF, RIB) ont des formats relativement structurés et répétitifs. Les regex atteignent un bon taux d'extraction sur ces formats.
- Un modèle NER français entraîné (spaCy `fr_core_news_lg`, CamemBERT-NER) aurait alourdi l'image Docker de plusieurs centaines de Mo et augmenté la latence d'extraction.
- Le temps de développement pour fine-tuner un NER sur ces types de documents spécifiques dépasse le cadre du projet.

Le résultat pratique : l'extraction fonctionne bien sur les champs numériques (SIRET, TVA, IBAN, montants) grâce aux regex, mais est moins robuste sur les champs textuels comme la raison sociale, qui repose sur une heuristique basée sur les suffixes juridiques (SAS, SARL, EURL, etc.).

C'est le point le plus éloigné de la cible et le plus impactant sur la qualité des résultats.

---

### Classification — étape non prévue

**Cible** : non mentionné.

**Ce qui a été fait** : ajout d'une étape de classification du type de document (FACTURE, DEVIS, KBIS, URSSAF, RIB, SIRET) entre l'OCR et l'extraction.

Cette étape est nécessaire pour deux raisons. D'abord, l'extraction des champs est spécifique au type de document — les règles pour extraire un montant TTC d'une facture sont différentes de celles pour extraire une date d'expiration d'un URSSAF. Ensuite, la validation métier est différente selon le type (le KBIS a une limite légale de 90 jours, l'URSSAF doit avoir une date d'expiration, le RIB doit avoir un IBAN valide, etc.).

Le classifieur est un Random Forest entraîné sur 900 documents synthétiques (TF-IDF + 200 arbres), avec un fallback sur des règles lexicales si le modèle n'est pas chargé ou si la confiance est inférieure à 0.6.

---

## Optimisations envisageables

### Priorité haute

**Remplacer les regex par un modèle NER**
C'est le principal écart avec la cible et le principal frein à la qualité. spaCy avec le modèle `fr_core_news_lg` permet de reconnaître les entités nommées (organisations, montants, dates, lieux) sans règles manuelles. Pour un gain maximal, un fine-tuning sur les types de documents du projet serait nécessaire, mais même le modèle généraliste améliorerait l'extraction de la raison sociale et des adresses.

**Remplir automatiquement les formulaires**
Les données extraites existent dans MongoDB. Il manque uniquement la partie frontend : quand un opérateur crée ou édite un fournisseur, les champs pourraient être pré-remplis depuis les derniers documents traités de ce fournisseur. C'est un développement frontend pur, sans impact sur le pipeline.

### Priorité moyenne

**Remplacer Tesseract par un modèle Deep Learning sur les documents dégradés**
TrOCR (Microsoft) ou EasyOCR donneraient de meilleurs résultats sur les scans très dégradés, mais au prix d'un GPU ou d'une latence plus élevée sur CPU. Une approche hybride serait envisageable : Tesseract par défaut, modèle DL uniquement si le score qualité OCR est inférieur à un seuil.

**Passer le backend en MERN (Express/Node)**
Si la conformité stricte à la stack MERN est requise, le backend FastAPI pourrait être remplacé par Express. Cela demanderait de réécrire le pipeline en JavaScript ou de le garder en Python et l'exposer comme microservice séparé appelé par Express. Le gain est principalement académique — FastAPI fait le même travail de façon plus cohérente avec le reste de la stack Python.

### Priorité basse

**API SIRENE en cache local**
Le seed appelle l'API INSEE à chaque exécution. Si la clé expire ou le réseau est indisponible, le seed échoue. Un cache local des entreprises récupérées éviterait cette dépendance externe.

**Monitoring Airflow plus fin**
Actuellement, si un DAG échoue, l'opérateur doit aller dans l'UI Airflow pour comprendre pourquoi. Une notification dans le frontend (webhook ou polling depuis le backend) améliorerait la visibilité sans changer l'architecture.
