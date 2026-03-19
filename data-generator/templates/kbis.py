"""Template KBIS — Extrait Kbis du Registre du Commerce."""

import random
from datetime import date, timedelta
from .helpers import fake, get_company


def _text_kbis(company=None, expired: bool = False, anomaly: str = None) -> str:
    company = company or get_company()

    if expired:
        date_emission = (date.today() - timedelta(days=random.randint(91, 365))).strftime("%d/%m/%Y")
    else:
        date_emission = (date.today() - timedelta(days=random.randint(1, 85))).strftime("%d/%m/%Y")

    gerant = fake.name()
    date_creation = (date.today() - timedelta(days=random.randint(365, 365 * 20))).strftime("%d/%m/%Y")
    date_naissance = fake.date_of_birth(minimum_age=25, maximum_age=70).strftime('%d/%m/%Y')
    activite = fake.bs().title()
    code_ape = f"{random.randint(1000, 9999)}{random.choice(['A','B','C','D','Z'])}"

    displayed_siret = company["siret"]
    if anomaly == "bad_siret":
        displayed_siret = get_company()["siret"]

    text = f"""EXTRAIT Kbis

REGISTRE DU COMMERCE ET DES SOCIÉTÉS
Tribunal de Commerce de {company['tribunal']}

Date de délivrance : {date_emission}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DÉSIGNATION

Dénomination sociale : {company['name']}
Forme juridique : {company['name'].split()[-1]}
Capital social : {company['capital']:,} €
Adresse du siège social : {company['address']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMMATRICULATION

Numéro d'immatriculation (SIREN) : {company['siren']}
SIRET siège : {displayed_siret}
N° TVA intracommunautaire : {company['tva']}
{company['rcs']}
Date d'immatriculation : {date_creation}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DIRIGEANTS

Gérant : {gerant}
Né(e) le : {date_naissance}
Nationalité : Française

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Activité principale : {activite}
Code APE/NAF : {code_ape}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Certifié conforme par le greffier du Tribunal de Commerce.
Cet extrait Kbis n'est valable que 3 mois à compter de sa date de délivrance.
Tout extrait périmé doit faire l'objet d'une nouvelle demande.

Greffe du Tribunal de Commerce de {company['tribunal']}
"""
    return text
