"""
Preprocesseur d'images pour OCR robuste.

Stratégie : évaluer la qualité de l'image (flou, contraste, luminosité,
rotation), puis appliquer la chaîne de traitement la plus adaptée parmi
plusieurs stratégies. On conserve le résultat qui donne la meilleure
lisibilité estimée (score Laplacian + densité de texte Tesseract).
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────

@dataclass
class ImageQuality:
    blur_score: float        # variance Laplacian — plus haut = plus net
    contrast_score: float    # écart-type des pixels
    brightness: float        # luminosité moyenne (0-255)
    noise_score: float       # estimation bruit haute fréquence
    skew_angle: float        # angle de rotation estimé (degrés)
    width: int
    height: int

    @property
    def is_blurry(self) -> bool:
        return self.blur_score < 80

    @property
    def is_very_blurry(self) -> bool:
        return self.blur_score < 30

    @property
    def is_low_contrast(self) -> bool:
        return self.contrast_score < 40

    @property
    def is_dark(self) -> bool:
        return self.brightness < 80

    @property
    def is_overexposed(self) -> bool:
        return self.brightness > 210

    @property
    def is_skewed(self) -> bool:
        return abs(self.skew_angle) > 0.5

    @property
    def is_noisy(self) -> bool:
        return self.noise_score > 15

    @property
    def needs_upscale(self) -> bool:
        return self.width < 1000 or self.height < 1000


@dataclass
class PreprocessResult:
    image: np.ndarray                    # image préprocessée finale (BGR ou gray)
    strategy_used: str
    quality_before: ImageQuality
    quality_after: ImageQuality
    all_candidates: List[Tuple[str, np.ndarray, float]] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# QUALITY ASSESSMENT
# ─────────────────────────────────────────────────────────────

def assess_quality(img: np.ndarray) -> ImageQuality:
    """Évaluer la qualité d'une image (BGR ou grayscale)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

    # Flou : variance du Laplacian (mesure la netteté des contours)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Contraste : écart-type des niveaux de gris
    contrast_score = float(gray.std())

    # Luminosité : moyenne
    brightness = float(gray.mean())

    # Bruit : différence entre image originale et version lissée
    blurred_ref = cv2.GaussianBlur(gray, (5, 5), 0)
    noise_map = cv2.absdiff(gray, blurred_ref)
    noise_score = float(noise_map.mean())

    # Angle de biais
    skew_angle = _estimate_skew(gray)

    return ImageQuality(
        blur_score=blur_score,
        contrast_score=contrast_score,
        brightness=brightness,
        noise_score=noise_score,
        skew_angle=skew_angle,
        width=img.shape[1],
        height=img.shape[0],
    )


def _estimate_skew(gray: np.ndarray) -> float:
    """
    Estimer l'angle de rotation dominant via transformée de Hough.
    Retourne l'angle en degrés (positif = sens antihoraire).
    """
    try:
        # Binarisation rapide pour détection de lignes
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Dilater horizontalement pour connecter les mots en lignes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        dilated = cv2.dilate(binary, kernel, iterations=1)

        # Trouver les contours des lignes de texte
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        angles = []
        for cnt in contours:
            if cv2.contourArea(cnt) < 500:
                continue
            rect = cv2.minAreaRect(cnt)
            angle = rect[-1]
            # cv2.minAreaRect retourne des angles entre -90 et 0
            if angle < -45:
                angle += 90
            angles.append(angle)

        if not angles:
            return 0.0

        # Médiane pour robustesse aux outliers
        return float(np.median(angles))
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────
# TRANSFORMATIONS ÉLÉMENTAIRES
# ─────────────────────────────────────────────────────────────

def to_gray(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.copy()


def deskew(img: np.ndarray, angle: float) -> np.ndarray:
    """Corriger la rotation. Angle en degrés."""
    if abs(angle) < 0.3:
        return img
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    logger.debug("deskew_applied", angle=round(angle, 2))
    return rotated


def upscale_if_needed(img: np.ndarray, target_min_dim: int = 1500) -> np.ndarray:
    """Upscaler si la résolution est trop faible pour Tesseract."""
    h, w = img.shape[:2]
    min_dim = min(h, w)
    if min_dim >= target_min_dim:
        return img
    scale = target_min_dim / min_dim
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def unsharp_mask(img: np.ndarray, sigma: float = 1.0, strength: float = 1.5) -> np.ndarray:
    """Accentuation des contours pour documents flous."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1 + strength, blurred, -strength, 0)


def apply_clahe(gray: np.ndarray, clip_limit: float = 3.0, tile_size: int = 8) -> np.ndarray:
    """CLAHE : amélioration contraste local adaptatif. Idéal pour scans inégaux."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    return clahe.apply(gray)


def gamma_correction(gray: np.ndarray, gamma: float) -> np.ndarray:
    """Correction gamma : gamma < 1 éclaircit, gamma > 1 assombrit."""
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)], dtype=np.uint8)
    return cv2.LUT(gray, table)


def denoise(gray: np.ndarray, strength: int = 10) -> np.ndarray:
    """Débruitage Non-Local Means — lent mais très efficace sur forte granularité."""
    return cv2.fastNlMeansDenoising(gray, h=strength, templateWindowSize=7, searchWindowSize=21)


def denoise_bilateral(gray: np.ndarray) -> np.ndarray:
    """Filtre bilatéral : lisse sans perdre les contours (bon pour scan moyen)."""
    return cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)


def threshold_otsu(gray: np.ndarray) -> np.ndarray:
    """Binarisation Otsu globale — efficace si contraste uniforme."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def threshold_adaptive(gray: np.ndarray, block_size: int = 31, C: int = 10) -> np.ndarray:
    """Seuillage adaptatif local — meilleur pour éclairage non-uniforme."""
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size, C
    )


def threshold_sauvola_approx(gray: np.ndarray, window: int = 25, k: float = 0.2) -> np.ndarray:
    """
    Approximation de Sauvola : seuillage local basé sur moyenne et écart-type locaux.
    Très robuste pour documents avec fond non uniforme (scan papier jauni, ombres).
    """
    gray_f = gray.astype(np.float32)
    mean = cv2.boxFilter(gray_f, -1, (window, window))
    mean_sq = cv2.boxFilter(gray_f ** 2, -1, (window, window))
    std = np.sqrt(np.maximum(mean_sq - mean ** 2, 0))
    R = 128.0  # range de l'écart-type (normalisé)
    threshold_map = mean * (1 + k * (std / R - 1))
    binary = np.where(gray_f >= threshold_map, 255, 0).astype(np.uint8)
    return binary


def remove_borders(gray: np.ndarray, border_px: int = 10) -> np.ndarray:
    """Supprimer les bordures noires d'un scan (artefact de numérisation)."""
    h, w = gray.shape
    # Remplir les bords par blanc
    result = gray.copy()
    result[:border_px, :] = 255
    result[-border_px:, :] = 255
    result[:, :border_px] = 255
    result[:, -border_px:] = 255
    return result


def morphological_cleanup(binary: np.ndarray) -> np.ndarray:
    """Nettoyage morphologique : supprimer le bruit résiduel fin."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    # Opening : élimine les petits spots de bruit
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    return opened


# ─────────────────────────────────────────────────────────────
# STRATÉGIES DE PREPROCESSING
# ─────────────────────────────────────────────────────────────

def strategy_standard(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline standard pour document bien scanné.
    grayscale → deskew → upscale → Otsu threshold
    """
    gray = to_gray(img)
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    gray = upscale_if_needed(gray)
    gray = remove_borders(gray)
    return threshold_otsu(gray)


def strategy_blurry(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline pour image floue (scan de mauvaise qualité, photo smartphone).
    unsharp mask fort → CLAHE → Sauvola threshold
    """
    gray = to_gray(img)
    gray = upscale_if_needed(gray, target_min_dim=2000)  # Upscale plus agressif
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    # Accentuation contours
    gray = unsharp_mask(gray, sigma=1.5, strength=2.0)
    # Amélioration contraste local
    gray = apply_clahe(gray, clip_limit=4.0, tile_size=8)
    gray = remove_borders(gray)
    # Sauvola robuste aux irrégularités
    return threshold_sauvola_approx(gray, window=25, k=0.15)


def strategy_very_blurry(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline pour image très floue.
    Upscale agressif → débruitage NLM → unsharp fort → adaptive threshold
    """
    gray = to_gray(img)
    gray = upscale_if_needed(gray, target_min_dim=2500)
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    # Débruitage fort avant accentuation (sinon on accentue le bruit)
    gray = denoise(gray, strength=15)
    gray = unsharp_mask(gray, sigma=2.0, strength=2.5)
    gray = apply_clahe(gray, clip_limit=5.0)
    gray = remove_borders(gray)
    return threshold_adaptive(gray, block_size=41, C=12)


def strategy_low_contrast(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline pour document pâle / peu contrasté (papier blanc + impression légère).
    CLAHE aggressif → Otsu
    """
    gray = to_gray(img)
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    gray = upscale_if_needed(gray)
    gray = apply_clahe(gray, clip_limit=6.0, tile_size=4)
    gray = remove_borders(gray)
    return threshold_otsu(gray)


def strategy_dark_scan(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline pour scan sombre (mauvais réglage scanner, photo à contre-jour).
    Correction gamma → CLAHE → adaptive threshold
    """
    gray = to_gray(img)
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    gray = upscale_if_needed(gray)
    # Éclaircir : gamma < 1
    gamma = 0.5 if quality.brightness < 50 else 0.7
    gray = gamma_correction(gray, gamma)
    gray = apply_clahe(gray, clip_limit=3.0)
    gray = remove_borders(gray)
    return threshold_adaptive(gray, block_size=31, C=8)


def strategy_overexposed(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline pour scan surexposé / trop blanc (fond brûlé).
    Gamma > 1 pour assombrir → Sauvola
    """
    gray = to_gray(img)
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    gray = upscale_if_needed(gray)
    gray = gamma_correction(gray, 1.5)
    gray = remove_borders(gray)
    return threshold_sauvola_approx(gray, window=21, k=0.25)


def strategy_noisy(img: np.ndarray, quality: ImageQuality) -> np.ndarray:
    """
    Pipeline pour scan très bruyant (basse résolution scannée, photocopie de photocopie).
    Bilatéral → median → CLAHE → Otsu
    """
    gray = to_gray(img)
    if quality.is_skewed:
        gray = deskew(gray, quality.skew_angle)
    gray = upscale_if_needed(gray)
    # Débruitage multicouche
    gray = denoise_bilateral(gray)
    gray = cv2.medianBlur(gray, 3)
    gray = apply_clahe(gray, clip_limit=2.5)
    gray = remove_borders(gray)
    binary = threshold_otsu(gray)
    return morphological_cleanup(binary)


# ─────────────────────────────────────────────────────────────
# SÉLECTEUR DE STRATÉGIE
# ─────────────────────────────────────────────────────────────

def _score_preprocessed(binary: np.ndarray) -> float:
    """
    Score de lisibilité estimé d'une image binaire.
    Combine : netteté des contours + rapport texte/fond raisonnable.
    """
    # Sharpness de l'image binaire (contours nets = score élevé)
    sharpness = float(cv2.Laplacian(binary, cv2.CV_64F).var())

    # Ratio noir/blanc (texte sombre sur fond blanc)
    # Un bon document a entre 5% et 40% de pixels noirs
    black_ratio = float(np.sum(binary == 0)) / binary.size
    ratio_score = 100.0 if 0.05 <= black_ratio <= 0.40 else 0.0

    return sharpness + ratio_score


def select_and_apply(img: np.ndarray) -> PreprocessResult:
    """
    Évaluer la qualité de l'image, sélectionner la meilleure stratégie,
    et retourner l'image préprocessée avec métadonnées.
    """
    quality = assess_quality(img)
    logger.info(
        "image_quality_assessed",
        blur=round(quality.blur_score, 1),
        contrast=round(quality.contrast_score, 1),
        brightness=round(quality.brightness, 1),
        noise=round(quality.noise_score, 1),
        skew=round(quality.skew_angle, 2),
        size=f"{quality.width}x{quality.height}",
    )

    # Candidats à tester (stratégie → fonction)
    candidates_to_try = [("standard", strategy_standard)]

    if quality.is_very_blurry:
        candidates_to_try.insert(0, ("very_blurry", strategy_very_blurry))
        candidates_to_try.insert(1, ("blurry", strategy_blurry))
    elif quality.is_blurry:
        candidates_to_try.insert(0, ("blurry", strategy_blurry))

    if quality.is_dark:
        candidates_to_try.insert(0, ("dark_scan", strategy_dark_scan))

    if quality.is_overexposed:
        candidates_to_try.insert(0, ("overexposed", strategy_overexposed))

    if quality.is_low_contrast:
        candidates_to_try.insert(0, ("low_contrast", strategy_low_contrast))

    if quality.is_noisy:
        candidates_to_try.insert(0, ("noisy", strategy_noisy))

    # Dédupliquer en conservant l'ordre
    seen = set()
    unique_candidates = []
    for name, fn in candidates_to_try:
        if name not in seen:
            seen.add(name)
            unique_candidates.append((name, fn))

    # Tester chaque stratégie et scorer le résultat
    all_candidates = []
    best_name = "standard"
    best_img = None
    best_score = -1.0

    for name, fn in unique_candidates:
        try:
            result_img = fn(img, quality)
            score = _score_preprocessed(result_img)
            all_candidates.append((name, result_img, score))
            if score > best_score:
                best_score = score
                best_img = result_img
                best_name = name
            logger.debug("strategy_scored", name=name, score=round(score, 1))
        except Exception as e:
            logger.warning("strategy_failed", name=name, error=str(e))

    if best_img is None:
        # Fallback absolu
        best_img = strategy_standard(img, quality)
        best_name = "standard_fallback"

    quality_after = assess_quality(best_img)

    logger.info(
        "preprocessing_done",
        strategy=best_name,
        score=round(best_score, 1),
        blur_before=round(quality.blur_score, 1),
        blur_after=round(quality_after.blur_score, 1),
    )

    return PreprocessResult(
        image=best_img,
        strategy_used=best_name,
        quality_before=quality,
        quality_after=quality_after,
        all_candidates=all_candidates,
    )


# ─────────────────────────────────────────────────────────────
# API PUBLIQUE
# ─────────────────────────────────────────────────────────────

def preprocess_image(img: np.ndarray) -> PreprocessResult:
    """
    Point d'entrée principal.
    Accepte une image numpy BGR (chargée via cv2.imread ou depuis bytes).
    """
    if img is None or img.size == 0:
        raise ValueError("Image vide ou invalide")
    return select_and_apply(img)


def preprocess_from_bytes(image_bytes: bytes) -> PreprocessResult:
    """Charger une image depuis des bytes et la préprocesser."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Impossible de décoder l'image depuis les bytes fournis")
    return preprocess_image(img)


def image_to_bytes(img: np.ndarray, ext: str = ".png") -> bytes:
    """Convertir une image numpy en bytes pour stockage MinIO."""
    success, buffer = cv2.imencode(ext, img)
    if not success:
        raise RuntimeError("Echec encodage image")
    return buffer.tobytes()
