"""Template SIRET — Attestation de situation au Répertoire SIRENE."""

import random
from datetime import date
from .helpers import fake, get_company, _gen_date_past


def _text_attestation_siret(company=None, anomaly: str = None) -> str:
    company = company or get_company()
    date_emission = _gen_date_past(1, 90)
    code_ape = f"{random.randint(1000, 9999)}{random.choice(['A','B','C'])}"
    date_creation = fake.date_between(start_date='-20y', end_date='-1y').strftime('%d/%m/%Y')
    ref = random.randint(10000000, 99999999)

    displayed_siret = company["siret"]
    if anomaly == "bad_siret":
        displayed_siret = get_company()["siret"]

    text = f"""ATTESTATION DE SITUATION AU RÉPERTOIRE SIRENE

Délivrée par l'INSEE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

L'INSEE atteste de l'existence légale de l'établissement suivant
dans le Répertoire National des Entreprises et des Établissements (SIRENE).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ÉTABLISSEMENT

Numéro SIRET : {displayed_siret}
Numéro SIREN : {company['siren']}
Raison sociale : {company['name']}
Adresse : {company['address']}
Activité (code APE) : {code_ape}
Date de création : {date_creation}
Situation : ACTIF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date d'édition : {date_emission}
Référence : {ref}

Cette attestation est délivrée en application de l'article R.123-220
du Code de Commerce. Peut être vérifiée sur annuaire-entreprises.data.gouv.fr

INSEE — Direction Générale
"""
    return text
