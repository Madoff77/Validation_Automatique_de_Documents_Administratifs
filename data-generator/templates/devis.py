import random
from datetime import date, timedelta
from .helpers import fake, get_company, _gen_amounts, _gen_date_past


def _text_devis(vendor=None, client=None, anomaly=None) -> str:
    vendor = vendor or get_company()
    client = client or get_company()
    amounts = _gen_amounts()
    num = f"DEVIS-{date.today().year}-{random.randint(100, 999)}"
    date_emission = _gen_date_past(1, 30)
    validity_days = random.choice([15, 30, 45, 60, 90])
    date_validite = (date.today() + timedelta(days=validity_days)).strftime("%d/%m/%Y")
    objet = fake.catch_phrase()

    layout = random.choice(["A", "B", "C"])

    if layout == "A":
        header = f"""DEVIS

Référence devis : {num}
Date d'établissement : {date_emission}
Valable jusqu'au : {date_validite}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ÉMETTEUR
{vendor['name']}
{vendor['address']}
SIRET : {vendor['siret']}
N° TVA : {vendor['tva']}

CLIENT
{client['name']}
{client['address']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objet : {objet}

PRESTATIONS PROPOSÉES

"""
    elif layout == "B":
        header = f"""PROPOSITION COMMERCIALE

{vendor['name']}
{vendor['address']}
SIRET : {vendor['siret']}  —  TVA : {vendor['tva']}

Adressée à : {client['name']}, {client['address']}

Référence : {num}  |  Établie le {date_emission}  |  Validité : {date_validite}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objet de la proposition : {objet}

DÉTAIL DES PRESTATIONS PROPOSÉES

"""
    else:
        header = f"""OFFRE DE SERVICES — DEVIS N° {num}

De : {vendor['name']}
     {vendor['address']}
     SIRET {vendor['siret']}

Pour : {client['name']}
       {client['address']}

Date : {date_emission}  —  Validité de l'offre : jusqu'au {date_validite}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Objet de la mission : {objet}

ÉLÉMENTS CHIFFRÉS DE LA PROPOSITION

"""

    n_items = random.randint(2, 5)
    item_ht = round(amounts["ht"] / n_items, 2)
    body = ""
    for _ in range(n_items):
        unit_ht = item_ht + round(random.uniform(-50, 50), 2)
        body += f"• {fake.bs().title()}\n"
        body += f"  Quantité : {random.randint(1, 10)} - Prix unitaire HT : {unit_ht:.2f} €\n\n"

    footer = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sous-total HT        {amounts['ht']:.2f} €
TVA {amounts['taux']}%         {amounts['tva']:.2f} €
Total TTC            {amounts['ttc']:.2f} €

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONDITIONS D'ACCEPTATION DU DEVIS

Ce devis est valable {validity_days} jours à compter de sa date d'établissement.
Ce document est un devis non contractuel jusqu'à signature des deux parties.

Pour accepter cette proposition commerciale, veuillez retourner ce devis signé
avec la mention manuscrite "Bon pour accord" et "Lu et approuvé",
accompagné d'un acompte de {int(amounts['ttc'] * 0.3):.0f} € (30% du montant TTC).

Sous réserve d'acceptation du devis dans le délai de validité indiqué.
Passé ce délai, ce devis sera caduc et devra faire l'objet d'une nouvelle proposition.

Acceptation du devis (précédée de "Bon pour accord") :

___________________   Date : _______________
"""
    return header + body + footer
