"""
Générateur de documents administratifs synthétiques.

Produit :
  - Texte brut (pour entraînement classifier)
  - PDF (pour tests OCR pipeline)
  - Images dégradées (scans simulés)

Types de documents : FACTURE, DEVIS, SIRET, URSSAF, KBIS, RIB
Dégradations simulées : flou, rotation, bruit, basse résolution, combiné

Usage :
  python generator.py --mode training --n-per-class 150 --output data/training
  python generator.py --mode demo --output data/demo
  python generator.py --mode pdf --doc-type FACTURE --n 5 --output data/pdfs
"""

import os
import json
import random
import argparse
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

import numpy as np
from faker import Faker
from PIL import Image, ImageFilter, ImageEnhance
import cv2
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("INSEE_API_KEY")
if not API_KEY:
    print("Clé API SIRENE non trouvée. Veuillez définir INSEE_API_KEY dans votre .env.")

fake = Faker("fr_FR")
Faker.seed(42)
random.seed(42)
np.random.seed(42)

def fetch_sirene_companies(n_companies: int = 100) -> list:
    """
    Récupère un lot d'entreprises réelles actives via l'API SIRENE.
    """
    print(f"Récupération de {n_companies} entreprises depuis l'API SIRENE...")
    url = "https://api.insee.fr/api-sirene/3.11/siret"
    headers = {
        "X-INSEE-Api-Key-Integration": API_KEY,
        "Accept": "application/json"
    }

    params = {
        "q": "periode(etatAdministratifEtablissement:A)",
        "nombre": min(n_companies, 1000),
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'appel à l'API SIRENE : {e}")
        return []

    real_companies = []
    for etab in data.get("etablissements", []):
        unite = etab.get("uniteLegale", {})
        adresse = etab.get("adresseEtablissement", {})

        name = unite.get("denominationUniteLegale") or \
               unite.get("denominationUsuelle1UniteLegale") or \
               f"{unite.get('nomUniteLegale', '')} {unite.get('prenom1UniteLegale', '')}".strip()
        name = name.upper() if name else "ENTREPRISE INCONNUE"

        num = adresse.get("numeroVoieEtablissement", "")
        type_voie = adresse.get("typeVoieEtablissement", "")
        lib = adresse.get("libelleVoieEtablissement", "")
        cp = adresse.get("codePostalEtablissement", "")
        ville = adresse.get("libelleCommuneEtablissement", "")

        street = " ".join([p for p in [num, type_voie, lib] if p])
        full_address = f"{street}, {cp} {ville}".strip(", ")

        real_companies.append({
            "name": name,
            "siret": etab.get("siret"),
            "siren": etab.get("siren"),
            "address": full_address
        })

    print(f"{len(real_companies)} entreprises récupérées avec succès.")
    return real_companies

REAL_COMPANIES_POOL = []

def _siren_to_tva(siren: str) -> str:
    key = (12 + 3 * (int(siren) % 97)) % 97
    return f"FR{key:02d}{siren}"

def _gen_iban() -> str:
    bank = f"{random.randint(10000, 99999)}"
    branch = f"{random.randint(10000, 99999)}"
    account = f"{random.randint(10000000000, 99999999999)}"
    rib_key = f"{random.randint(10, 97):02d}"
    bban = bank + branch + account + rib_key
    # Calcul clé IBAN
    rearranged = bban + "FR00"
    numeric = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    check = 98 - (int(numeric) % 97)
    return f"FR{check:02d} {bank} {branch} {account} {rib_key}"


def _gen_bic() -> str:
    banks = ["BNPAFRPP", "AGRIFRPP", "SOGEFRPP", "CMCIFRPP", "CEPAFRPP",
             "CRLYFRPP", "BREDFRPP", "CCOPFRPP", "LCHLFRP1", "NATXFRPP"]
    return random.choice(banks)


def _gen_date_past(days_min: int = 30, days_max: int = 365) -> str:
    d = date.today() - timedelta(days=random.randint(days_min, days_max))
    return d.strftime("%d/%m/%Y")


def _gen_date_future(days_min: int = 30, days_max: int = 365) -> str:
    d = date.today() + timedelta(days=random.randint(days_min, days_max))
    return d.strftime("%d/%m/%Y")


def _gen_date_expired(days_min: int = 1, days_max: int = 180) -> str:
    """Date passée = document expiré."""
    d = date.today() - timedelta(days=random.randint(days_min, days_max))
    return d.strftime("%d/%m/%Y")

def _gen_company() -> dict:
    """Générer une entreprise complète avec tous les identifiants basés sur l'API."""
    global REAL_COMPANIES_POOL
    
    if not REAL_COMPANIES_POOL:
        fetched_companies = fetch_sirene_companies(n_companies=200)
        if not fetched_companies:
            raise RuntimeError("Impossible de récupérer des données SIRENE. Vérifiez votre clé API ou votre réseau.")
        REAL_COMPANIES_POOL = fetched_companies

    base_data = random.choice(REAL_COMPANIES_POOL)
    siren = base_data["siren"]

    return {
        "name": base_data["name"],
        "siret": base_data["siret"],
        "siren": siren,
        "tva": _siren_to_tva(siren),
        "address": base_data["address"],
        "email": fake.company_email(),
        "phone": fake.phone_number(),
        "iban": _gen_iban(),
        "bic": _gen_bic(),
        "capital": random.choice([1000, 5000, 10000, 50000, 100000, 500000]),
        "tribunal": random.choice(["Paris", "Lyon", "Marseille", "Bordeaux", "Nantes", "Lille", "Toulouse"]),
        "rcs": f"RCS {random.choice(['Paris', 'Lyon', 'Marseille'])} {siren[:3]} {siren[3:6]} {siren[6:]}",
    }

def _gen_amounts(base_min: float = 500, base_max: float = 50000) -> dict:
    ht = round(random.uniform(base_min, base_max), 2)
    taux_choices = [20.0, 10.0, 5.5, 2.1]
    taux = random.choice(taux_choices)
    tva = round(ht * taux / 100, 2)
    ttc = round(ht + tva, 2)
    return {"ht": ht, "tva": tva, "ttc": ttc, "taux": taux}


# ─────────────────────────────────────────────────────────────
# TEMPLATES TEXTE
# ─────────────────────────────────────────────────────────────

def _text_facture(vendor: dict = None, client: dict = None, anomaly: str = None) -> str:
    vendor = vendor or _gen_company()
    client = client or _gen_company()
    amounts = _gen_amounts()
    num = f"FACT-{date.today().year}-{random.randint(1000, 9999)}"
    date_emission = _gen_date_past(1, 90)
    date_echeance = (date.today() + timedelta(days=random.choice([30, 45, 60, 90]))).strftime("%d/%m/%Y")

    lines = [random.choice([
        f"{fake.bs().title()} - Prestation de service",
        f"Mission de conseil - {fake.catch_phrase()}",
        f"Fourniture de {fake.word()} - lot {random.randint(1, 10)}",
        f"Développement logiciel - phase {random.randint(1, 5)}",
    ]) for _ in range(random.randint(1, 4))]

    items_ht = [round(amounts["ht"] / len(lines), 2) for _ in lines]
    items_ht[-1] = round(amounts["ht"] - sum(items_ht[:-1]), 2)

    # Anomalie volontaire : SIRET différent
    displayed_siret = vendor["siret"]
    if anomaly == "bad_siret":
        displayed_siret = _gen_company()["siret"]

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
    for _, (line, item_ht) in enumerate(zip(lines, items_ht)):
        text += f"{line:<45} {item_ht:>10.2f} €\n"

    text += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total HT                                     {amounts['ht']:>10.2f} €
TVA {amounts['taux']}%                       {amounts['tva']:>10.2f} €
                                            ─────────────
TOTAL TTC                                    {amounts['ttc']:>10.2f} €

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode de règlement : Virement bancaire
IBAN : {vendor['iban']}
BIC : {vendor['bic']}

Pénalités de retard : 3× taux légal en vigueur
Escompte pour paiement anticipé : néant
Indemnité forfaitaire de recouvrement : 40 €
"""
    return text


def _text_devis(vendor: dict = None, client: dict = None, anomaly: str = None) -> str:
    vendor = vendor or _gen_company()
    client = client or _gen_company()
    amounts = _gen_amounts()
    num = f"DEVIS-{date.today().year}-{random.randint(100, 999)}"
    date_emission = _gen_date_past(1, 30)
    validity_days = random.choice([15, 30, 45, 60, 90])
    date_validite = (date.today() + timedelta(days=validity_days)).strftime("%d/%m/%Y")

    text = f"""DEVIS / PROPOSITION COMMERCIALE

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

Objet : {fake.catch_phrase()}

PRESTATIONS PROPOSÉES

"""
    n_items = random.randint(2, 5)
    item_ht = round(amounts["ht"] / n_items, 2)
    for _ in range(n_items):
        unit_ht = item_ht + round(random.uniform(-50, 50), 2)
        text += f"• {fake.bs().title()}\n"
        text += f"  Quantité : {random.randint(1, 10)} - Prix unitaire HT : {unit_ht:.2f} €\n\n"

    text += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sous-total HT        {amounts['ht']:.2f} €
TVA {amounts['taux']}%         {amounts['tva']:.2f} €
Total TTC            {amounts['ttc']:.2f} €

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ce devis est valable {validity_days} jours à compter de sa date d'émission.
Pour accepter cette offre, veuillez retourner ce document signé avec la mention
"Bon pour accord" accompagné d'un acompte de {int(amounts['ttc'] * 0.3):.0f} €.

Signature client :                    Signature et cachet :

___________________                   ___________________
"""
    return text


def _text_urssaf(company: dict = None, expired: bool = False, anomaly: str = None) -> str:
    company = company or _gen_company()

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
        displayed_siret = _gen_company()["siret"]

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

URSSAF — {random.choice(['Île-de-France', 'Rhône-Alpes', 'Provence', 'Bretagne', 'Occitanie'])}
Document électronique authentique — Vérification possible sur urssaf.fr
Référence : {random.randint(100000, 999999)}-{date.today().year}
"""
    return text


def _text_kbis(company: dict = None, expired: bool = False, anomaly: str = None) -> str:
    company = company or _gen_company()

    if expired:
        date_emission = (date.today() - timedelta(days=random.randint(91, 365))).strftime("%d/%m/%Y")
    else:
        date_emission = (date.today() - timedelta(days=random.randint(1, 85))).strftime("%d/%m/%Y")

    gerant = fake.name()
    date_creation = (date.today() - timedelta(days=random.randint(365, 365 * 20))).strftime("%d/%m/%Y")

    displayed_siret = company["siret"]
    if anomaly == "bad_siret":
        displayed_siret = _gen_company()["siret"]

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
Né(e) le : {fake.date_of_birth(minimum_age=25, maximum_age=70).strftime('%d/%m/%Y')}
Nationalité : Française

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Activité principale : {fake.bs().title()}
Code APE/NAF : {random.randint(1000, 9999)}{random.choice(['A','B','C','D','Z'])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Certifié conforme par le greffier du Tribunal de Commerce.
Cet extrait Kbis n'est valable que 3 mois à compter de sa date de délivrance.
Tout extrait périmé doit faire l'objet d'une nouvelle demande.

Greffe du Tribunal de Commerce de {company['tribunal']}
"""
    return text


def _text_attestation_siret(company: dict = None, anomaly: str = None) -> str:
    company = company or _gen_company()
    date_emission = _gen_date_past(1, 90)

    displayed_siret = company["siret"]
    if anomaly == "bad_siret":
        displayed_siret = _gen_company()["siret"]

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
Activité (code APE) : {random.randint(1000, 9999)}{random.choice(['A','B','C'])}
Date de création : {fake.date_between(start_date='-20y', end_date='-1y').strftime('%d/%m/%Y')}
Situation : ACTIF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date d'édition : {date_emission}
Référence : {random.randint(10000000, 99999999)}

Cette attestation est délivrée en application de l'article R.123-220
du Code de Commerce. Peut être vérifiée sur annuaire-entreprises.data.gouv.fr

INSEE — Direction Générale
"""
    return text


def _text_rib(company: dict = None, anomaly: str = None) -> str:
    company = company or _gen_company()

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

Domiciliation : {random.choice(["BNP Paribas", "Société Générale", "Crédit Agricole",
                                  "LCL", "Banque Populaire", "Caisse d'Épargne", "CIC"])}
Agence : {fake.city()}

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


# ─────────────────────────────────────────────────────────────
# GÉNÉRATION PDF via fpdf2
# ─────────────────────────────────────────────────────────────

def _text_to_pdf(text: str, title: str = "Document") -> Optional[bytes]:
    """Convertir un texte en PDF via fpdf2. Retourne None si fpdf2 absent."""
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)

        # Police par défaut (Helvetica supporte les caractères courants)
        pdf.set_font("Helvetica", size=9)

        # Titre en haut (sanitiser pour latin-1)
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.set_text_color(40, 40, 120)
        safe_title = title.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 8, txt=safe_title, ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=8.5)
        pdf.ln(3)

        # Corps du document ligne par ligne
        for line in text.split('\n'):
            # Gérer les séparateurs━
            if '━' in line:
                pdf.set_draw_color(100, 100, 180)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(2)
                continue
            # Lignes en gras si elles ressemblent à des titres de section
            if line.strip() and line.strip() == line.strip().upper() and len(line.strip()) > 5:
                pdf.set_font("Helvetica", style="B", size=8.5)
            else:
                pdf.set_font("Helvetica", size=8.5)

            # multi_cell gère le retour à la ligne
            safe_line = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, txt=safe_line, ln=True)

        return pdf.output()  # bytes

    except ImportError:
        return None
    except Exception as e:
        print(f"  [WARN] PDF generation error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# SIMULATION DE DÉGRADATION (scans mauvaise qualité)
# ─────────────────────────────────────────────────────────────

def degrade_image(img: np.ndarray, degradation: str, severity: float = 0.5) -> np.ndarray:
    """
    Appliquer une dégradation à une image numpy (grayscale ou BGR).
    severity : 0.0 (léger) → 1.0 (extrême)
    """
    result = img.copy()

    if degradation == "blur":
        # Flou gaussien — simule un appareil photo mal focalisé ou une numérisation floue
        ksize = int(3 + severity * 14)
        ksize = ksize if ksize % 2 == 1 else ksize + 1
        result = cv2.GaussianBlur(result, (ksize, ksize), sigmaX=severity * 5)

    elif degradation == "rotation":
        # Légère rotation — document mal posé sur le scanner
        angle = (random.random() - 0.5) * severity * 12  # max ±6°
        h, w = result.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        result = cv2.warpAffine(result, M, (w, h),
                                 flags=cv2.INTER_LINEAR, borderValue=255)

    elif degradation == "noise":
        # Bruit sel et poivre — artefact scanner vieux ou mauvais JPEG
        n_pix = int(severity * 0.04 * result.size)
        rng = np.random.default_rng()
        # Sel (pixels blancs)
        coords = (rng.integers(0, result.shape[0], n_pix),
                  rng.integers(0, result.shape[1], n_pix))
        result[coords] = 255
        # Poivre (pixels noirs)
        coords = (rng.integers(0, result.shape[0], n_pix),
                  rng.integers(0, result.shape[1], n_pix))
        result[coords] = 0

    elif degradation == "low_resolution":
        # Basse résolution — photo de téléphone bas de gamme
        h, w = result.shape[:2]
        scale = max(0.15, 1.0 - severity * 0.75)
        small = cv2.resize(result, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        result = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    elif degradation == "shadow":
        # Ombre sur une partie du document — coin de page soulevé
        if len(result.shape) == 2:
            result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        h, w = result.shape[:2]
        shadow = np.ones((h, w), dtype=np.float32)
        # Ombre diagonale dans un coin
        corner = random.choice(["tl", "tr", "bl", "br"])
        intensity = 0.3 + severity * 0.4
        for y in range(h):
            for x in range(w):
                pass  # Version vectorisée ci-dessous

        # Gradient d'ombre vectorisé
        xs = np.linspace(0, 1, w)
        ys = np.linspace(0, 1, h)
        xx, yy = np.meshgrid(xs, ys)
        if corner == "tl":
            dist = np.sqrt(xx**2 + yy**2) / np.sqrt(2)
        elif corner == "tr":
            dist = np.sqrt((1-xx)**2 + yy**2) / np.sqrt(2)
        elif corner == "bl":
            dist = np.sqrt(xx**2 + (1-yy)**2) / np.sqrt(2)
        else:
            dist = np.sqrt((1-xx)**2 + (1-yy)**2) / np.sqrt(2)

        shadow_mask = (1.0 - (1.0 - dist) * intensity).astype(np.float32)
        for c in range(result.shape[2]):
            result[:, :, c] = np.clip(result[:, :, c] * shadow_mask, 0, 255).astype(np.uint8)

    elif degradation == "combined":
        # Dégradation réaliste combinée (ce qu'on voit sur un vrai mauvais scan)
        result = degrade_image(result, "rotation", severity * 0.6)
        result = degrade_image(result, "blur", severity * 0.8)
        result = degrade_image(result, "noise", severity * 0.4)
        if severity > 0.5:
            result = degrade_image(result, "low_resolution", severity * 0.5)

    elif degradation == "high_quality":
        # Quasi pas de dégradation (bon scanner)
        result = degrade_image(result, "rotation", 0.05)
        result = degrade_image(result, "noise", 0.05)

    return result


def text_to_image(text: str, width: int = 1240, dpi_scale: float = 1.0) -> np.ndarray:
    """
    Rendre du texte brut en image PNG via Pillow.
    Retourne une image numpy BGR.
    """
    from PIL import Image as PILImage, ImageDraw, ImageFont

    font_size = int(14 * dpi_scale)
    line_height = int(font_size * 1.4)
    margin = int(40 * dpi_scale)
    w = int(width * dpi_scale)

    lines = text.split('\n')
    height = margin * 2 + len(lines) * line_height + 40
    # Garantir l'orientation portrait (ratio A4 ≈ 1.41)
    height = max(height, int(w * 1.41))

    img = PILImage.new("RGB", (w, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        # Essayer d'utiliser une police système
        font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
        font_bold = ImageFont.truetype("DejaVuSansMono-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    y = margin
    for line in lines:
        is_bold = (line.strip() and line.strip() == line.strip().upper()
                   and len(line.strip()) > 3 and '━' not in line)
        f = font_bold if is_bold else font
        draw.text((margin, y), line, fill=(20, 20, 20), font=f)
        y += line_height
        if y > height - margin:
            break

    np_img = np.array(img)
    return cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)


# ─────────────────────────────────────────────────────────────
# GÉNÉRATEURS PAR TYPE
# ─────────────────────────────────────────────────────────────

_TEXT_GENERATORS = {
    "FACTURE": lambda anomaly=None: _text_facture(anomaly=anomaly),
    "DEVIS":   lambda anomaly=None: _text_devis(anomaly=anomaly),
    "SIRET":   lambda anomaly=None: _text_attestation_siret(anomaly=anomaly),
    "URSSAF":  lambda anomaly=None: _text_urssaf(expired=(anomaly == "expired"), anomaly=anomaly),
    "KBIS":    lambda anomaly=None: _text_kbis(expired=(anomaly == "expired"), anomaly=anomaly),
    "RIB":     lambda anomaly=None: _text_rib(anomaly=anomaly),
}

DOC_TYPES = list(_TEXT_GENERATORS.keys())


def generate_text(doc_type: str, anomaly: str = None) -> str:
    gen = _TEXT_GENERATORS.get(doc_type.upper())
    if not gen:
        raise ValueError(f"Type inconnu: {doc_type}. Valides: {DOC_TYPES}")
    return gen(anomaly=anomaly)


def generate_training_dataset(n_per_class: int = 150) -> list:
    """
    Générer n_per_class textes par classe → liste de (text, label).
    Utilisé pour l'entraînement du classifier.
    """
    dataset = []
    for doc_type in DOC_TYPES:
        print(f"  Génération {n_per_class} × {doc_type}...")
        for _ in range(n_per_class):
            text = generate_text(doc_type)
            dataset.append((text, doc_type))

    random.shuffle(dataset)
    print(f"  Dataset total : {len(dataset)} documents")
    return dataset


def generate_demo_documents(output_dir: str = "data/demo") -> list:
    """
    Générer les documents de démonstration avec anomalies volontaires.
    Retourne la liste des fichiers créés avec leurs métadonnées.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Entreprise de demo fixe (SIRET cohérent entre les docs)
    company = _gen_company()
    company["name"] = "BTP SOLUTIONS SAS"
    # Entreprise avec SIRET différent pour anomalie
    bad_company = dict(company)
    bad_company["siret"] = _gen_company()["siret"]

    scenarios = [
        ("facture_ok",            "FACTURE", company,     None,       "high_quality",   0.1),
        ("facture_scan_degrade",  "FACTURE", company,     None,       "combined",       0.7),
        ("devis_ok",              "DEVIS",   company,     None,       "high_quality",   0.1),
        ("urssaf_expire",         "URSSAF",  company,     "expired",  "blur",           0.4),
        ("urssaf_ok",             "URSSAF",  company,     None,       "high_quality",   0.1),
        ("kbis_expire",           "KBIS",    company,     "expired",  "noise",          0.5),
        ("kbis_ok",               "KBIS",    company,     None,       "rotation",       0.3),
        ("rib_ok",                "RIB",     company,     None,       "high_quality",   0.1),
        ("siret_bad_siret",       "SIRET",   bad_company, "bad_siret","combined",       0.6),
        ("facture_mauvais_siret", "FACTURE", bad_company, "bad_siret","blur",           0.5),
    ]

    created = []
    for name, doc_type, comp, anomaly, degradation, severity in scenarios:
        text = _TEXT_GENERATORS[doc_type](anomaly=anomaly)

        # Sauvegarder le texte brut
        txt_path = os.path.join(output_dir, f"{name}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)

        # Générer le PDF
        pdf_bytes = _text_to_pdf(text, title=f"{doc_type} — {name}")
        if pdf_bytes:
            pdf_path = os.path.join(output_dir, f"{name}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
        else:
            pdf_path = None

        # Générer l'image dégradée
        img = text_to_image(text)
        img_degraded = degrade_image(img, degradation, severity)
        img_path = os.path.join(output_dir, f"{name}_scan.jpg")
        cv2.imwrite(img_path, img_degraded, [cv2.IMWRITE_JPEG_QUALITY, 70])

        meta = {
            "name": name,
            "doc_type": doc_type,
            "anomaly": anomaly,
            "degradation": degradation,
            "severity": severity,
            "siret": comp["siret"],
            "txt_path": txt_path,
            "pdf_path": pdf_path,
            "img_path": img_path,
        }
        created.append(meta)
        print(f"  ✓ {name} ({doc_type}, {degradation} sévérité={severity})")

    # Sauvegarder les métadonnées
    meta_path = os.path.join(output_dir, "manifest.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(created, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n  {len(created)} documents générés dans {output_dir}")
    print(f"  Manifest : {meta_path}")
    return created


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Générateur de documents synthétiques")
    parser.add_argument("--mode", choices=["training", "demo", "pdf", "image"], default="demo", help="Mode de génération")
    parser.add_argument("--n-per-class", type=int, default=150, help="Nombre de documents par classe (mode training)")
    parser.add_argument("--doc-type", choices=DOC_TYPES, help="Type de document (mode pdf/image)")
    parser.add_argument("--n", type=int, default=5, help="Nombre de documents (mode pdf/image)")
    parser.add_argument("--output", default="data/output", help="Dossier de sortie")
    parser.add_argument("--degradation", choices=["none", "blur", "rotation", "noise", "combined", "high_quality"], default="none", help="Type de dégradation (mode image)")
    parser.add_argument("--severity", type=float, default=0.5, help="Sévérité dégradation 0.0-1.0")
    parser.add_argument("--insee-api-key", help="Clé API pour récupérer des entreprises réelles (optionnel)")
    args = parser.parse_args()

    if args.insee_api_key:
        API_KEY = args.insee_api_key
    
    Path(args.output).mkdir(parents=True, exist_ok=True)

    if args.mode == "training":
        print(f"Génération dataset d'entraînement ({args.n_per_class} par classe)...")
        dataset = generate_training_dataset(args.n_per_class)
        out_path = os.path.join(args.output, "training_data.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([{"text": t, "label": l} for t, l in dataset], f,
                      ensure_ascii=False, indent=2)
        print(f"Dataset sauvegardé : {out_path} ({len(dataset)} exemples)")

    elif args.mode == "demo":
        print("Génération des documents de démonstration...")
        generate_demo_documents(args.output)

    elif args.mode == "pdf":
        doc_type = args.doc_type or random.choice(DOC_TYPES)
        print(f"Génération {args.n} PDFs de type {doc_type}...")
        for i in range(args.n):
            text = generate_text(doc_type)
            pdf_bytes = _text_to_pdf(text, title=doc_type)
            if pdf_bytes:
                path = os.path.join(args.output, f"{doc_type.lower()}_{i+1:03d}.pdf")
                with open(path, "wb") as f:
                    f.write(pdf_bytes)
                print(f"  ✓ {path}")

    elif args.mode == "image":
        doc_type = args.doc_type or random.choice(DOC_TYPES)
        print(f"Génération {args.n} images de type {doc_type} (dégradation: {args.degradation})...")
        for i in range(args.n):
            text = generate_text(doc_type)
            img = text_to_image(text)
            if args.degradation != "none":
                img = degrade_image(img, args.degradation, args.severity)
            path = os.path.join(args.output, f"{doc_type.lower()}_{i+1:03d}.jpg")
            cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 75])
            print(f"  ✓ {path}")