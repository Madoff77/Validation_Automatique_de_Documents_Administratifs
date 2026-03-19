# Analyse & améliorations — Extraction de champs

> Réalisé le 2026-03-19. Concerne `backend/pipeline/extraction/field_extractor.py`.

---

## Contexte

L'extraction repose sur des **regex contextuelles** plutôt que sur du NLP/NER ou du deep learning.
Ce choix est justifié par les contraintes du projet (temps, profils, infrastructure), mais il impose
une rigueur particulière sur la robustesse des patterns face aux artefacts OCR.

Ce document trace l'état des lieux initial, les faiblesses identifiées, et les correctifs appliqués.

---

## État des lieux par champ

### Champs fiables

| Champ | Mécanisme | Robustesse |
|-------|-----------|------------|
| SIRET | Contexte "SIRET :" puis 14 chiffres | Bonne après fix |
| SIREN | Dérivé du SIRET si disponible | Très bonne |
| TVA | Contexte "FR" + structure alphanum | Bonne |
| Taux TVA | Regex + vérification taux légaux (20/10/8.5/5.5/2.1%) | Bonne |
| Montants | Contexte HT/TTC/TVA + déductions croisées | Correcte après fix |
| Dates | dateutil en fallback, 8+ formats | Bonne |
| IBAN | Pattern FR27 + contexte "IBAN :" | Correcte après fix |
| BIC | Contexte étendu + proximité IBAN | Correcte après fix |
| N° document | Contexte "Facture N°" / "Devis N°" | Bonne |

### Champs fragiles (accepté)

| Champ | Problème | Décision |
|-------|----------|----------|
| Raison sociale | Ne matche que les entités avec suffixe juridique visible (SARL, SAS…) | Acceptable — B2B admin FR toujours avec sigle |
| Adresse | Requiert numéro + type de voie + CP + ville dans l'OCR | Informative seulement, aucune validation |

---

## Faiblesses identifiées et corrigées

### 1. Erreurs OCR dans les identifiants numériques

**Problème** : Tesseract confond régulièrement certaines lettres et chiffres dans les séquences longues :

| OCR lit | Valeur réelle |
|---------|--------------|
| `O` / `o` | `0` |
| `l` / `I` | `1` |
| `B` | `8` |
| `S` | `5` |
| `Z` | `2` |

Un SIRET `12345678901234` lu `123O5678901234` ne matchait aucun pattern `\d{14}`.

**Correction — `_normalize_numeric_ocr()`** :
```python
# Appliqué uniquement sur les séquences de 8+ caractères contenant déjà des chiffres
# → évite de corriger du texte normal ("SAS" → "5A5" serait catastrophique)
re.sub(r'[0-9OolIBSZ\s.\-]{8,}', fix_digits, text)
```
Appelée en tête de `extract_fields()` avant tout extracteur.

---

### 2. SIRET : mauvais candidat sur documents multi-entités

**Problème** : sur une attestation URSSAF ou un Kbis, deux SIRET coexistent dans le texte :
- le SIRET de l'entreprise concernée
- le SIRET de l'organisme émetteur (URSSAF Île-de-France, greffe du tribunal…)

L'ancienne stratégie retournait le **premier** SIRET de 14 chiffres trouvé — souvent le mauvais.

**Correction — scoring par proximité au mot-clé** :
```python
keyword_positions = [m.start() for m in re.finditer(r'\bsiret\b', text, re.IGNORECASE)]
# Pour chaque candidat, calculer dist = min(|pos_candidat - pos_keyword|)
# → retenir le candidat le plus proche du label "SIRET"
```
La priorité reste le contexte explicite `SIRET : 12345...` — le scoring n'intervient que si
ce contexte est absent.

---

### 3. Montants sur factures multi-colonnes

**Problème** : le gap `[^\d]{0,20}` entre label et montant était trop court.
Sur une facture avec tableau de lignes, le texte OCR reconstruit peut être :
```
Total HT   |   Remise   |   Net HT
                                   1 250,00
```
Le label `Total HT` et le montant `1 250,00` sont séparés par plus de 20 caractères (espaces + texte de colonnes) et le montant peut être sur la ligne suivante.

**Correction** :
```python
# Gap : 0,20 → 0,40 caractères (non-chiffres)
# + re.MULTILINE : le . ne s'arrête plus à \n
_RE_MONTANT_HT = re.compile(
    r'(?:total\s+ht|...)[^\d]{0,40}' + _AMOUNT_PATTERN,
    re.IGNORECASE | re.MULTILINE
)
```
Appliqué aux trois patterns : `_RE_MONTANT_HT`, `_RE_MONTANT_TTC`, `_RE_MONTANT_TVA`.

---

### 4. IBAN : espaces multiples entre groupes

**Problème** : `[\s]?` n'autorisait qu'**un seul** espace entre les groupes de chiffres.
Tesseract sur scan basse qualité produit couramment des espaces doubles :
```
FR76  3000  6000  0112  3456  7890  189
     ^^    ^^    ^^    ^^    ^^    ^^
     2 espaces → pattern cassé
```

**Correction** :
```python
# [\s]? → [\s]{0,2}
_RE_IBAN = re.compile(
    r'\b(FR\d{2}[\s]{0,2}\d{4}[\s]{0,2}\d{4}[\s]{0,2}\d{4}[\s]{0,2}\d{4}[\s]{0,2}\d{4}[\s]{0,2}\d{2,3})\b',
    re.IGNORECASE
)
```

Un contexte explicite `IBAN :` est également tenté en priorité, avec capture large puis nettoyage.

---

### 5. BIC : labels trop restrictifs + espaces OCR

**Problème** — trois faiblesses cumulées :

**a) Labels insuffisants**
L'ancienne regex ne reconnaissait que `BIC` ou `SWIFT` seuls avant le code.
Les variantes réelles sur les RIBs français n'étaient pas couvertes :

| Label dans le document | Ancien code | Nouveau code |
|------------------------|-------------|--------------|
| `BIC : BNPAFRPPXXX` | ✓ | ✓ |
| `Code BIC : BNPAFRPPXXX` | ✗ | ✓ |
| `BIC/SWIFT : BNPAFRPPXXX` | ✗ | ✓ |
| `SWIFT/BIC : BNPAFRPPXXX` | ✗ | ✓ |
| `Identifiant BIC : BNPAFRPPXXX` | ✗ | ✓ |
| `Code établissement : BNPAFRPPXXX` | ✗ | ✓ |
| Aucun label (RIB imprimé) | ✗ | ✓ (via IBAN) |

**b) Espaces OCR dans le BIC**
Tesseract segmente en groupes de 4 chars (même format que l'IBAN).
`BNPAFRPPXXX` → `BNPA FRPP XXX`. Le pattern requérant des lettres consécutives ne matchait pas.

**c) Aucun fallback**
Si le label n'était pas exactement `BIC` ou `SWIFT`, retour `None` systématique.

**Correction — stratégie en deux niveaux** :
```python
# Niveau 1 : labels étendus + nettoyage des espaces
ctx = re.search(
    r'(?:(?:code[\s\-]?)?bic(?:[\s/]?swift)?'
    r'|swift(?:[\s/]?(?:code|bic))?'
    r'|identifiant[\s\-](?:bic|swift)'
    r'|code[\s\-]établissement)'
    r'[\s:/]*'
    r'([A-Za-z]{4}[\s]?[A-Za-z]{2}[\s]?[A-Za-z0-9]{2}(?:[\s]?[A-Za-z0-9]{3})?)',
    text, re.IGNORECASE
)
# → spaces supprimés du candidat avant validation structurelle

# Niveau 2 : voisinage IBAN (±150 chars)
# BIC et IBAN sont toujours sur le même RIB, à proximité immédiate
```

**Validation structurelle BIC — `_is_valid_bic()`** :
Tout candidat passe par une vérification de structure réelle avant d'être retourné :
- Positions 1-4 : bank code (4 lettres obligatoires)
- Positions 5-6 : country code (2 lettres obligatoires)
- Positions 7-8 : location code (lettres ou chiffres)
- Positions 9-11 : branch code (optionnel)

Évite de retourner n'importe quelle séquence de 8 caractères comme BIC.

---

### 6. Adresse : silencieuse par design

L'adresse n'est validée dans **aucune** règle du validator (`validator.py`).
Elle est présente dans `extracted` uniquement à titre informatif.

La fonction `_extract_adresse()` est enveloppée dans un `try/except` explicite
pour garantir qu'aucune exception — même inattendue — ne remonte depuis ce champ.
Les `None` sont filtrés par `{k: v for k, v in result.items() if v is not None}`
avant insertion MongoDB.

**Aucun check, aucun warning, aucune anomalie ne peut être généré à partir de l'adresse.**

---

## Ce qui reste fragile (accepté, non corrigé)

### Raison sociale sans suffixe juridique

Le pattern `_RE_RAISON_SOCIALE` requiert un suffixe visible (`SARL`, `SAS`, `EURL`…).
Les grandes entreprises sans sigle dans l'OCR (`La Poste`, `Orange`, `EDF`) retournent `None`.

**Pourquoi c'est acceptable** : dans le contexte de documents administratifs B2B français
(URSSAF, Kbis, attestation SIRET), le suffixe juridique est **toujours** présent dans l'en-tête.
La raison sociale n'est pas validée et n'est pas critique pour la conformité.

**Évolution possible** : spaCy `fr_core_news_sm` avec NER label `ORG` — mais nécessite
un modèle supplémentaire (~50MB) et une dépendance spaCy non triviale.

### Dates sur documents avec dates multiples

Sur un Kbis, il peut y avoir : date de création de l'entreprise, date du dernier acte,
date d'émission du Kbis. Le fallback "première date plausible" peut prendre la mauvaise.
Mitigé par le contexte explicite `_RE_DATE_EMISSION` et le calcul automatique
de l'expiration Kbis (+90 jours depuis l'émission) dans `_extract_kbis()`.

---

## Évolutions futures (hors scope immédiat)

| Amélioration | Complexité | Gain |
|--------------|------------|------|
| spaCy NER pour raison sociale | Moyenne | +15% précision raison sociale |
| Score de confiance par champ | Faible | Meilleure observabilité |
| LayoutLMv3 (Microsoft) | Élevée | State-of-the-art extraction structurée |
| Validation BIC via liste ISO 9362 | Faible | Élimination des faux positifs BIC |
