"""
Template FACTURE — 3 variantes de mise en page.

Variantes pour que le RF apprenne les contenus, pas juste la position du mot-clé :
  - layout A : en-tête émetteur puis "FACTURE N°..."  (le plus courant)
  - layout B : titre centré "FACTURE" en haut, puis coordonnées
  - layout C : style récapitulatif avec "Objet : Règlement de la prestation"
"""

import random
from datetime import date, timedelta
from .helpers import fake, get_company, _gen_amounts, _gen_date_past


def _text_facture(vendor=None, client=None, anomaly=None) -> str:
    vendor = vendor or get_company()
    client = client or get_company()
    amounts = _gen_amounts()
    num = f"FACT-{date.today().year}-{random.randint(1000, 9999)}"
    date_emission = _gen_date_past(1, 90)
    date_echeance = (date.today() + timedelta(days=random.choice([30, 45, 60, 90]))).strftime("%d/%m/%Y")

    lines = [random.choice([
        f"{fake.bs().title()} - Prestation de service",
        f"Mission de conseil — {fake.catch_phrase()}",
        f"Fourniture de {fake.word()} - lot {random.randint(1, 10)}",
        f"Développement logiciel - phase {random.randint(1, 5)}",
        f"Maintenance et support technique - {fake.bs()}",
        f"Formation professionnelle - {fake.job()}",
    ]) for _ in range(random.randint(1, 4))]

    items_ht = [round(amounts["ht"] / len(lines), 2) for _ in lines]
    items_ht[-1] = round(amounts["ht"] - sum(items_ht[:-1]), 2)

    displayed_siret = vendor["siret"]
    if anomaly == "bad_siret":
        displayed_siret = get_company()["siret"]

    layout = random.choice(["A", "B", "C"])

    if layout == "A":
        # Layout A : en-tête fournisseur d'abord, puis numéro de facture
        text = f"""{vendor['name']}
{vendor['address']}
SIRET : {displayed_siret}  |  TVA : {vendor['tva']}
Tél : {vendor['phone']}  |  {vendor['email']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FACTURE N° {num}

Date d'émission : {date_emission}
Date d'échéance : {date_echeance}

DESTINATAIRE
{client['name']}
{client['address']}
SIRET : {client['siret']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DÉTAIL DES PRESTATIONS FACTURÉES

"""
    elif layout == "B":
        # Layout B : titre centré traditionnel
        text = f"""FACTURE

Numéro de facture : {num}
Date d'émission : {date_emission}
Date d'échéance : {date_echeance}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VENDEUR (Émetteur)
{vendor['name']}
{vendor['address']}
SIRET : {displayed_siret}
N° TVA Intracommunautaire : {vendor['tva']}
Tél : {vendor['phone']} - Email : {vendor['email']}

ACHETEUR (Client)
{client['name']}
{client['address']}
SIRET : {client['siret']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DÉSIGNATION                                    MONTANT HT

"""
    else:
        # Layout C : style récapitulatif professionnel
        text = f"""DOCUMENT DE FACTURATION

Réf. : {num}
Émis le : {date_emission}  —  Paiement attendu le : {date_echeance}

De : {vendor['name']} ({displayed_siret})
     {vendor['address']}
     TVA : {vendor['tva']}

À  : {client['name']}
     {client['address']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objet : Règlement des prestations réalisées

LIGNES DE FACTURATION

"""

    for line, item_ht in zip(lines, items_ht):
        text += f"  • {line:<43} {item_ht:>10.2f} €\n"

    text += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total HT                                     {amounts['ht']:>10.2f} €
TVA {amounts['taux']}%                       {amounts['tva']:>10.2f} €
                                            ─────────────
TOTAL TTC                                    {amounts['ttc']:>10.2f} €

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONDITIONS DE RÈGLEMENT

Mode de règlement : Virement bancaire
IBAN : {vendor['iban']}
BIC : {vendor['bic']}
Date d'échéance de paiement : {date_echeance}

Pénalités de retard : 3 fois le taux légal en vigueur, applicables dès le lendemain
de la date d'échéance de la présente facture.
Escompte pour paiement anticipé : néant
Indemnité forfaitaire de recouvrement : 40 €

Cette facture a été émise conformément aux articles L441-3 et L441-9 du Code de commerce.
En cas de litige relatif à cette facture, le tribunal compétent sera saisi.
"""
    return text
