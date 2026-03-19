"""
Classifier de documents administratifs.

Architecture : TF-IDF (1-2 grams, 5000 features) + Random Forest (200 arbres).

Pourquoi Random Forest ?
  - Interprétable : feature importances montrent les mots discriminants par classe
  - Robuste au bruit OCR : les fautes d'OCR sont rares dans les mots discriminants
  - Pas de GPU nécessaire, latence < 50ms
  - Fonctionne très bien avec peu de données (50-150 par classe)
  - Calibré naturellement → probabilités fiables pour seuil de confiance

Fallback keyword : si le modèle n'est pas chargé OU si la confiance < seuil,
on utilise un classifieur à règles lexicales simples.
"""

import os
import re
from typing import Tuple, Dict, Optional, List
from pathlib import Path

import joblib
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)

DOC_TYPES = ["FACTURE", "DEVIS", "SIRET", "URSSAF", "KBIS", "RIB"]

# CLASSIFIEUR PAR RÈGLES (fallback sans modèle ML)

# Mots-clés discriminants par classe, avec poids relatifs
KEYWORD_RULES: Dict[str, List[Tuple[str, float]]] = {
    "FACTURE": [
        ("facture", 4.0), ("numéro de facture", 5.0), ("fact-", 3.0),
        ("date d'échéance", 3.5), ("date d'émission", 2.0),
        ("pénalités de retard", 4.0), ("indemnité forfaitaire", 4.0),
        ("mode de règlement", 3.0), ("escompte", 2.5),
        ("vendeur", 2.0), ("acheteur", 2.0),
        # "tva" retiré : trop générique, présent aussi dans DEVIS → confusion
        # "montant ttc/ht/total ttc" retirés : présents dans DEVIS aussi
    ],
    "DEVIS": [
        ("devis", 4.0), ("proposition commerciale", 5.0),
        ("valable jusqu", 4.0), ("bon pour accord", 4.5),
        ("référence devis", 5.0), ("devis-", 3.0),
        ("acompte de", 3.0), ("validité", 2.5),
        ("prestations proposées", 4.0), ("acceptation", 2.5),
        ("non contractuel", 3.0), ("sous réserve", 2.0),
    ],
    "SIRET": [
        ("attestation de situation", 4.0), ("répertoire sirene", 5.0),
        ("répertoire national", 4.0), ("insee", 3.0), ("numéro siret", 3.0),
        ("attestation siret", 5.0), ("annuaire-entreprises", 3.0),
        ("code ape", 2.0), ("date de création", 1.5), ("établissement actif", 3.0),
    ],
    "URSSAF": [
        ("urssaf", 5.0), ("attestation de vigilance", 5.0),
        ("cotisations sociales", 4.0), ("contributions patronales", 3.5),
        ("l.243-15", 4.0), ("net-entreprises", 3.0), ("code de la sécurité sociale", 3.0),
        ("en règle", 2.5), ("régularité de situation", 3.0),
        ("sécurité sociale", 2.0),
    ],
    "KBIS": [
        ("extrait kbis", 5.0), ("tribunal de commerce", 4.5),
        ("registre du commerce", 4.5), ("immatriculation", 3.0),
        ("capital social", 3.0), ("gérant", 2.5), ("rcs", 3.0),
        ("greffier", 3.5), ("forme juridique", 2.5), ("siège social", 2.0),
        ("date d'immatriculation", 3.0), ("3 mois", 2.0),
    ],
    "RIB": [
        ("relevé d'identité bancaire", 5.0), ("rib", 3.0),
        ("iban", 4.0), ("bic", 3.0), ("swift", 2.5),
        ("domiciliation", 3.0), ("code banque", 4.0),
        ("code guichet", 4.0), ("clé rib", 4.0), ("titulaire du compte", 3.5),
        ("virement", 1.5), ("prélèvement", 1.5),
    ],
}


def classify_by_keywords(text: str) -> Tuple[str, float, Dict[str, float]]:
    """
    Classifier basé sur densité de mots-clés pondérés.
    Retourne (doc_type, confidence, scores_par_classe).
    """
    text_lower = text.lower()
    word_count = max(len(text_lower.split()), 1)

    scores: Dict[str, float] = {}
    for doc_type, keywords in KEYWORD_RULES.items():
        score = 0.0
        for kw, weight in keywords:
            count = len(re.findall(re.escape(kw), text_lower))
            score += count * weight
        # Normaliser par longueur du texte (densité)
        scores[doc_type] = score / (word_count / 100.0)

    if not scores or max(scores.values()) == 0:
        return "UNKNOWN", 0.0, {k: 0.0 for k in DOC_TYPES}

    total = sum(scores.values())
    probs = {k: v / total for k, v in scores.items()}
    best = max(probs, key=lambda k: probs[k])
    confidence = probs[best]

    return best, confidence, probs


# CLASSIFIEUR ML (TF-IDF + Random Forest)

class DocumentClassifier:
    """
    Classifieur TF-IDF + Random Forest avec fallback keyword.

    Méthodes publiques :
      load()              : charger modèle depuis disque
      predict(text)       : classer un document
      get_feature_names() : mots importants par classe (pour jury)
    """

    def __init__(
        self,
        model_path: str = "/app/models/trained/classifier.joblib",
        vectorizer_path: str = "/app/models/trained/vectorizer.joblib",
        confidence_threshold: float = 0.6,
    ):
        self.model_path = model_path
        self.vectorizer_path = vectorizer_path
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._vectorizer = None
        self._is_loaded = False

    def load(self) -> bool:
        """Charger le modèle pré-entraîné depuis le disque."""
        if not os.path.exists(self.model_path) or not os.path.exists(self.vectorizer_path):
            logger.warning(
                "classifier_model_not_found",
                model_path=self.model_path,
                fallback="keyword_rules",
            )
            return False
        try:
            self._model = joblib.load(self.model_path)
            self._vectorizer = joblib.load(self.vectorizer_path)
            self._is_loaded = True
            logger.info(
                "classifier_loaded",
                model_path=self.model_path,
                classes=list(self._model.classes_),
            )
            return True
        except Exception as e:
            logger.error("classifier_load_failed", error=str(e))
            return False

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """
        Classifier un document.

        Retourne :
          (doc_type: str, confidence: float, probs: dict)

        Stratégie :
          1. Si modèle ML disponible → TF-IDF + RF
          2. Si confiance ML < seuil → essayer keyword + prendre le meilleur
          3. Fallback total → keyword rules
        """
        if not text or not text.strip():
            return "UNKNOWN", 0.0, {k: 0.0 for k in DOC_TYPES}

        # Préprocesser le texte
        clean_text = self._preprocess(text)

        # Prédiction ML
        if self._is_loaded and self._model and self._vectorizer:
            try:
                X = self._vectorizer.transform([clean_text])
                proba = self._model.predict_proba(X)[0]
                classes = self._model.classes_
                probs = {cls: float(p) for cls, p in zip(classes, proba)}
                best = max(probs, key=lambda k: probs[k])
                confidence = probs[best]

                if confidence >= self.confidence_threshold:
                    logger.debug("classify_ml", doc_type=best, confidence=round(confidence, 3))
                    return best, confidence, probs

                # Confiance faible → combiner avec keyword
                kw_type, kw_conf, kw_probs = classify_by_keywords(text)
                if kw_conf > confidence:
                    logger.info(
                        "classify_keyword_override",
                        ml_type=best, ml_conf=round(confidence, 3),
                        kw_type=kw_type, kw_conf=round(kw_conf, 3),
                    )
                    return kw_type, kw_conf, kw_probs

                return best, confidence, probs

            except Exception as e:
                logger.warning("classify_ml_failed", error=str(e))

        # Fallback keyword
        kw_type, kw_conf, kw_probs = classify_by_keywords(text)
        logger.debug("classify_keyword", doc_type=kw_type, confidence=round(kw_conf, 3))
        return kw_type, kw_conf, kw_probs

    @staticmethod
    def _preprocess(text: str) -> str:
        """
        Normaliser le texte pour TF-IDF :
        - lowercase
        - supprimer ponctuation excessive
        - normaliser les montants (→ "MONTANT")
        - normaliser les dates (→ "DATE")
        - normaliser les numéros (→ préserver les mots-clés)
        """
        text = text.lower()

        # Normaliser montants (ex: "1 234,56 €" → "MONTANT_EUR")
        text = re.sub(r'\d[\d\s]*[,\.]\d{2}\s*(?:€|eur)', ' montant_eur ', text)

        # Normaliser dates
        text = re.sub(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}', ' date_doc ', text)
        text = re.sub(r'\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2}', ' date_doc ', text)

        # Normaliser SIRET/SIREN (remplacer par tokens)
        text = re.sub(r'\b\d{14}\b', ' num_siret ', text)
        text = re.sub(r'\b\d{9}\b', ' num_siren ', text)
        text = re.sub(r'\bfr[\s\d]{11,13}\b', ' num_tva ', text)
        text = re.sub(r'\bfr\d{2}[\s\d]{23,27}\b', ' num_iban ', text)

        # Supprimer séquences de symboles
        text = re.sub(r'[━─═]{3,}', ' separateur ', text)
        text = re.sub(r'[^\w\sàâäéèêëïîôùûüç]', ' ', text)

        # Compresser espaces multiples
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_top_features(self, doc_type: str, n: int = 20) -> List[Tuple[str, float]]:
        """
        Retourner les N features (mots) les plus importantes pour une classe.
        Utile pour expliquer le modèle au jury.
        """
        if not self._is_loaded:
            return []
        try:
            class_idx = list(self._model.classes_).index(doc_type)
            feature_names = self._vectorizer.get_feature_names_out()
            importances = self._model.estimators_[0].feature_importances_  # 1er arbre pour approx

            # Moyenne sur tous les arbres pour la classe
            all_importances = np.mean(
                [tree.feature_importances_ for tree in self._model.estimators_], axis=0
            )
            top_indices = np.argsort(all_importances)[::-1][:n]
            return [(feature_names[i], float(all_importances[i])) for i in top_indices]
        except Exception:
            return []

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded


# SINGLETON (chargé une seule fois en mémoire)

_instance: Optional[DocumentClassifier] = None


def get_classifier() -> DocumentClassifier:
    """Retourner l'instance singleton du classifier (lazy loading)."""
    global _instance
    if _instance is None:
        from api.config import settings
        _instance = DocumentClassifier(
            model_path=settings.model_path,
            vectorizer_path=settings.vectorizer_path,
            confidence_threshold=settings.classification_confidence_threshold,
        )
        _instance.load()
    return _instance
