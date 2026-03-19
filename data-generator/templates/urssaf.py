"""Template URSSAF — Attestation de vigilance."""

import random
from datetime import date, timedelta
from .helpers import fake, get_company, _gen_date_past, _gen_date_future, _gen_date_expired


def _text_urssaf(company=None, expired: bool = False, anomaly: str = None) -> str:
    company = company or get_company()

    if expired:
        date_expiration = _gen_date_expired(1, 180)
        date_emission = (
            date.today() - timedelta(days=random.randint(181, 365))
        ).strftime("%d/%m/%Y")
    else:
        date_emission = _gen_date_past(1, 30)
        date_expiration = _gen_date_future(30, 180)

    displayed_siret = company["siret"]
    if anomaly == "bad_siret":
        displayed_siret = get_company()["siret"]

    region = random.choice(['Île-de-France', 'Rhône-Alpes', 'Provence', 'Bretagne', 'Occitanie'])
    ref = f"{random.randint(100000, 999999)}-{date.today().year}"

    text = f"""ATTESTATION DE VIGILANCE

Délivrée par l'URSSAF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

L'URSSAF atteste que l'entreprise désignée ci-après est à jour
de ses obligations de déclaration et de paiement de cotisations
et contributions sociales auprès de l'URSSAF.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENTREPRISE CONCERNÉE
Raison sociale : {company['name']}
SIRET : {displayed_siret}
SIREN : {company['siren']}
Adresse : {company['address']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VALIDITÉ DE L'ATTESTATION
Date d'émission : {date_emission}
Valable jusqu'au : {date_expiration}

Cette attestation est délivrée au titre de l'article L.243-15 du
Code de la Sécurité Sociale. Elle peut être vérifiée sur
net-entreprises.fr ou urssaf.fr.

Cotisations sociales : EN RÈGLE
Contributions patronales : EN RÈGLE
Régularité de situation : CONFORME

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

URSSAF — {region}
Document électronique authentique — Vérification possible sur urssaf.fr
Référence : {ref}
"""
    return text
