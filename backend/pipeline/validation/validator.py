"""
Moteur de validation métier.

Deux niveaux de validation :
1. Intra-document : champs obligatoires, formats, cohérence interne (HT+TVA=TTC)
2. Inter-documents : cohérence SIRET entre docs du même fournisseur,
   expirations URSSAF/Kbis, doublons

Chaque règle retourne un ValidationCheck et éventuellement une anomalie à persister.
Les anomalies sont séparées des checks : les checks sont stockés sur le document,
les anomalies dans la collection dédiée pour le dashboard compliance.

Sévérités :
  error   → bloquant, non-conforme légalement
  warning → à surveiller, action recommandée
  info    → informatif
"""

from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

# Tolérance pour la vérification HT+TVA=TTC (1€ ou 0.5%)
TVA_COHERENCE_TOLERANCE_EUR = 1.0
TVA_COHERENCE_TOLERANCE_PCT = 0.005

# Durée max de validité d'un Kbis (réglementation française)
KBIS_MAX_VALIDITY_DAYS = 90

# Durée d'alerte avant expiration (prévenir 30 jours avant)
EXPIRATION_WARNING_DAYS = 30


# UTILITAIRES

def _check(rule: str, ok: bool, message_ok: str, message_fail: str,
           severity: str = "error", details: Optional[dict] = None) -> dict:
    """Construire un ValidationCheck dict."""
    return {
        "rule": rule,
        "status": "ok" if ok else severity,
        "message": message_ok if ok else message_fail,
        "details": details or {},
    }


def _make_anomaly(
    supplier_id: str,
    document_id: str,
    anomaly_type: str,
    severity: str,
    message: str,
    details: dict = None,
    related_document_id: str = None,
) -> dict:
    return {
        "supplier_id": supplier_id,
        "document_id": document_id,
        "related_document_id": related_document_id,
        "type": anomaly_type,
        "severity": severity,
        "message": message,
        "details": details or {},
    }


def _parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


# VALIDATION SIRET

def _luhn_check_siret(siret: str) -> bool:
    """
    Validation Luhn du SIRET (algorithme de Luhn mod 10).
    Référence : INSEE — tous les SIRET valides passent ce test.
    Exception : entreprises La Poste (débutant par 356) utilisent règle spéciale.
    """
    if not siret or len(siret) != 14 or not siret.isdigit():
        return False

    # Cas spécial La Poste
    if siret.startswith("356"):
        return sum(int(d) for d in siret) % 5 == 0

    total = 0
    for i, digit in enumerate(reversed(siret)):
        n = int(digit)
        if i % 2 == 1:  # positions paires depuis la droite (1-indexé)
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_siret_format(siret: Optional[str]) -> Tuple[bool, str]:
    if not siret:
        return False, "SIRET absent"
    if len(siret) != 14:
        return False, f"SIRET longueur incorrecte : {len(siret)} chiffres (attendu 14)"
    if not siret.isdigit():
        return False, "SIRET contient des caractères non numériques"
    if not _luhn_check_siret(siret):
        return False, f"SIRET invalide (échec contrôle Luhn) : {siret}"
    return True, "SIRET valide"


# VALIDATION IBAN

def validate_iban_format(iban: Optional[str]) -> Tuple[bool, str]:
    if not iban:
        return False, "IBAN absent"
    iban = iban.replace(" ", "").upper()
    if not iban.startswith("FR") or len(iban) != 27:
        return False, f"Format IBAN français incorrect : {iban}"
    # Vérification MOD-97 standard
    rearranged = iban[4:] + iban[:4]
    numeric = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    try:
        if int(numeric) % 97 != 1:
            return False, f"IBAN invalide (échec contrôle MOD-97) : {iban}"
    except ValueError:
        return False, "IBAN contient des caractères invalides"
    return True, "IBAN valide"


# VALIDATION TVA NUMÉRO

def validate_tva_number(tva: Optional[str], siren: Optional[str] = None) -> Tuple[bool, str]:
    """Vérifier cohérence TVA ↔ SIREN (clé calculée)."""
    if not tva:
        return False, "Numéro TVA absent"
    tva_clean = tva.replace(" ", "").upper()
    if not tva_clean.startswith("FR") or len(tva_clean) != 13:
        return False, f"Format TVA incorrect : {tva_clean}"

    if siren and len(siren) == 9 and siren.isdigit():
        expected_key = (12 + 3 * (int(siren) % 97)) % 97
        tva_key_str = tva_clean[2:4]
        try:
            tva_key = int(tva_key_str)
            if tva_key != expected_key:
                return False, f"Clé TVA incohérente avec SIREN (attendu FR{expected_key:02d}, trouvé FR{tva_key:02d})"
        except ValueError:
            pass  # Clé alphanumérique — on ne valide pas la cohérence SIREN
    return True, "Numéro TVA valide"


# VALIDATION COHÉRENCE TVA (HT × taux = TVA, HT + TVA = TTC)

def validate_tva_coherence(
    ht: Optional[float],
    tva_amount: Optional[float],
    ttc: Optional[float],
    taux: Optional[float],
) -> Tuple[bool, str, dict]:
    """Vérifier HT + TVA = TTC avec tolérance."""
    details = {"ht": ht, "tva": tva_amount, "ttc": ttc, "taux": taux}

    if not all([ht is not None, tva_amount is not None, ttc is not None]):
        return True, "Vérification impossible (champs manquants)", details

    expected_ttc = round(ht + tva_amount, 2)
    ecart = abs(expected_ttc - ttc)

    # Tolérance absolue ET relative
    tolerance = max(TVA_COHERENCE_TOLERANCE_EUR, abs(ttc) * TVA_COHERENCE_TOLERANCE_PCT)

    if ecart > tolerance:
        details["ecart"] = round(ecart, 2)
        details["expected_ttc"] = expected_ttc
        return False, f"Incohérence HT+TVA≠TTC : {ht} + {tva_amount} = {expected_ttc} ≠ {ttc} (écart {ecart:.2f}€)", details

    # Vérifier aussi HT × taux = TVA si taux disponible
    if taux and ht:
        expected_tva = round(ht * taux / 100, 2)
        ecart_tva = abs(expected_tva - tva_amount)
        if ecart_tva > tolerance:
            details["expected_tva"] = expected_tva
            details["ecart_tva"] = round(ecart_tva, 2)
            return False, f"Incohérence HT×taux≠TVA : {ht} × {taux}% = {expected_tva} ≠ {tva_amount} (écart {ecart_tva:.2f}€)", details

    return True, "Cohérence TVA vérifiée", details


# VALIDATION DATES D'EXPIRATION

def validate_expiration(
    date_expiration: Optional[str],
    doc_type: str,
    now: Optional[datetime] = None,
) -> Tuple[str, str, str]:  # (status, message, anomaly_type)
    """
    Vérifier si une date d'expiration est dans les limites acceptables.
    Retourne (status: ok/warning/error, message, anomaly_type).
    """
    now = now or datetime.now(timezone.utc)
    exp = _parse_iso_date(date_expiration)

    if not exp:
        if doc_type in ("URSSAF", "KBIS"):
            return "warning", f"Date d'expiration non trouvée pour {doc_type}", "MISSING_FIELD"
        return "ok", "Pas de date d'expiration requise", ""

    delta = exp - now

    if delta.days < 0:
        # Expiré
        anomaly_type = "URSSAF_EXPIRED" if doc_type == "URSSAF" else "KBIS_EXPIRED" if doc_type == "KBIS" else "DATE_EXPIRED"
        return "error", f"Document {doc_type} expiré depuis {abs(delta.days)} jours ({date_expiration})", anomaly_type

    if delta.days <= EXPIRATION_WARNING_DAYS:
        anomaly_type = "DATE_EXPIRED"
        return "warning", f"Document {doc_type} expire dans {delta.days} jours ({date_expiration})", anomaly_type

    return "ok", f"Document {doc_type} valide jusqu'au {date_expiration} ({delta.days} jours restants)", ""


def validate_kbis_age(
    date_emission: Optional[str],
    now: Optional[datetime] = None,
) -> Tuple[str, str]:
    """
    Kbis légalement valide uniquement si émis il y a moins de 3 mois.
    Retourne (status, message).
    """
    now = now or datetime.now(timezone.utc)
    emission = _parse_iso_date(date_emission)

    if not emission:
        return "warning", "Date d'émission Kbis non trouvée, impossibilité de vérifier la validité légale"

    age_days = (now - emission).days

    if age_days > KBIS_MAX_VALIDITY_DAYS:
        return "error", f"Kbis trop ancien : émis il y a {age_days} jours (limite légale : {KBIS_MAX_VALIDITY_DAYS} jours)"

    remaining = KBIS_MAX_VALIDITY_DAYS - age_days
    if remaining <= 14:
        return "warning", f"Kbis bientôt invalide : {remaining} jours restants (limite {KBIS_MAX_VALIDITY_DAYS} jours)"

    return "ok", f"Kbis valide ({age_days} jours, limite {KBIS_MAX_VALIDITY_DAYS} jours)"


# VALIDATION INTER-DOCUMENTS (cohérence fournisseur)

def validate_siret_consistency(
    current_doc: dict,
    sibling_docs: List[dict],
) -> List[Tuple[bool, str, dict]]:
    """
    Vérifier que le SIRET du document courant est cohérent avec
    les autres documents du même fournisseur.
    Retourne une liste de (ok, message, details).
    """
    issues = []
    current_siret = current_doc.get("extracted", {}).get("siret")
    if not current_siret:
        return issues

    for sibling in sibling_docs:
        sibling_siret = sibling.get("extracted", {}).get("siret")
        if not sibling_siret:
            continue
        if sibling_siret != current_siret:
            issues.append((
                False,
                f"Incohérence SIRET : {current_doc['original_filename']} ({current_siret}) "
                f"≠ {sibling['original_filename']} ({sibling_siret})",
                {
                    "current_siret": current_siret,
                    "sibling_siret": sibling_siret,
                    "sibling_document_id": sibling["document_id"],
                    "sibling_filename": sibling["original_filename"],
                }
            ))

    return issues


# RÈGLES PAR TYPE DE DOCUMENT

def _validate_facture(doc: dict, sibling_docs: List[dict]) -> Tuple[List[dict], List[dict]]:
    """
    Validation d'une facture.

    Philosophie : pas de législation imposant un format strict de facture
    entre professionnels en France (art. L441-9 CGI liste les mentions
    obligatoires mais l'absence d'un champ n'est pas un motif de rejet
    d'un point de vue compliance fournisseur).

    Règles appliquées :
    - SIRET : vérifié UNIQUEMENT s'il a été extrait par OCR. Absent = pas de check
      (l'OCR ne l'a pas trouvé, ce n'est pas un défaut du document).
    - Cohérence TVA (HT + TVA = TTC) : vérifiée si au moins TTC extrait.
      Incohérence avérée = anomalie warning.
    - Champs financiers manquants : INFO seulement, pas d'anomalie
      (c'est une limite OCR, non un problème de conformité).
    - SIRET inter-docs : si SIRET extrait, vérifier cohérence avec autres docs
      du même fournisseur (incohérence = anomalie error).
    """
    checks = []
    anomalies = []
    extracted = doc.get("extracted", {})
    sid = doc["supplier_id"]
    did = doc["document_id"]

    # 1. SIRET — seulement si extrait par OCR
    siret = extracted.get("siret")
    if siret:
        valid_siret, msg_siret = validate_siret_format(siret)
        checks.append(_check("siret_format", valid_siret, "SIRET valide", msg_siret,
                              severity="warning", details={"siret": siret}))
        if not valid_siret:
            anomalies.append(_make_anomaly(sid, did, "FORMAT_ERROR", "warning",
                                            f"Facture {doc['original_filename']} : {msg_siret}",
                                            {"siret": siret}))

    # 2. Cohérence TVA — seulement si des montants ont été extraits
    ht = extracted.get("montant_ht")
    tva = extracted.get("montant_tva")
    ttc = extracted.get("montant_ttc")
    taux = extracted.get("taux_tva")
    if any(v is not None for v in [ht, tva, ttc]):
        tva_ok, tva_msg, tva_details = validate_tva_coherence(ht, tva, ttc, taux)
        checks.append(_check("tva_coherence", tva_ok, "Cohérence TVA OK", tva_msg,
                              severity="warning", details=tva_details))
        if not tva_ok:
            anomalies.append(_make_anomaly(sid, did, "TVA_INCOHERENCE", "warning", tva_msg, tva_details))

    # 3. Présence des champs financiels clés — INFO uniquement, pas d'anomalie
    #    (champ non extrait = limite OCR, pas un défaut du document)
    for field_name, label in [
        ("montant_ttc",   "Montant TTC"),
        ("montant_ht",    "Montant HT"),
        ("raison_sociale","Raison sociale vendeur"),
    ]:
        present = extracted.get(field_name) is not None
        checks.append({
            "rule": f"field_{field_name}",
            "status": "ok" if present else "info",
            "message": f"{label} extrait" if present else f"{label} non extrait par OCR",
            "details": {"field": field_name},
        })

    # 4. Cohérence SIRET inter-docs — seulement si SIRET présent
    if siret:
        for ok, msg, details in validate_siret_consistency(doc, sibling_docs):
            checks.append(_check("siret_consistency", ok, "SIRET cohérent entre documents", msg,
                                  severity="error", details=details))
            if not ok:
                anomalies.append(_make_anomaly(
                    sid, did, "SIRET_MISMATCH", "error", msg, details,
                    related_document_id=details.get("sibling_document_id"),
                ))

    return checks, anomalies


def _validate_devis(doc: dict, sibling_docs: List[dict]) -> Tuple[List[dict], List[dict]]:
    """
    Validation d'un devis.

    Philosophie : le devis est un document commercial, pas un document de
    conformité légale. On vérifie la cohérence financière si les montants
    sont disponibles, et la validité temporelle.
    Aucune exigence de SIRET (non obligatoire sur un devis).
    """
    checks = []
    anomalies = []
    extracted = doc.get("extracted", {})
    sid = doc["supplier_id"]
    did = doc["document_id"]

    # 1. Cohérence TVA — seulement si des montants ont été extraits
    ht = extracted.get("montant_ht")
    tva = extracted.get("montant_tva")
    ttc = extracted.get("montant_ttc")
    taux = extracted.get("taux_tva")
    if any(v is not None for v in [ht, tva, ttc]):
        tva_ok, tva_msg, tva_details = validate_tva_coherence(ht, tva, ttc, taux)
        checks.append(_check("tva_coherence", tva_ok, "Cohérence TVA OK", tva_msg,
                              severity="warning", details=tva_details))
        if not tva_ok:
            anomalies.append(_make_anomaly(sid, did, "TVA_INCOHERENCE", "warning", tva_msg, tva_details))

    # 2. Présence des champs clés — INFO uniquement
    for field_name, label in [
        ("montant_ttc",   "Montant TTC"),
        ("raison_sociale","Raison sociale émetteur"),
        ("date_expiration","Date de validité du devis"),
    ]:
        present = extracted.get(field_name) is not None
        checks.append({
            "rule": f"field_{field_name}",
            "status": "ok" if present else "info",
            "message": f"{label} extrait" if present else f"{label} non extrait par OCR",
            "details": {"field": field_name},
        })

    # 3. Date d'expiration — warning si devis expiré (anomalie commerciale)
    exp_date = extracted.get("date_expiration")
    if exp_date:
        status, msg, atype = validate_expiration(exp_date, "DEVIS")
        checks.append({"rule": "devis_expiration", "status": status, "message": msg,
                        "details": {"date_expiration": exp_date}})
        if status == "error" and atype:
            anomalies.append(_make_anomaly(sid, did, atype, "warning", msg,
                                            {"date_expiration": exp_date}))

    return checks, anomalies


def _validate_urssaf(doc: dict, sibling_docs: List[dict]) -> Tuple[List[dict], List[dict]]:
    checks = []
    anomalies = []
    extracted = doc.get("extracted", {})
    sid = doc["supplier_id"]
    did = doc["document_id"]

    siret = extracted.get("siret")

    # Format SIRET
    valid_siret, msg_siret = validate_siret_format(siret)
    checks.append(_check("siret_format", valid_siret, "SIRET valide", msg_siret,
                          severity="error", details={"siret": siret}))

    # Expiration URSSAF — critique
    exp_date = extracted.get("date_expiration")
    status, msg, atype = validate_expiration(exp_date, "URSSAF")
    severity_map = {"ok": "ok", "warning": "warning", "error": "error"}
    checks.append({"rule": "urssaf_expiration", "status": status, "message": msg,
                   "details": {"date_expiration": exp_date}})
    if status in ("error", "warning") and atype:
        anomalies.append(_make_anomaly(
            sid, did, atype, severity_map.get(status, "warning"), msg,
            {"date_expiration": exp_date}
        ))

    # Champ obligatoire
    if not exp_date:
        checks.append(_check("field_date_expiration", False,
                              "Date expiration présente", "Date d'expiration URSSAF manquante",
                              severity="error"))
        anomalies.append(_make_anomaly(sid, did, "MISSING_FIELD", "error",
                                        f"Attestation URSSAF {doc['original_filename']} : date d'expiration manquante",
                                        {"field": "date_expiration"}))

    # Cohérence SIRET inter-docs
    for ok, msg, details in validate_siret_consistency(doc, sibling_docs):
        checks.append(_check("siret_consistency", ok, "SIRET cohérent", msg,
                              severity="error", details=details))
        if not ok:
            anomalies.append(_make_anomaly(
                sid, did, "SIRET_MISMATCH", "error", msg, details,
                related_document_id=details.get("sibling_document_id"),
            ))

    return checks, anomalies


def _validate_kbis(doc: dict, sibling_docs: List[dict]) -> Tuple[List[dict], List[dict]]:
    checks = []
    anomalies = []
    extracted = doc.get("extracted", {})
    sid = doc["supplier_id"]
    did = doc["document_id"]

    siret = extracted.get("siret")
    date_emission = extracted.get("date_emission")

    # Format SIRET
    valid_siret, msg_siret = validate_siret_format(siret)
    checks.append(_check("siret_format", valid_siret, "SIRET valide", msg_siret,
                          severity="error", details={"siret": siret}))

    # Validité légale Kbis (< 3 mois)
    age_status, age_msg = validate_kbis_age(date_emission)
    checks.append({"rule": "kbis_age", "status": age_status, "message": age_msg,
                   "details": {"date_emission": date_emission}})
    if age_status == "error":
        anomalies.append(_make_anomaly(sid, did, "KBIS_EXPIRED", "error", age_msg,
                                        {"date_emission": date_emission}))
    elif age_status == "warning":
        anomalies.append(_make_anomaly(sid, did, "KBIS_EXPIRED", "warning", age_msg,
                                        {"date_emission": date_emission}))

    # Cohérence SIRET inter-docs
    for ok, msg, details in validate_siret_consistency(doc, sibling_docs):
        checks.append(_check("siret_consistency", ok, "SIRET cohérent", msg,
                              severity="error", details=details))
        if not ok:
            anomalies.append(_make_anomaly(
                sid, did, "SIRET_MISMATCH", "error", msg, details,
                related_document_id=details.get("sibling_document_id"),
            ))

    return checks, anomalies


def _validate_rib(doc: dict, sibling_docs: List[dict]) -> Tuple[List[dict], List[dict]]:
    checks = []
    anomalies = []
    extracted = doc.get("extracted", {})
    sid = doc["supplier_id"]
    did = doc["document_id"]

    # IBAN
    iban = extracted.get("iban")
    valid_iban, msg_iban = validate_iban_format(iban)
    checks.append(_check("iban_format", valid_iban, "IBAN valide", msg_iban,
                          severity="warning", details={"iban": iban}))
    if not valid_iban and iban:
        anomalies.append(_make_anomaly(sid, did, "FORMAT_ERROR", "warning",
                                        f"RIB {doc['original_filename']} : {msg_iban}",
                                        {"iban": iban}))

    # BIC présent
    bic = extracted.get("bic")
    checks.append(_check("bic_present", bic is not None,
                          "BIC présent", "BIC absent du RIB",
                          severity="info"))

    # Cohérence SIRET inter-docs
    for ok, msg, details in validate_siret_consistency(doc, sibling_docs):
        checks.append(_check("siret_consistency", ok, "SIRET cohérent", msg,
                              severity="error", details=details))
        if not ok:
            anomalies.append(_make_anomaly(
                sid, did, "SIRET_MISMATCH", "error", msg, details,
                related_document_id=details.get("sibling_document_id"),
            ))

    return checks, anomalies


def _validate_siret_doc(doc: dict, sibling_docs: List[dict]) -> Tuple[List[dict], List[dict]]:
    checks = []
    anomalies = []
    extracted = doc.get("extracted", {})
    sid = doc["supplier_id"]
    did = doc["document_id"]

    siret = extracted.get("siret")
    valid_siret, msg_siret = validate_siret_format(siret)
    checks.append(_check("siret_format", valid_siret, "SIRET valide", msg_siret,
                          severity="error", details={"siret": siret}))
    if not valid_siret and siret:
        anomalies.append(_make_anomaly(sid, did, "FORMAT_ERROR", "error",
                                        f"Attestation SIRET {doc['original_filename']} : {msg_siret}",
                                        {"siret": siret}))

    for ok, msg, details in validate_siret_consistency(doc, sibling_docs):
        checks.append(_check("siret_consistency", ok, "SIRET cohérent", msg,
                              severity="error", details=details))
        if not ok:
            anomalies.append(_make_anomaly(
                sid, did, "SIRET_MISMATCH", "error", msg, details,
                related_document_id=details.get("sibling_document_id"),
            ))

    return checks, anomalies


# DISPATCH ET API PUBLIQUE

_VALIDATORS = {
    "FACTURE": _validate_facture,
    "DEVIS": _validate_devis,
    "URSSAF": _validate_urssaf,
    "KBIS": _validate_kbis,
    "RIB": _validate_rib,
    "SIRET": _validate_siret_doc,
    "UNKNOWN": lambda doc, siblings: ([], []),
}


def validate_document(
    doc: dict,
    sibling_docs: List[dict],
) -> Tuple[dict, List[dict]]:
    """
    Valider un document et retourner :
    - validation_result : dict {status, checks} pour MongoDB documents
    - anomalies : list de dicts à insérer dans collection anomalies

    sibling_docs : autres documents traités du même fournisseur
    """
    doc_type = doc.get("doc_type", "UNKNOWN")
    validator = _VALIDATORS.get(doc_type, _VALIDATORS["UNKNOWN"])

    try:
        checks, anomalies = validator(doc, sibling_docs)
    except Exception as e:
        logger.error("validation_failed", doc_id=doc.get("document_id"), error=str(e))
        checks = []
        anomalies = []

    # Calcul statut global — "info" est informatif, n'impacte pas le statut
    statuses = [c.get("status", "ok") for c in checks if c.get("status") not in ("ok", "info")]
    if "error" in statuses:
        global_status = "error"
    elif "warning" in statuses:
        global_status = "warning"
    else:
        global_status = "ok"

    validation_result = {
        "status": global_status,
        "checks": checks,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "document_validated",
        document_id=doc.get("document_id"),
        doc_type=doc_type,
        status=global_status,
        checks=len(checks),
        anomalies=len(anomalies),
    )

    return validation_result, anomalies
