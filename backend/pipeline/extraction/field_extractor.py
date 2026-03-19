import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, date
from dateutil import parser as dateutil_parser
from utils.logger import get_logger

logger = get_logger(__name__)

# les patterns regex compilés une fois au démarrage

# SIRET : 14 chiffres espacés par groupes 3-3-3-5
_RE_SIRET = re.compile(
    r'\b(\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3}[\s.\-]?\d{5})\b'
)

# SIREN : 9 chiffres 3 3 3
_RE_SIREN = re.compile(
    r'\b(\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3})\b'
)

# Numéro TVA intracommunautaire français : FR + 2 alphanum + 9 chiffres
_RE_TVA = re.compile(
    r'\b(FR[\s.\-]?[0-9A-Z]{2}[\s.\-]?\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3})\b',
    re.IGNORECASE
)

# Montants
# Capture un nombre décimal (virgule ou point) suivi optionnellement de €
_AMOUNT_PATTERN = r'([\d\s]{1,10}[,.]?\d{0,2})\s*(?:€|EUR|euros?)?'

# Contexte HT

_RE_MONTANT_HT = re.compile(
    r'(?:total\s+ht|montant\s+ht|sous.?total\s+ht|base\s+ht|net\s+ht|\bht\s*:)[^\d]{0,20}' + _AMOUNT_PATTERN,
    re.IGNORECASE
)
# Contexte TTC
_RE_MONTANT_TTC = re.compile(
    r'(?:total\s+ttc|montant\s+ttc|ttc\s*:?|net\s+à\s+payer|à\s+payer\s*:?|total\s+général)[^\d]{0,20}' + _AMOUNT_PATTERN,
    re.IGNORECASE
)
# Montant TVA
_RE_MONTANT_TVA = re.compile(
    r'(?:tva\s+(?:à\s+)?\d[\d,.]?\s*%|dont\s+tva|montant\s+tva)[^\d]{0,20}' + _AMOUNT_PATTERN,
    re.IGNORECASE
)
# Taux TVA
_RE_TAUX_TVA = re.compile(
    r'tva\s*(?:à\s*|au\s*)?(\d{1,2}[,.]?\d?)\s*%',
    re.IGNORECASE
)

# Dates
# Formats supportés : DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY,
#                     YYYY-MM-DD, D MOIS YYYY, "le DD/MM/YYYY"
_DATE_FORMATS_STR = [
    r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b',       # DD/MM/YYYY
    r'\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b',       # YYYY-MM-DD
    r'\b(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|'
    r'août|septembre|octobre|novembre|décembre)\s+(\d{4})\b',  # D MOIS YYYY
    r'\b(\d{1,2})\s+(jan|fév|mar|avr|mai|jun|jul|aoû|sep|oct|nov|déc)\.?\s+(\d{4})\b',
]
_RE_DATES = [re.compile(p, re.IGNORECASE) for p in _DATE_FORMATS_STR]

# Contexte date émission
_RE_DATE_EMISSION = re.compile(
    r'(?:date\s+(?:d[\'e]?\s*)?(?:émission|facturation|facture|devis|édition|document|établissement)'
    r'|émis\s+le|fait\s+le|le\s+:)\s*[:\s]?\s*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',
    re.IGNORECASE
)
# Contexte date échéance / paiement
_RE_DATE_ECHEANCE = re.compile(
    r'(?:date\s+(?:d[\'e]?\s*)?(?:échéance|paiement|règlement|due)|payable\s+(?:le|avant\s+le)|à\s+régler\s+(?:le|avant\s+le))\s*[:\s]?\s*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',
    re.IGNORECASE
)
# Contexte date expiration / validité
_RE_DATE_EXPIRATION = re.compile(
    r'(?:valable\s+jusqu[\'au]*\s+(?:au)?|valide?\s+(?:jusqu[\'au]*\s+(?:au)?|jusqu\'au)'
    r'|expire\s+le|date\s+(?:de\s+)?(?:fin|expiration|validité)|jusqu\'au)\s*[:\s]?\s*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})',
    re.IGNORECASE
)

# Numéro de document
_RE_NUM_FACTURE = re.compile(
    r'(?:facture\s*n[o°]?\s*:?|n[o°]\s*(?:de\s+)?facture\s*:?|ref[.\s]*facture\s*:?)\s*([A-Z0-9\-_/]{3,25})',
    re.IGNORECASE
)
_RE_NUM_DEVIS = re.compile(
    r'(?:devis\s*n[o°]?\s*:?|n[o°]\s*(?:du\s+)?devis\s*:?|offre\s*n[o°]?\s*:?)\s*([A-Z0-9\-_/]{3,25})',
    re.IGNORECASE
)
_RE_NUM_DOCUMENT = re.compile(
    r'(?:n[o°]\s*:?|numéro\s*:?|ref[.\s]*:?)\s*([A-Z0-9\-_/]{4,25})',
    re.IGNORECASE
)

# IBAN / BIC
_RE_IBAN = re.compile(
    r'\b(FR\d{2}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{4}[\s]?\d{2,3})\b',
    re.IGNORECASE
)
_RE_BIC = re.compile(
    r'\b([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b'
)
_RE_BANQUE = re.compile(
    r'(?:domiciliation|banque|établissement)\s*[:\s]\s*([A-Za-zÀ-ÿ\s\-]{3,50}?)(?:\n|$)',
    re.IGNORECASE
)

#  Raison sociale 
_RE_RAISON_SOCIALE = re.compile(
    r'\b([A-ZÀÂÉÈÊÙÛÇ][A-Za-zÀ-ÿ\s\-&]{2,50}(?:SAS|SA|SARL|EURL|SNC|SCI|SASU|EI|EIRL|SCP|GIE|GIP|SELARL))\b'
    r'|'
    r'\b((?:SAS|SA|SARL|EURL|SNC|SCI|SASU|EI|EIRL)\s+[A-ZÀÂÉÈÊÙÛÇ][A-Za-zÀ-ÿ\s\-&]{2,50})\b'
)

# Adresse
_RE_ADRESSE = re.compile(
    r'\b(\d{1,5}[,\s]+(?:rue|avenue|boulevard|allée|impasse|chemin|route|place|'
    r'résidence|cité|domaine|voie)[,\s]+[A-Za-zÀ-ÿ\s\-,]{5,60}[,\s]+\d{5}[,\s]+[A-Za-zÀ-ÿ\s]{2,30})\b',
    re.IGNORECASE
)

# UTILITAIRES

def _clean_number(raw: str) -> Optional[str]:
    """Normaliser un identifiant numérique : supprimer espaces/tirets/points."""
    if not raw:
        return None
    return re.sub(r'[\s.\-]', '', raw.strip())


def _parse_amount(raw: str) -> Optional[float]:
    """Convertir une chaîne montant en float. Gère '1 234,56' et '1234.56'."""
    if not raw:
        return None
    s = raw.strip()
    # supprimer séparateurs de milliers
    s = re.sub(r'[\s\u00a0]', '', s)
    # distinguer virgule décimale vs point décimal
    if ',' in s and '.' in s:
        # exmeple pour se cas : 1.234,56 → 1234.56
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        val = float(s)
        #montant raisonnable pour une facture=
        if 0 < val < 10_000_000:
            return round(val, 2)
    except (ValueError, TypeError):
        pass
    return None


def _parse_date(raw: str) -> Optional[str]:
    """Parser une date et la retourner en format ISO YYYY-MM-DD."""
    if not raw:
        return None
    try:
        d = dateutil_parser.parse(raw, dayfirst=True, fuzzy=False)
        # rejeter les dates absurdes
        if d.year < 1990 or d.year > 2050:
            return None
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None


def _first_match(pattern: re.Pattern, text: str, group: int = 1) -> Optional[str]:
    """Retourner le premier groupe capturé d'un pattern, ou None."""
    m = pattern.search(text)
    return m.group(group).strip() if m else None


def _all_matches(pattern: re.Pattern, text: str, group: int = 1) -> List[str]:
    """Retourner tous les groupes capturés d'un pattern."""
    return [m.group(group).strip() for m in pattern.finditer(text) if m.group(group)]


# extraction par champ

def _extract_siret(text: str) -> Optional[str]:
    """
    Extraire le SIRET (14 chiffres).
    Stratégie : chercher d'abord près du mot-clé "SIRET", puis en fallback
    n'importe quel groupe de 14 chiffres (potentiellement espacés).
    """
    # Priorité : contexte explicite SIRET
    ctx = re.search(
        r'(?:siret|n[o°]?\s*siret)\s*[:\s]?\s*(\d[\d\s.\-]{12,18}\d)',
        text, re.IGNORECASE
    )
    if ctx:
        candidate = _clean_number(ctx.group(1))
        if candidate and len(candidate) == 14:
            return candidate

    # Fallback : toute séquence de 14 chiffres
    for m in _RE_SIRET.finditer(text):
        candidate = _clean_number(m.group(1))
        if candidate and len(candidate) == 14:
            return candidate

    return None


def _extract_siren(text: str, siret: Optional[str] = None) -> Optional[str]:
    # extraire SIREN si le SIRET est disponible
    if siret and len(siret) == 14:
        return siret[:9]

    ctx = re.search(
        r'(?:siren|n[o°]?\s*siren)\s*[:\s]?\s*(\d[\d\s.\-]{7,11}\d)',
        text, re.IGNORECASE
    )
    if ctx:
        candidate = _clean_number(ctx.group(1))
        if candidate and len(candidate) == 9:
            return candidate
    return None


def _extract_tva_number(text: str) -> Optional[str]:
    # extraire le numéro TVA
    m = _RE_TVA.search(text)
    if m:
        return _clean_number(m.group(1)).upper()
    return None


def _tva_rate_plausible(ht: float, tva: float) -> bool:
    # vérifie que le taux TVA implicite (tva/ht)
    if ht <= 0 or tva <= 0:
        return False
    rate = (tva / ht) * 100
    for legal in (20.0, 10.0, 8.5, 5.5, 2.1):
        if abs(rate - legal) <= 2.0:
            return True
    return False


def _extract_montants(text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    #Extraire HT, TVA (montant), TTC et si certains sont manquants tenter de les déduire des autres
    ht = _parse_amount(_first_match(_RE_MONTANT_HT, text))
    tva_amount = _parse_amount(_first_match(_RE_MONTANT_TVA, text))
    ttc = _parse_amount(_first_match(_RE_MONTANT_TTC, text))

    # déductions croisées
    if ht and tva_amount and not ttc:
        ttc = round(ht + tva_amount, 2)
    elif ht and ttc and not tva_amount:
        deduced = round(ttc - ht, 2)
        if deduced > 0 and _tva_rate_plausible(ht, deduced):
            tva_amount = deduced
    elif tva_amount and ttc and not ht:
        deduced = round(ttc - tva_amount, 2)
        if deduced > 0 and _tva_rate_plausible(deduced, tva_amount):
            ht = deduced

    return ht, tva_amount, ttc


def _extract_taux_tva(text: str, ht: Optional[float] = None, tva: Optional[float] = None) -> Optional[float]:
    # extraire le taux TVA
    m = _RE_TAUX_TVA.search(text)
    if m:
        try:
            taux = float(m.group(1).replace(',', '.'))
            # valeurs légales françaises
            if taux in (20.0, 10.0, 8.5, 5.5, 2.1):
                return taux
            # tolérance plus ou moins 0.5%
            for legal in (20.0, 10.0, 8.5, 5.5, 2.1):
                if abs(taux - legal) <= 0.5:
                    return legal
            return taux
        except ValueError:
            pass

    # fallback calculé 
    if ht and tva and ht > 0:
        taux = round((tva / ht) * 100, 1)
        for legal in (20.0, 10.0, 8.5, 5.5, 2.1):
            if abs(taux - legal) <= 1.0:
                return legal

    return None


def _extract_dates(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # extraire date émission, échéance et expiration
    emission = _parse_date(_first_match(_RE_DATE_EMISSION, text))
    echeance = _parse_date(_first_match(_RE_DATE_ECHEANCE, text))
    expiration = _parse_date(_first_match(_RE_DATE_EXPIRATION, text))

    # si pas de date d'émission, prendre la première date plausible dans le doc
    if not emission:
        for r in _RE_DATES:
            m = r.search(text)
            if m:
                raw = m.group(0)
                d = _parse_date(raw)
                if d:
                    emission = d
                    break

    return emission, echeance, expiration


def _extract_numero_document(text: str, doc_type: str) -> Optional[str]:
    # extraire le numéro de document selon le type
    if doc_type == "FACTURE":
        num = _first_match(_RE_NUM_FACTURE, text)
        if num:
            return num
    elif doc_type == "DEVIS":
        num = _first_match(_RE_NUM_DEVIS, text)
        if num:
            return num
    # fallback 
    return _first_match(_RE_NUM_DOCUMENT, text)


def _extract_iban(text: str) -> Optional[str]:
    m = _RE_IBAN.search(text)
    if m:
        return re.sub(r'\s', '', m.group(1).upper())
    return None


def _extract_bic(text: str) -> Optional[str]:
    # chercher dans contexte explicite
    ctx = re.search(r'(?:bic|swift)\s*[:\s]?\s*([A-Z]{4}[A-Z]{2}[A-Z0-9]{2,5})', text, re.IGNORECASE)
    if ctx:
        return ctx.group(1).upper()
    return None


def _extract_banque(text: str) -> Optional[str]:
    m = _RE_BANQUE.search(text)
    if m:
        return m.group(1).strip().title()
    return None


def _extract_raison_sociale_heuristic(text: str) -> Optional[str]:
    # retourne la raison sociale la plus proche du début du document
    m = _RE_RAISON_SOCIALE.search(text[:2000])
    if m:
        return (m.group(1) or m.group(2) or "").strip()
    return None


def _extract_raison_sociale(text: str) -> Optional[str]:
    return _extract_raison_sociale_heuristic(text)


def _extract_adresse(text: str) -> Optional[str]:
    m = _RE_ADRESSE.search(text)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip()
    return None


# extraction de la facture

def _extract_facture(text: str) -> dict:
    siret = _extract_siret(text)
    siren = _extract_siren(text, siret)
    ht, tva_amount, ttc = _extract_montants(text)
    taux = _extract_taux_tva(text, ht, tva_amount)
    emission, echeance, _ = _extract_dates(text)
    return {
        "siret": siret,
        "siren": siren,
        "tva_number": _extract_tva_number(text),
        "montant_ht": ht,
        "montant_tva": tva_amount,
        "montant_ttc": ttc,
        "taux_tva": taux,
        "date_emission": emission,
        "date_echeance": echeance,
        "date_expiration": None,
        "numero_document": _extract_numero_document(text, "FACTURE"),
        "raison_sociale": _extract_raison_sociale(text),
        "adresse": _extract_adresse(text),
    }


def _extract_devis(text: str) -> dict:
    siret = _extract_siret(text)
    siren = _extract_siren(text, siret)
    ht, tva_amount, ttc = _extract_montants(text)
    taux = _extract_taux_tva(text, ht, tva_amount)
    emission, echeance, expiration = _extract_dates(text)
    # si pas d expiration on prend l'échéance
    if not expiration:
        expiration = echeance
    return {
        "siret": siret,
        "siren": siren,
        "tva_number": _extract_tva_number(text),
        "montant_ht": ht,
        "montant_tva": tva_amount,
        "montant_ttc": ttc,
        "taux_tva": taux,
        "date_emission": emission,
        "date_echeance": expiration,
        "date_expiration": expiration,
        "numero_document": _extract_numero_document(text, "DEVIS"),
        "raison_sociale": _extract_raison_sociale(text),
        "adresse": _extract_adresse(text),
    }


def _extract_attestation_siret(text: str) -> dict:
    siret = _extract_siret(text)
    siren = _extract_siren(text, siret)
    _, _, expiration = _extract_dates(text)
    emission, _, _ = _extract_dates(text)
    return {
        "siret": siret,
        "siren": siren,
        "tva_number": _extract_tva_number(text),
        "date_emission": emission,
        "date_expiration": expiration,
        "raison_sociale": _extract_raison_sociale(text),
        "adresse": _extract_adresse(text),
    }


def _extract_urssaf(text: str) -> dict:
    siret = _extract_siret(text)
    siren = _extract_siren(text, siret)
    emission, _, expiration = _extract_dates(text)
    if not expiration:
        # pour l'URSSAF on cherche valable ou valable jusqu'au
        m = re.search(
            r'valable?\s+jusqu[\'au]*\s+(?:au)?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})',
            text, re.IGNORECASE
        )
        if m:
            expiration = _parse_date(m.group(1))
    return {
        "siret": siret,
        "siren": siren,
        "date_emission": emission,
        "date_expiration": expiration,
        "raison_sociale": _extract_raison_sociale(text),
        "adresse": _extract_adresse(text),
    }


def _extract_kbis(text: str) -> dict:
    siret = _extract_siret(text)
    siren = _extract_siren(text, siret)
    emission, _, expiration = _extract_dates(text)
    # si pas de date d'expiration explicite calculer à partir de l'émission
    if emission and not expiration:
        try:
            from datetime import timedelta
            d = datetime.strptime(emission, "%Y-%m-%d")
            expiration = (d + timedelta(days=90)).strftime("%Y-%m-%d")
        except Exception:
            pass
    return {
        "siret": siret,
        "siren": siren,
        "tva_number": _extract_tva_number(text),
        "date_emission": emission,
        "date_expiration": expiration,
        "raison_sociale": _extract_raison_sociale(text),
        "adresse": _extract_adresse(text),
    }


def _extract_rib(text: str) -> dict:
    siret = _extract_siret(text)
    siren = _extract_siren(text, siret)
    iban = _extract_iban(text)
    bic = _extract_bic(text)
    banque = _extract_banque(text)
    return {
        "siret": siret,
        "siren": siren,
        "iban": iban,
        "bic": bic,
        "banque": banque,
        "raison_sociale": _extract_raison_sociale(text),
        "adresse": _extract_adresse(text),
    }

# API PUBLIQUE

_EXTRACTORS = {
    "FACTURE": _extract_facture,
    "DEVIS": _extract_devis,
    "SIRET": _extract_attestation_siret,
    "URSSAF": _extract_urssaf,
    "KBIS": _extract_kbis,
    "RIB": _extract_rib,
    "UNKNOWN": _extract_facture,
}


def extract_fields(ocr_text: str, doc_type: str) -> dict:
    if not ocr_text or not ocr_text.strip():
        logger.warning("extract_fields_empty_text", doc_type=doc_type)
        return {}

    extractor = _EXTRACTORS.get(doc_type.upper(), _extract_facture)

    try:
        result = extractor(ocr_text)
        # nettoyer les valeurs None pour alléger MongoDB
        result = {k: v for k, v in result.items() if v is not None}

        fields_found = len(result)
        logger.info(
            "fields_extracted",
            doc_type=doc_type,
            fields_found=fields_found,
            fields=list(result.keys()),
        )
        return result

    except Exception as e:
        logger.error("field_extraction_failed", doc_type=doc_type, error=str(e))
        return {}
