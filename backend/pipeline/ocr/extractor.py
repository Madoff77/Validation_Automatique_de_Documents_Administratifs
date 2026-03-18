"""
Extracteur OCR hybride.

Stratégie en deux temps :
1. Si le fichier est un PDF avec texte natif extractible → pdfplumber (pas d'OCR)
   → Meilleure précision, latence ~200ms, pas de dégradation OCR
2. Sinon (PDF scanné, image JPEG/PNG/TIFF) → preprocessing OpenCV + Tesseract
   → Plusieurs passes avec configs différentes, on garde la meilleure

Retourne un OCRResult avec le texte, un score de confiance, et des métadonnées.
"""

import io
import re
import tempfile
import os
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from pipeline.ocr.preprocessor import preprocess_from_bytes, image_to_bytes, preprocess_image
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIG TESSERACT
# ─────────────────────────────────────────────────────────────

# Configurations Tesseract à essayer (PSM = Page Segmentation Mode)
TESSERACT_CONFIGS = [
    # PSM 3 : auto — détection colonne + orientation  (défaut, bon pour tout)
    r"--oem 3 --psm 3 -l fra+eng",
    # PSM 6 : bloc de texte uniforme  (bon pour formulaires/factures)
    r"--oem 3 --psm 6 -l fra+eng",
]

# Seuil de confiance au-dessus duquel on arrête d'essayer d'autres configs
EARLY_STOP_CONFIDENCE = 0.65

# Seuil minimum de confiance Tesseract (0-100) pour conserver un mot
MIN_WORD_CONFIDENCE = 20

# Un PDF est considéré "natif" si on extrait plus de N caractères non-espaces
NATIVE_PDF_MIN_CHARS = 50


# ─────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────

@dataclass
class OCRResult:
    text: str                          # Texte extrait complet
    confidence: float                  # Score moyen confiance (0-1)
    method: str                        # "native_pdf" | "tesseract" | "tesseract_multi"
    ocr_config: Optional[str]          # Config Tesseract utilisée
    page_count: int                    # Nombre de pages traitées
    word_count: int
    preprocessing_strategy: Optional[str] = None
    raw_ocr_data: Optional[dict] = None

    @property
    def is_usable(self) -> bool:
        """Vrai si le texte extrait est exploitable."""
        return len(self.text.strip()) > 20 and self.confidence > 0.2


# ─────────────────────────────────────────────────────────────
# EXTRACTION TEXTE NATIF PDF
# ─────────────────────────────────────────────────────────────

def _extract_native_pdf(pdf_bytes: bytes) -> Optional[str]:
    """
    Extraire le texte d'un PDF natif (non-scanné) via pdfplumber.
    Retourne None si le PDF est un scan ou si l'extraction échoue.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    pages_text.append(text.strip())
            full_text = "\n\n".join(pages_text)
            # Valider qu'on a vraiment du texte
            non_space = re.sub(r'\s+', '', full_text)
            if len(non_space) >= NATIVE_PDF_MIN_CHARS:
                return full_text
    except Exception as e:
        logger.debug("native_pdf_extraction_failed", error=str(e))
    return None


# ─────────────────────────────────────────────────────────────
# CONVERSION PDF → IMAGES
# ─────────────────────────────────────────────────────────────

def _pdf_to_images(pdf_bytes: bytes, dpi: int = 300) -> List[np.ndarray]:
    """
    Convertir un PDF en liste d'images numpy via pdf2image (Poppler).
    DPI 300 est le minimum recommandé pour Tesseract.
    """
    try:
        from pdf2image import convert_from_bytes
        pil_images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="png")
        images = []
        for pil_img in pil_images:
            np_img = np.array(pil_img.convert("RGB"))
            # Convertir RGB → BGR pour OpenCV
            bgr = cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
            images.append(bgr)
        return images
    except Exception as e:
        logger.error("pdf_to_images_failed", error=str(e))
        return []


# ─────────────────────────────────────────────────────────────
# OCR TESSERACT — UNE IMAGE
# ─────────────────────────────────────────────────────────────

def _tesseract_single(pil_img: Image.Image, config: str) -> Tuple[str, float]:
    """
    Lancer Tesseract sur une image PIL avec une configuration donnée.
    Retourne (texte, confiance_moyenne).

    Les mots sont regroupés par ligne (block_num, par_num, line_num) pour
    préserver la structure ligne/colonne du document. Sans ça, les en-têtes
    de colonnes ("Prix HT", "Montant HT") se retrouvent dans le même flux
    que les lignes totaux, ce qui fait matcher les regex montants sur les
    mauvaises valeurs.
    """
    try:
        data = pytesseract.image_to_data(
            pil_img,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
        # Grouper les mots par ligne physique (block > paragraph > line)
        lines: dict = {}
        confidences = []
        for i, conf in enumerate(data["conf"]):
            if isinstance(conf, (int, float)) and conf >= MIN_WORD_CONFIDENCE:
                word = data["text"][i].strip()
                if word:
                    key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                    lines.setdefault(key, []).append(word)
                    confidences.append(float(conf))

        # Reconstruire le texte avec sauts de ligne entre chaque ligne physique
        text = "\n".join(" ".join(words) for words in lines.values())
        avg_conf = float(np.mean(confidences)) / 100.0 if confidences else 0.0

        return text.strip(), avg_conf
    except Exception as e:
        logger.warning("tesseract_call_failed", config=config, error=str(e))
        return "", 0.0


def _best_tesseract_pass(np_img: np.ndarray) -> Tuple[str, float, str]:
    """
    Essayer les configurations Tesseract sur une image préprocessée,
    retourner (texte, confiance, config_utilisée) du meilleur résultat.
    Early stop si la confiance dépasse EARLY_STOP_CONFIDENCE.
    """
    pil_img = Image.fromarray(np_img)
    best_text = ""
    best_conf = 0.0
    best_config = TESSERACT_CONFIGS[0]

    for config in TESSERACT_CONFIGS:
        text, conf = _tesseract_single(pil_img, config)
        score = conf * min(len(text) / 500.0, 1.0)
        if score > best_conf * min(len(best_text) / 500.0, 1.0):
            best_text = text
            best_conf = conf
            best_config = config
        # Arrêter dès qu'on a une bonne confiance — inutile de tester les autres configs
        if best_conf >= EARLY_STOP_CONFIDENCE:
            break

    return best_text, best_conf, best_config


# ─────────────────────────────────────────────────────────────
# NETTOYAGE TEXTE OCR
# ─────────────────────────────────────────────────────────────

def _clean_ocr_text(text: str) -> str:
    """
    Post-traitement du texte OCR :
    - Supprimer lignes vides multiples
    - Corriger artefacts courants Tesseract
    - Normaliser les espaces
    """
    if not text:
        return ""

    # Corrections OCR fréquentes sur documents français
    corrections = {
        r'\bI€\b': 'Le',
        r'\bI"s\b': 'Les',
        r'0(?=[A-Z])': 'O',   # 0 -> O devant majuscule (ex: 0RACLE -> ORACLE)
        r'(?<=[A-Z])0': 'O',  # 0 -> O après majuscule
        r'\|': 'I',            # pipe -> I
        r'§IRET': 'SIRET',
        r'§IREN': 'SIREN',
        r'TVl\b': 'TVA',
    }
    for pattern, replacement in corrections.items():
        text = re.sub(pattern, replacement, text)

    # Normaliser sauts de ligne multiples
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Normaliser espaces multiples
    text = re.sub(r'[ \t]+', ' ', text)
    # Supprimer lignes ne contenant que des caractères spéciaux
    lines = [
        line for line in text.split('\n')
        if re.search(r'[a-zA-Z0-9€]', line)
    ]

    return '\n'.join(lines).strip()


# ─────────────────────────────────────────────────────────────
# API PUBLIQUE
# ─────────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, mime_type: str) -> OCRResult:
    """
    Point d'entrée principal.

    Logique de routage :
    - PDF → essayer extraction native, sinon convertir en images + OCR
    - Image (JPEG, PNG, TIFF, BMP) → preprocessing + OCR directement
    """
    mime_type = mime_type.lower().strip()

    if mime_type == "application/pdf":
        return _extract_from_pdf(file_bytes)
    elif mime_type in ("image/jpeg", "image/png", "image/tiff", "image/bmp", "image/webp"):
        return _extract_from_image(file_bytes)
    elif mime_type.startswith("text/"):
        # Fichier texte brut (seed sans générateur) — pas besoin d'OCR
        text = file_bytes.decode("utf-8", errors="replace")
        text = _clean_ocr_text(text)
        return OCRResult(
            text=text,
            confidence=1.0,
            method="plain_text",
            ocr_config=None,
            page_count=1,
            word_count=len(text.split()),
        )
    else:
        logger.warning("unknown_mime_type", mime_type=mime_type)
        return _extract_from_image(file_bytes)


def _extract_from_pdf(pdf_bytes: bytes) -> OCRResult:
    """Pipeline complet pour PDF."""
    # 1. Tentative extraction native
    native_text = _extract_native_pdf(pdf_bytes)
    if native_text:
        cleaned = _clean_ocr_text(native_text)
        word_count = len(cleaned.split())
        logger.info("pdf_native_extraction_success", words=word_count)
        return OCRResult(
            text=cleaned,
            confidence=0.98,  # Texte natif = quasi-parfait
            method="native_pdf",
            ocr_config=None,
            page_count=native_text.count('\n\n') + 1,
            word_count=word_count,
        )

    # 2. PDF scanné → convertir en images + OCR
    logger.info("pdf_is_scanned_fallback_to_ocr")
    images = _pdf_to_images(pdf_bytes, dpi=300)
    if not images:
        # Retry à 150 DPI si Poppler échoue à 300
        images = _pdf_to_images(pdf_bytes, dpi=150)

    if not images:
        return OCRResult(
            text="",
            confidence=0.0,
            method="failed",
            ocr_config=None,
            page_count=0,
            word_count=0,
        )

    return _ocr_multiple_images(images, page_count=len(images))


def _extract_from_image(image_bytes: bytes) -> OCRResult:
    """Pipeline pour une image unique."""
    images_bgr = []
    # Tenter chargement OpenCV
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is not None:
        images_bgr.append(img)
    else:
        # Fallback PIL
        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            np_img = np.array(pil_img)
            images_bgr.append(cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR))
        except Exception as e:
            logger.error("image_load_failed", error=str(e))
            return OCRResult(text="", confidence=0.0, method="failed",
                             ocr_config=None, page_count=0, word_count=0)

    return _ocr_multiple_images(images_bgr, page_count=1)


def _ocr_multiple_images(images: List[np.ndarray], page_count: int) -> OCRResult:
    """OCR sur une liste d'images (pages d'un PDF ou image unique)."""
    all_texts = []
    all_confidences = []
    best_config = TESSERACT_CONFIGS[0]
    preprocessing_strategy = None

    for page_idx, img_bgr in enumerate(images):
        # Preprocessing adaptatif
        try:
            prep_result = preprocess_image(img_bgr)
            preprocessed = prep_result.image
            preprocessing_strategy = prep_result.strategy_used
        except Exception as e:
            logger.warning("preprocessing_failed_page", page=page_idx, error=str(e))
            preprocessed = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Multi-pass Tesseract
        text, conf, config = _best_tesseract_pass(preprocessed)

        # Si confiance trop faible, retenter sans preprocessing (parfois contre-productif)
        if conf < 0.4:
            gray_raw = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            text_raw, conf_raw, config_raw = _best_tesseract_pass(gray_raw)
            if conf_raw > conf:
                text, conf, config = text_raw, conf_raw, config_raw
                preprocessing_strategy = "none_raw"
                logger.info("raw_ocr_better", page=page_idx, conf_prep=round(conf, 2), conf_raw=round(conf_raw, 2))

        all_texts.append(text)
        all_confidences.append(conf)
        best_config = config

        logger.info(
            "page_ocr_done",
            page=page_idx + 1,
            total_pages=len(images),
            confidence=round(conf, 2),
            words=len(text.split()),
            strategy=preprocessing_strategy,
        )

    full_text = "\n\n--- PAGE SUIVANTE ---\n\n".join(all_texts) if len(all_texts) > 1 else (all_texts[0] if all_texts else "")
    full_text = _clean_ocr_text(full_text)
    avg_confidence = float(np.mean(all_confidences)) if all_confidences else 0.0

    return OCRResult(
        text=full_text,
        confidence=avg_confidence,
        method="tesseract_multi" if len(images) > 1 else "tesseract",
        ocr_config=best_config,
        page_count=page_count,
        word_count=len(full_text.split()),
        preprocessing_strategy=preprocessing_strategy,
    )
