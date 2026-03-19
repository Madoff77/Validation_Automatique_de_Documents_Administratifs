"""Template RIB — Relevé d'Identité Bancaire."""

import random
from .helpers import fake, get_company, _gen_date_past


def _text_rib(company=None, anomaly: str = None) -> str:
    company = company or get_company()
    bank = random.choice([
        "BNP Paribas", "Société Générale", "Crédit Agricole",
        "LCL", "Banque Populaire", "Caisse d'Épargne", "CIC"
    ])
    agence = fake.city()

    text = f"""RELEVÉ D'IDENTITÉ BANCAIRE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TITULAIRE DU COMPTE

Raison sociale : {company['name']}
Adresse : {company['address']}
SIRET : {company['siret']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COORDONNÉES BANCAIRES

IBAN : {company['iban']}
BIC (SWIFT) : {company['bic']}

Domiciliation : {bank}
Agence : {agence}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Code banque   : {random.randint(10000, 99999)}
Code guichet  : {random.randint(10000, 99999)}
Numéro compte : {random.randint(10000000000, 99999999999)}
Clé RIB       : {random.randint(10, 97):02d}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ce relevé d'identité bancaire (RIB) est fourni à titre informatif.
Il permet les virements et les prélèvements automatiques.

Document émis le {_gen_date_past(1, 30)}
"""
    return text
