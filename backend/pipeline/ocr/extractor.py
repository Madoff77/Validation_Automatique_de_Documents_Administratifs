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


# Configurations Tesseract
TESSERACT_CONFIGS = [
    # PSM 3 : auto — détection colonne + orientation
    r"--oem 3 --psm 3 -l fra+eng",
    # PSM 6 : bloc de texte uniforme
    r"--oem 3 --psm 6 -l fra+eng",
]

# seuil de confiance au dessus duquel on arrete d'essayer d'autres configs
EARLY_STOP_CONFIDENCE = 0.65

# seuil minimum de confiance Tesseract (0-100) pour conserver un mot
MIN_WORD_CONFIDENCE = 20

# pdf natif si on extrait plus que N caracteres non vides
NATIVE_PDF_MIN_CHARS = 50

# DATA CLASSES

@dataclass
class OCRResult:
    text: str                      
    confidence: float               
    method: str                       
    ocr_config: Optional[str]          
    page_count: int                    
    word_count: int
    preprocessing_strategy: Optional[str] = None
    raw_ocr_data: Optional[dict] = None

    @property
    def is_usable(self) -> bool:
        """Vrai si le texte extrait est exploitable."""
        return len(self.text.strip()) > 20 and self.confidence > 0.2


# EXTRACTION TEXTE NATIF PDF

def _extract_native_pdf(pdf_bytes: bytes) -> Optional[str]:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    pages_text.append(text.strip())
            full_text = "\n\n".join(pages_text)
            non_space = re.sub(r'\s+', '', full_text)
            if len(non_space) >= NATIVE_PDF_MIN_CHARS:
                return full_text
    except Exception as e:
        logger.debug("native_pdf_extraction_failed", error=str(e))
    return None



# convertion de pdf en images

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


# OCR tesseract — UNE IMAGE

def _tesseract_single(pil_img: Image.Image, config: str) -> Tuple[str, float]:
    try:
        data = pytesseract.image_to_data(
            pil_img,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
        # grouper les mots par ligne physique
        lines: dict = {}
        confidences = []
        for i, conf in enumerate(data["conf"]):
            if isinstance(conf, (int, float)) and conf >= MIN_WORD_CONFIDENCE:
                word = data["text"][i].strip()
                if word:
                    key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                    lines.setdefault(key, []).append(word)
                    confidences.append(float(conf))

        # reconstruire le texte avec sauts de ligne entre chaque ligne physique
        text = "\n".join(" ".join(words) for words in lines.values())
        avg_conf = float(np.mean(confidences)) / 100.0 if confidences else 0.0

        return text.strip(), avg_conf
    except Exception as e:
        logger.warning("tesseract_call_failed", config=config, error=str(e))
        return "", 0.0


def _best_tesseract_pass(np_img: np.ndarray) -> Tuple[str, float, str]:
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
        # arrêter dès qu'on a une bonne confiance
        if best_conf >= EARLY_STOP_CONFIDENCE:
            break

    return best_text, best_conf, best_config


# NETTOYAGE TEXTE OCR

def _clean_ocr_text(text: str) -> str:
    if not text:
        return ""

    # Corrections OCR fréquentes sur documents français
    corrections = {
        r'\bI€\b': 'Le',
        r'\bI"s\b': 'Les',
        r'0(?=[A-Z])': 'O',   # 0 -> O
        r'(?<=[A-Z])0': 'O',
        r'\|': 'I',            # pipe -> I
        r'§IRET': 'SIRET',
        r'§IREN': 'SIREN',
        r'TVl\b': 'TVA',
    }
    for pattern, replacement in corrections.items():
        text = re.sub(pattern, replacement, text)

    # normaliser sauts de ligne multiples
    text = re.sub(r'\n{3,}', '\n\n', text)
    # normaliser espaces multiples
    text = re.sub(r'[ \t]+', ' ', text)
    # supprimer lignes ne contenant que des caractère spéciaux
    lines = [
        line for line in text.split('\n')
        if re.search(r'[a-zA-Z0-9€]', line)
    ]

    return '\n'.join(lines).strip()


# API PUBLIQUE

def extract_text(file_bytes: bytes, mime_type: str) -> OCRResult:
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
    # tentative extraction native
    native_text = _extract_native_pdf(pdf_bytes)
    if native_text:
        cleaned = _clean_ocr_text(native_text)
        word_count = len(cleaned.split())
        logger.info("pdf_native_extraction_success", words=word_count)
        return OCRResult(
            text=cleaned,
            confidence=0.98,
            method="native_pdf",
            ocr_config=None,
            page_count=native_text.count('\n\n') + 1,
            word_count=word_count,
        )

    # PDF scanné doonc : convertir en images + OCR
    logger.info("pdf_is_scanned_fallback_to_ocr")
    images = _pdf_to_images(pdf_bytes, dpi=300)
    if not images:
        # retry a 150 si poppler échoue a 300
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
    # OCR sur une liste d'images
    all_texts = []
    all_confidences = []
    best_config = TESSERACT_CONFIGS[0]
    preprocessing_strategy = None

    for page_idx, img_bgr in enumerate(images):
        # preprocessing adaptatif
        try:
            prep_result = preprocess_image(img_bgr)
            preprocessed = prep_result.image
            preprocessing_strategy = prep_result.strategy_used
        except Exception as e:
            logger.warning("preprocessing_failed_page", page=page_idx, error=str(e))
            preprocessed = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # multi-pass Tesseract
        text, conf, config = _best_tesseract_pass(preprocessed)

        # si confiance trop faible retenter sans preprocessing
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
