"""
Générateur de documents administratifs synthétiques.

Produit :
  - Texte brut (pour entraînement classifier)
  - PDF (pour tests OCR pipeline)
  - Images dégradées (scans simulés)

Types de documents : FACTURE, DEVIS, SIRET, URSSAF, KBIS, RIB
Dégradations simulées : flou, rotation, bruit, basse résolution, combiné

Structure :
  generator.py              → point d'entrée, CLI, _gen_company, generate_text
  templates/helpers.py      → utilitaires partagés (Faker, dates, montants)
  templates/facture.py      → template FACTURE (3 variantes)
  templates/devis.py        → template DEVIS (3 variantes)
  templates/urssaf.py       → template URSSAF
  templates/kbis.py         → template KBIS
  templates/siret.py        → template SIRET
  templates/rib.py          → template RIB

Usage :
  python generator.py --mode training --n-per-class 150 --output data/training
  python generator.py --mode demo --output data/demo
  python generator.py --mode pdf --doc-type FACTURE --n 5 --output data/pdfs
"""

import os
import json
import random
import argparse
import sys
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

import numpy as np
from faker import Faker
import cv2
import requests
from dotenv import load_dotenv

# ─── Charger .env depuis plusieurs chemins possibles ─────────────────────────
for _env_path in ["../", "/app/", "./"]:
    _candidate = Path(_env_path) / ".env"
    if _candidate.exists():
        load_dotenv(_candidate)
        break
else:
    load_dotenv()

API_KEY = os.getenv("INSEE_API_KEY")
if not API_KEY:
    import warnings
    warnings.warn(
        "INSEE_API_KEY manquante. fetch_sirene_companies() ne fonctionnera pas. "
        "Définissez INSEE_API_KEY dans votre .env pour utiliser les données réelles.",
        RuntimeWarning,
        stacklevel=2,
    )

# ─── Faker (sans seed global — voir note ci-dessous) ─────────────────────────
#
# NOTE IMPORTANTE — pourquoi on ne seed PAS ici :
#
# Avec Faker.seed(42) + random.seed(42), le dataset d'entraînement est entièrement
# déterministe. Chaque run génère exactement les mêmes 900 documents. Le jeu de
# test (20%) est structurellement identique au jeu d'entraînement → le Random
# Forest mémorise les patterns exacts des templates et atteint 100% d'accuracy
# sur le test synthétique, mais échoue sur de vrais documents OCR.
#
# En production, "FACTURE" peut être lu "FACTUR E" par Tesseract, ou un devis peut
# mentionner "suite au devis n°XXX" dans une facture → le modèle confond.
#
# Solution :
#   - Pas de seed global → données différentes à chaque entraînement → accuracy
#     réelle ~85-93% sur le set synthétique, plus représentative du réel
#   - Les templates ont 2-3 variantes de layout → le RF doit apprendre le contenu
#   - train.py fixe random_state=42 uniquement pour la reproductibilité du split
#
# ─────────────────────────────────────────────────────────────────────────────

fake = Faker("fr_FR")

# ─── Importer les templates ───────────────────────────────────────────────────
# Ajouter le dossier courant au path pour que les templates trouvent ce module
sys.path.insert(0, os.path.dirname(__file__))

from templates import (
    _text_facture,
    _text_devis,
    _text_urssaf,
    _text_kbis,
    _text_attestation_siret,
    _text_rib,
)
from templates.helpers import register_company_factory, fake as _helpers_fake


# ─────────────────────────────────────────────────────────────────────────────
# API SIRENE
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sirene_companies(n_companies: int = 100) -> list:
    """Récupère un lot d'entreprises réelles actives via l'API SIRENE."""
    if not API_KEY:
        return []

    print(f"Récupération de {n_companies} entreprises depuis l'API SIRENE...")
    url = "https://api.insee.fr/api-sirene/3.11/siret"
    headers = {
        "X-INSEE-Api-Key-Integration": API_KEY,
        "Accept": "application/json",
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

        name = (
            unite.get("denominationUniteLegale")
            or unite.get("denominationUsuelle1UniteLegale")
            or f"{unite.get('nomUniteLegale', '')} {unite.get('prenom1UniteLegale', '')}".strip()
        )
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
            "address": full_address,
        })

    print(f"{len(real_companies)} entreprises récupérées avec succès.")
    return real_companies


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS ENTREPRISE
# ─────────────────────────────────────────────────────────────────────────────

REAL_COMPANIES_POOL: list = []


def _siren_to_tva(siren: str) -> str:
    key = (12 + 3 * (int(siren) % 97)) % 97
    return f"FR{key:02d}{siren}"


def _gen_iban() -> str:
    bank = f"{random.randint(10000, 99999)}"
    branch = f"{random.randint(10000, 99999)}"
    account = f"{random.randint(10000000000, 99999999999)}"
    rib_key = f"{random.randint(10, 97):02d}"
    bban = bank + branch + account + rib_key
    rearranged = bban + "FR00"
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    check = 98 - (int(numeric) % 97)
    return f"FR{check:02d} {bank} {branch} {account} {rib_key}"


def _gen_bic() -> str:
    banks = [
        "BNPAFRPP", "AGRIFRPP", "SOGEFRPP", "CMCIFRPP", "CEPAFRPP",
        "CRLYFRPP", "BREDFRPP", "CCOPFRPP", "LCHLFRP1", "NATXFRPP",
    ]
    return random.choice(banks)


def _gen_company() -> dict:
    """Générer une entreprise complète avec identifiants SIRENE réels."""
    global REAL_COMPANIES_POOL

    if not REAL_COMPANIES_POOL:
        fetched = fetch_sirene_companies(n_companies=200)
        if not fetched:
            raise RuntimeError(
                "Impossible de récupérer des données SIRENE. "
                "Vérifiez INSEE_API_KEY dans votre .env."
            )
        REAL_COMPANIES_POOL = fetched

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
        "tribunal": random.choice([
            "Paris", "Lyon", "Marseille", "Bordeaux", "Nantes", "Lille", "Toulouse"
        ]),
        "rcs": (
            f"RCS {random.choice(['Paris', 'Lyon', 'Marseille'])} "
            f"{siren[:3]} {siren[3:6]} {siren[6:]}"
        ),
    }


# Injecter la factory dans le package templates (évite les imports circulaires)
register_company_factory(_gen_company)


# ─────────────────────────────────────────────────────────────────────────────
# GÉNÉRATEURS PAR TYPE
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION BRUIT OCR
# ─────────────────────────────────────────────────────────────────────────────

def _degrade_text_ocr(text: str, severity: float = 0.3) -> str:
    """
    Simuler les erreurs typiques d'un moteur OCR (Tesseract) sur du texte.

    Catégories d'erreurs simulées :
    1. Confusions de caractères similaires visuellement (l↔I↔1, 0↔O, rn↔m, etc.)
    2. Espaces parasites en milieu de mot (fractionnement)
    3. Fusion de mots adjacents (manque d'espace)
    4. Substitutions de caractères aléatoires (bruit générique)
    5. Suppression de lignes (OCR ne lit pas toute la page)

    severity : 0.0 (pas de bruit) → 1.0 (très dégradé)
    """
    OCR_CHAR_CONFUSIONS = [
        ("l", "I"), ("I", "l"), ("1", "l"), ("l", "1"),
        ("0", "O"), ("O", "0"),
        ("rn", "m"), ("m", "rn"),
        ("cl", "d"),
        ("vv", "w"),
        ("ii", "n"),
        ("§", "S"),
        ("€", "E"),
        ("à", "a"), ("é", "e"), ("è", "e"), ("ê", "e"), ("ù", "u"), ("â", "a"),
    ]

    lines = text.split("\n")
    result_lines = []

    for line in lines:
        if not line.strip():
            result_lines.append(line)
            continue

        if severity > 0.4 and random.random() < severity * 0.06:
            continue  # Ligne perdue

        degraded = line

        if random.random() < severity * 0.5:
            src, dst = random.choice(OCR_CHAR_CONFUSIONS)
            idx = degraded.find(src)
            if idx != -1:
                degraded = degraded[:idx] + dst + degraded[idx + len(src):]

        if random.random() < severity * 0.15 and len(degraded) > 5:
            pos = random.randint(2, len(degraded) - 2)
            if degraded[pos].isalpha():
                noise_chars = "ceoasiIlO01"
                degraded = degraded[:pos] + random.choice(noise_chars) + degraded[pos + 1:]

        if random.random() < severity * 0.12:
            words = degraded.split()
            if words:
                idx = random.randint(0, len(words) - 1)
                word = words[idx]
                if len(word) >= 5:
                    cut = random.randint(2, len(word) - 2)
                    words[idx] = word[:cut] + " " + word[cut:]
                    degraded = " ".join(words)

        if random.random() < severity * 0.08:
            words = degraded.split()
            if len(words) >= 2:
                idx = random.randint(0, len(words) - 2)
                merged = words[idx] + words[idx + 1]
                words = words[:idx] + [merged] + words[idx + 2:]
                degraded = " ".join(words)

        result_lines.append(degraded)

    return "\n".join(result_lines)


# ─────────────────────────────────────────────────────────────────────────────
# DATASET D'ENTRAÎNEMENT
# ─────────────────────────────────────────────────────────────────────────────

def generate_training_dataset(n_per_class: int = 150) -> list:
    """
    Générer n_per_class textes par classe → liste de (text, label).

    Distribution du bruit :
    - 45% texte propre (PDF natif bien extrait)
    - 30% bruit léger (severity 0.15–0.35 : bon scanner, quelques artefacts)
    - 20% bruit modéré (severity 0.35–0.60 : scan moyen, Tesseract imparfait)
    - 5%  bruit fort (severity 0.60–0.85 : mauvais scan, très dégradé)
    """
    DEGRADATION_SCHEDULE = [
        (0.45, None),
        (0.75, (0.15, 0.35)),
        (0.95, (0.35, 0.60)),
        (1.00, (0.60, 0.85)),
    ]

    dataset = []
    n_clean = n_degraded_light = n_degraded_medium = n_degraded_heavy = 0

    for doc_type in DOC_TYPES:
        print(f"  Génération {n_per_class} × {doc_type}...")
        for _ in range(n_per_class):
            text = generate_text(doc_type)
            roll = random.random()
            for threshold, severity_range in DEGRADATION_SCHEDULE:
                if roll < threshold:
                    if severity_range is None:
                        n_clean += 1
                    else:
                        severity = random.uniform(*severity_range)
                        text = _degrade_text_ocr(text, severity)
                        if severity_range[0] < 0.35:
                            n_degraded_light += 1
                        elif severity_range[0] < 0.60:
                            n_degraded_medium += 1
                        else:
                            n_degraded_heavy += 1
                    break
            dataset.append((text, doc_type))

    random.shuffle(dataset)
    total = len(dataset)
    print(f"  Dataset total : {total} documents")
    print(
        f"  Distribution bruit : propre={n_clean} ({n_clean*100//total}%) "
        f"léger={n_degraded_light} ({n_degraded_light*100//total}%) "
        f"modéré={n_degraded_medium} ({n_degraded_medium*100//total}%) "
        f"fort={n_degraded_heavy} ({n_degraded_heavy*100//total}%)"
    )
    return dataset


# ─────────────────────────────────────────────────────────────────────────────
# GÉNÉRATION PDF via fpdf2
# ─────────────────────────────────────────────────────────────────────────────

def _text_to_pdf(text: str, title: str = "Document") -> Optional[bytes]:
    """Convertir un texte en PDF via fpdf2. Retourne None si fpdf2 absent."""
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        pdf.set_font("Helvetica", style="B", size=11)
        pdf.set_text_color(40, 40, 120)
        safe_title = title.encode("latin-1", "replace").decode("latin-1")
        pdf.cell(0, 8, txt=safe_title, ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", size=8.5)
        pdf.ln(3)

        for line in text.split("\n"):
            if "━" in line:
                pdf.set_draw_color(100, 100, 180)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(2)
                continue
            if line.strip() and line.strip() == line.strip().upper() and len(line.strip()) > 5:
                pdf.set_font("Helvetica", style="B", size=8.5)
            else:
                pdf.set_font("Helvetica", size=8.5)
            safe_line = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, txt=safe_line, ln=True)

        return pdf.output()

    except ImportError:
        return None
    except Exception as e:
        print(f"  [WARN] PDF generation error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION DE DÉGRADATION (scans mauvaise qualité)
# ─────────────────────────────────────────────────────────────────────────────

def degrade_image(img: np.ndarray, degradation: str, severity: float = 0.5) -> np.ndarray:
    """
    Appliquer une dégradation à une image numpy (grayscale ou BGR).
    severity : 0.0 (léger) → 1.0 (extrême)
    """
    result = img.copy()

    if degradation == "blur":
        ksize = int(3 + severity * 14)
        ksize = ksize if ksize % 2 == 1 else ksize + 1
        result = cv2.GaussianBlur(result, (ksize, ksize), sigmaX=severity * 5)

    elif degradation == "rotation":
        angle = (random.random() - 0.5) * severity * 12
        h, w = result.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        result = cv2.warpAffine(result, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)

    elif degradation == "noise":
        n_pix = int(severity * 0.04 * result.size)
        rng = np.random.default_rng()
        coords = (rng.integers(0, result.shape[0], n_pix), rng.integers(0, result.shape[1], n_pix))
        result[coords] = 255
        coords = (rng.integers(0, result.shape[0], n_pix), rng.integers(0, result.shape[1], n_pix))
        result[coords] = 0

    elif degradation == "low_resolution":
        h, w = result.shape[:2]
        scale = max(0.15, 1.0 - severity * 0.75)
        small = cv2.resize(result, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        result = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    elif degradation == "shadow":
        if len(result.shape) == 2:
            result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
        h, w = result.shape[:2]
        corner = random.choice(["tl", "tr", "bl", "br"])
        intensity = 0.3 + severity * 0.4
        xs = np.linspace(0, 1, w)
        ys = np.linspace(0, 1, h)
        xx, yy = np.meshgrid(xs, ys)
        if corner == "tl":
            dist = np.sqrt(xx**2 + yy**2) / np.sqrt(2)
        elif corner == "tr":
            dist = np.sqrt((1 - xx)**2 + yy**2) / np.sqrt(2)
        elif corner == "bl":
            dist = np.sqrt(xx**2 + (1 - yy)**2) / np.sqrt(2)
        else:
            dist = np.sqrt((1 - xx)**2 + (1 - yy)**2) / np.sqrt(2)
        shadow_mask = (1.0 - (1.0 - dist) * intensity).astype(np.float32)
        for c in range(result.shape[2]):
            result[:, :, c] = np.clip(result[:, :, c] * shadow_mask, 0, 255).astype(np.uint8)

    elif degradation == "combined":
        result = degrade_image(result, "rotation", severity * 0.6)
        result = degrade_image(result, "blur", severity * 0.8)
        result = degrade_image(result, "noise", severity * 0.4)
        if severity > 0.5:
            result = degrade_image(result, "low_resolution", severity * 0.5)

    elif degradation == "high_quality":
        result = degrade_image(result, "rotation", 0.05)
        result = degrade_image(result, "noise", 0.05)

    return result


def text_to_image(text: str, width: int = 1240, dpi_scale: float = 1.0) -> np.ndarray:
    """Rendre du texte brut en image PNG via Pillow. Retourne une image numpy BGR."""
    from PIL import Image as PILImage, ImageDraw, ImageFont

    font_size = int(14 * dpi_scale)
    line_height = int(font_size * 1.4)
    margin = int(40 * dpi_scale)
    w = int(width * dpi_scale)

    lines = text.split("\n")
    height = margin * 2 + len(lines) * line_height + 40
    height = max(height, int(w * 1.41))

    img = PILImage.new("RGB", (w, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
        font_bold = ImageFont.truetype("DejaVuSansMono-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    y = margin
    for line in lines:
        is_bold = (
            line.strip()
            and line.strip() == line.strip().upper()
            and len(line.strip()) > 3
            and "━" not in line
        )
        f = font_bold if is_bold else font
        draw.text((margin, y), line, fill=(20, 20, 20), font=f)
        y += line_height
        if y > height - margin:
            break

    np_img = np.array(img)
    return cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)


# ─────────────────────────────────────────────────────────────────────────────
# GÉNÉRATION RÉELLE (entreprises SIRENE → PDFs + images)
# ─────────────────────────────────────────────────────────────────────────────

# Dégradations appliquées par type de document (réaliste)
_DOC_DEGRADATIONS = {
    "FACTURE": ("high_quality", 0.1),
    "DEVIS":   ("noise",        0.3),
    "KBIS":    ("rotation",     0.2),
    "URSSAF":  ("high_quality", 0.1),
    "SIRET":   ("high_quality", 0.1),
    "RIB":     ("high_quality", 0.1),
}


def generate_documents(n_companies: int = 200, output_dir: str = "data/output") -> list:
    """
    Récupère n_companies entreprises réelles depuis l'API SIRENE,
    puis génère pour chacune un PDF et une image JPEG pour chaque type
    de document (FACTURE, DEVIS, KBIS, URSSAF, SIRET, RIB).

    Retourne la liste des métadonnées des fichiers créés.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    companies = fetch_sirene_companies(n_companies=n_companies)
    if not companies:
        raise RuntimeError(
            "Impossible de récupérer des entreprises depuis l'API SIRENE. "
            "Vérifiez INSEE_API_KEY dans votre .env."
        )

    # Pré-charger le pool pour _gen_company()
    global REAL_COMPANIES_POOL
    REAL_COMPANIES_POOL = companies

    created = []
    total = len(companies) * len(DOC_TYPES)
    done = 0

    print(f"\n  {len(companies)} entreprises — {total} documents à générer\n")

    for company_data in companies:
        siren = company_data.get("siren", "")
        if not siren:
            continue

        company = {
            "name":     company_data["name"],
            "siret":    company_data["siret"],
            "siren":    siren,
            "tva":      _siren_to_tva(siren),
            "address":  company_data["address"],
            "email":    fake.company_email(),
            "phone":    fake.phone_number(),
            "iban":     _gen_iban(),
            "bic":      _gen_bic(),
            "capital":  random.choice([1000, 5000, 10000, 50000, 100000]),
            "tribunal": random.choice(["Paris", "Lyon", "Marseille", "Bordeaux", "Nantes"]),
            "rcs": (
                f"RCS {random.choice(['Paris', 'Lyon', 'Marseille'])} "
                f"{siren[:3]} {siren[3:6]} {siren[6:]}"
            ),
        }

        safe_name = company["siret"]  # SIRET comme identifiant unique de dossier
        company_dir = os.path.join(output_dir, safe_name)
        Path(company_dir).mkdir(parents=True, exist_ok=True)

        for doc_type in DOC_TYPES:
            text = _TEXT_GENERATORS[doc_type]()
            degradation, severity = _DOC_DEGRADATIONS.get(doc_type, ("high_quality", 0.1))

            # PDF
            pdf_bytes = _text_to_pdf(text, title=f"{doc_type} — {company['name']}")
            pdf_path = None
            if pdf_bytes:
                pdf_path = os.path.join(company_dir, f"{doc_type.lower()}.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)

            # Image JPEG dégradée (simule un scan)
            img = text_to_image(text)
            img_degraded = degrade_image(img, degradation, severity)
            jpg_path = os.path.join(company_dir, f"{doc_type.lower()}_scan.jpg")
            cv2.imwrite(jpg_path, img_degraded, [cv2.IMWRITE_JPEG_QUALITY, 75])

            meta = {
                "company_name": company["name"],
                "siret":        company["siret"],
                "siren":        siren,
                "doc_type":     doc_type,
                "degradation":  degradation,
                "severity":     severity,
                "pdf_path":     pdf_path,
                "jpg_path":     jpg_path,
            }
            created.append(meta)
            done += 1

        print(f"  ✓ {company['name'][:40]:<40}  SIRET {company['siret']}  ({len(DOC_TYPES)} docs)")

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(created, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n  {done} documents générés dans {output_dir}/")
    print(f"  Manifest : {manifest_path}")
    return created


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Générateur de documents synthétiques")
    parser.add_argument(
        "--mode",
        choices=["training", "generate", "pdf", "image"],
        default="generate",
        help="Mode de génération",
    )
    parser.add_argument(
        "--n-per-class",
        type=int,
        default=150,
        help="Nombre de documents par classe (mode training)",
    )
    parser.add_argument(
        "--doc-type",
        choices=DOC_TYPES,
        help="Type de document (mode pdf/image)",
    )
    parser.add_argument("--n", type=int, default=5, help="Nombre de documents (mode pdf/image)")
    parser.add_argument("--output", default="data/output", help="Dossier de sortie")
    parser.add_argument(
        "--degradation",
        choices=["none", "blur", "rotation", "noise", "combined", "high_quality"],
        default="none",
        help="Type de dégradation (mode image)",
    )
    parser.add_argument("--severity", type=float, default=0.5, help="Sévérité 0.0-1.0")
    parser.add_argument("--insee-api-key", help="Clé API SIRENE (override .env)")
    args = parser.parse_args()

    if args.insee_api_key:
        API_KEY = args.insee_api_key

    Path(args.output).mkdir(parents=True, exist_ok=True)

    if args.mode == "training":
        print(f"Génération dataset d'entraînement ({args.n_per_class} par classe)...")
        dataset = generate_training_dataset(args.n_per_class)
        out_path = os.path.join(args.output, "training_data.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                [{"text": t, "label": l} for t, l in dataset],
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Dataset sauvegardé : {out_path} ({len(dataset)} exemples)")

    elif args.mode == "generate":
        print(f"Génération depuis l'API SIRENE ({args.n} entreprises)...")
        generate_documents(n_companies=args.n, output_dir=args.output)

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
