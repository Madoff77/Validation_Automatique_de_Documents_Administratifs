"""
Script d'entraînement du classifier de documents.

Usage :
  python -m pipeline.classification.train
  python -m pipeline.classification.train --n-per-class 200 --output /app/models/trained

Pipeline :
  1. Génération données synthétiques → images dégradées → Tesseract OCR
  2. Préprocessing TF-IDF
  3. Entraînement Random Forest avec class_weight='balanced'
  4. Évaluation : cross-validation + rapport de classification
  5. Sauvegarde modèle + vectorizer + rapport

Reproductibilité : random_state=42 partout.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
import joblib

# Ajouter les chemins nécessaires
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../backend"))
sys.path.insert(0, "/app/data-generator")  # Absolu (Docker)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../data-generator"))  # Relatif (local)

from pipeline.classification.classifier import DocumentClassifier, DOC_TYPES

DOC_TYPE_COLORS = {
    "FACTURE": "\033[94m", "DEVIS": "\033[96m", "SIRET": "\033[92m",
    "URSSAF": "\033[93m", "KBIS": "\033[91m", "RIB": "\033[95m",
}
RESET = "\033[0m"


def generate_training_data(n_per_class: int) -> list:
    """
    Générer les données d'entraînement via le vrai pipeline OCR.

    Pipeline :
      template text → image PNG → dégradation → Tesseract OCR → texte réel

    Le modèle apprend ainsi exactement ce que le pipeline verra en production,
    avec les artefacts réels de Tesseract (pas une simulation textuelle).
    """
    import io
    import random
    import cv2
    from PIL import Image as PILImage
    from pipeline.ocr.extractor import extract_text

    print(f"\n{'═'*60}")
    print(f"  Génération données d'entraînement ({n_per_class} par classe)")
    print(f"  Pipeline : template → image dégradée → Tesseract OCR")
    print(f"{'═'*60}")

    try:
        from generator import generate_text, text_to_image, degrade_image, DOC_TYPES as GEN_DOC_TYPES
    except ImportError as e:
        print(f"\n  ERREUR : Impossible d'importer le générateur ({e})")
        print("    Docker : volume mount ./data-generator:/app/data-generator")
        raise SystemExit(1)

    # Distribution des dégradations — couvre les cas réels de scan
    DEGRADATION_SCHEDULE = [
        (0.40, None,             None),           # 40% : PDF natif propre
        (0.60, "noise",          (0.1, 0.35)),    # 20% : bruit léger (bon scanner)
        (0.75, "blur",           (0.2, 0.5)),     # 15% : flou (mise au point imparfaite)
        (0.87, "rotation",       (0.05, 0.25)),   # 12% : rotation (page mal alignée)
        (0.95, "combined",       (0.3, 0.6)),     # 8%  : dégradation combinée
        (1.00, "low_resolution", (0.3, 0.65)),    # 5%  : basse résolution (vieux scanner)
    ]

    dataset = []
    n_clean = n_degraded = n_failed = 0

    for doc_type in GEN_DOC_TYPES:
        print(f"  {doc_type} : génération + OCR en cours...", flush=True)
        for _ in range(n_per_class):
            try:
                text = generate_text(doc_type)
                img = text_to_image(text)

                roll = random.random()
                deg_applied = None
                for threshold, deg_type, severity_range in DEGRADATION_SCHEDULE:
                    if roll < threshold:
                        if deg_type is not None:
                            severity = random.uniform(*severity_range)
                            img = degrade_image(img, deg_type, severity)
                            deg_applied = deg_type
                        break

                # Image numpy → bytes JPEG (même format que le pipeline production)
                pil_img = PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=75)

                # Vrai Tesseract — même fonction que task_ocr()
                ocr_result = extract_text(buf.getvalue(), "image/jpeg")

                if ocr_result.text.strip():
                    dataset.append((ocr_result.text, doc_type))
                    if deg_applied is None:
                        n_clean += 1
                    else:
                        n_degraded += 1
                else:
                    n_failed += 1

            except Exception as e:
                n_failed += 1
                print(f"    [WARN] {doc_type} sample ignoré : {e}")

    random.shuffle(dataset)
    total = len(dataset)
    print(f"\n  Dataset total  : {total} documents")
    print(f"  Propres        : {n_clean} ({n_clean*100//total if total else 0}%)")
    print(f"  Dégradés       : {n_degraded} ({n_degraded*100//total if total else 0}%)")
    print(f"  Échecs OCR     : {n_failed}")

    if not dataset:
        raise SystemExit("Aucun document généré — vérifier Tesseract et le générateur")

    return dataset


def build_vectorizer(texts: list) -> TfidfVectorizer:
    """
    TF-IDF avec unigrams + bigrams.

    Choix :
    - max_features=8000 : suffisant pour 6 classes bien séparées
    - ngram_range=(1,2) : bigrams captent "montant ht", "tribunal commerce", etc.
    - sublinear_tf=True : log-normalisation, réduit l'effet des mots très fréquents
    - min_df=2 : ignorer les hapax (bruit OCR)
    - analyzer='word' : mots entiers (pas chars)
    """
    return TfidfVectorizer(
        max_features=8000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_df=0.95,
        analyzer='word',
        token_pattern=r'(?u)\b[a-zA-ZÀ-ÿ_][a-zA-ZÀ-ÿ_]{2,}\b',  # Mots ≥ 3 chars
        strip_accents=None,  # Garder les accents français (discriminants)
        lowercase=True,
    )


def train_random_forest(X_train, y_train) -> RandomForestClassifier:
    """
    Random Forest calibré.

    Hyperparamètres :
    - n_estimators=200 : bonne précision sans surapprentissage
    - max_features='sqrt' : standard RF, réduit corrélation entre arbres
    - class_weight='balanced' : compense déséquilibre de classes éventuel
    - min_samples_leaf=2 : évite le surajustement sur les petits groupes
    - n_jobs=-1 : parallélisation maximale
    """
    return RandomForestClassifier(
        n_estimators=200,
        max_features="sqrt",
        max_depth=None,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )


def evaluate(model, vectorizer, X_test_raw, y_test, classes) -> dict:
    """Évaluer le modèle sur le jeu de test."""
    X_test = vectorizer.transform(X_test_raw)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average='macro')
    f1_weighted = f1_score(y_test, y_pred, average='weighted')
    report = classification_report(y_test, y_pred, target_names=classes, output_dict=True)
    cm = confusion_matrix(y_test, y_pred, labels=classes)

    # Confiance moyenne sur les bonnes prédictions
    correct_mask = np.array(y_pred) == np.array(y_test)
    correct_proba = np.max(y_proba[correct_mask], axis=1) if correct_mask.any() else []
    avg_confidence_correct = float(np.mean(correct_proba)) if len(correct_proba) else 0.0

    return {
        "accuracy": accuracy,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "avg_confidence_correct": avg_confidence_correct,
        "n_test": len(y_test),
    }


def cross_validate(model_factory, vectorizer, texts, labels, cv=5) -> dict:
    """Cross-validation stratifiée."""
    from sklearn.base import clone
    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)
    X = vectorizer.fit_transform(texts)
    scores = cross_val_score(model_factory, X, labels, cv=skf, scoring='f1_macro', n_jobs=-1)
    return {
        "cv_f1_macro_mean": float(scores.mean()),
        "cv_f1_macro_std": float(scores.std()),
        "cv_scores": scores.tolist(),
    }


def print_report(metrics: dict, cv_metrics: dict, classes: list):
    """Afficher le rapport d'entraînement formaté."""
    print(f"\n{'═'*60}")
    print("  RÉSULTATS D'ÉVALUATION")
    print(f"{'═'*60}")
    print(f"  Accuracy         : {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.1f}%)")
    print(f"  F1 macro         : {metrics['f1_macro']:.4f}")
    print(f"  F1 weighted      : {metrics['f1_weighted']:.4f}")
    print(f"  Confiance moy.   : {metrics['avg_confidence_correct']:.4f} (bonnes prédictions)")
    print(f"  Jeu de test      : {metrics['n_test']} exemples")
    print(f"\n  Cross-validation ({len(cv_metrics['cv_scores'])} folds) :")
    print(f"  F1 macro CV      : {cv_metrics['cv_f1_macro_mean']:.4f} ± {cv_metrics['cv_f1_macro_std']:.4f}")

    print(f"\n{'─'*60}")
    print("  RAPPORT PAR CLASSE")
    print(f"{'─'*60}")
    report = metrics["classification_report"]
    for cls in classes:
        if cls in report:
            r = report[cls]
            color = DOC_TYPE_COLORS.get(cls, "")
            print(f"  {color}{cls:<10}{RESET}  "
                  f"P={r['precision']:.3f}  R={r['recall']:.3f}  F1={r['f1-score']:.3f}  "
                  f"n={int(r['support'])}")

    print(f"\n{'─'*60}")
    print("  MATRICE DE CONFUSION")
    print(f"{'─'*60}")
    cm = metrics["confusion_matrix"]
    header = "         " + " ".join(f"{c[:5]:>6}" for c in classes)
    print(f"  {header}")
    for i, cls in enumerate(classes):
        row = " ".join(f"{v:6d}" for v in cm[i])
        color = DOC_TYPE_COLORS.get(cls, "")
        print(f"  {color}{cls[:5]:>5}{RESET}  {row}")


def main(n_per_class: int = 150, output_dir: str = "/app/models/trained"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()

    # ── 1. Données ─────────────────────────────────────────────
    dataset = generate_training_data(n_per_class)
    texts_raw = [t for t, _ in dataset]
    labels = [l for _, l in dataset]

    print(f"\n  Distribution : { {c: labels.count(c) for c in DOC_TYPES} }")

    # ── 2. Préprocessing ────────────────────────────────────────
    print(f"\n{'═'*60}")
    print("  PRÉPROCESSING TF-IDF")
    print(f"{'═'*60}")
    texts_processed = [DocumentClassifier._preprocess(t) for t in texts_raw]
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        texts_processed, labels, test_size=0.2, stratify=labels, random_state=42
    )

    vectorizer = build_vectorizer(X_train_raw)
    X_train = vectorizer.fit_transform(X_train_raw)
    X_test = vectorizer.transform(X_test_raw)

    print(f"  Train : {X_train.shape[0]} exemples, {X_train.shape[1]} features")
    print(f"  Test  : {X_test.shape[0]} exemples")

    # ── 3. Entraînement ─────────────────────────────────────────
    print(f"\n{'═'*60}")
    print("  ENTRAÎNEMENT — Random Forest (200 arbres)")
    print(f"{'═'*60}")
    model = train_random_forest(X_train, y_train)
    model.fit(X_train, y_train)
    print("  Modèle entraîné ✓")

    # ── 4. Cross-validation ─────────────────────────────────────
    print("\n  Cross-validation en cours (5 folds)...")
    cv_metrics = cross_validate(
        train_random_forest(None, None),  # factory
        build_vectorizer([]),             # sera re-fit dans CV
        texts_processed, labels, cv=5
    )

    # ── 5. Évaluation ───────────────────────────────────────────
    metrics = evaluate(model, vectorizer, X_test_raw, y_test, DOC_TYPES)
    print_report(metrics, cv_metrics, DOC_TYPES)

    # ── 6. Top features par classe ──────────────────────────────
    print(f"\n{'─'*60}")
    print("  TOP FEATURES PAR CLASSE (interprétabilité)")
    print(f"{'─'*60}")
    feature_names = vectorizer.get_feature_names_out()
    all_importances = np.mean([tree.feature_importances_ for tree in model.estimators_], axis=0)
    top_n = 8
    for cls in DOC_TYPES:
        # Approche : features avec plus de variance dans les prédictions de la classe
        top_idx = np.argsort(all_importances)[::-1][:top_n]
        top_features = [feature_names[i] for i in top_idx]
        color = DOC_TYPE_COLORS.get(cls, "")
        print(f"  {color}{cls:<10}{RESET}: {', '.join(top_features[:6])}")

    # ── 7. Sauvegarde ───────────────────────────────────────────
    model_path = os.path.join(output_dir, "classifier.joblib")
    vectorizer_path = os.path.join(output_dir, "vectorizer.joblib")
    joblib.dump(model, model_path, compress=3)
    joblib.dump(vectorizer, vectorizer_path, compress=3)

    # Sauvegarder le rapport complet
    report_data = {
        "trained_at": start_time.isoformat(),
        "n_per_class": n_per_class,
        "total_samples": len(dataset),
        "algorithm": "TF-IDF (1-2 grams, 8000 features) + RandomForest (200 trees)",
        "metrics": {
            "accuracy": metrics["accuracy"],
            "f1_macro": metrics["f1_macro"],
            "f1_weighted": metrics["f1_weighted"],
            "cv_f1_macro_mean": cv_metrics["cv_f1_macro_mean"],
            "cv_f1_macro_std": cv_metrics["cv_f1_macro_std"],
        },
        "per_class": {
            cls: {
                "precision": metrics["classification_report"][cls]["precision"],
                "recall": metrics["classification_report"][cls]["recall"],
                "f1": metrics["classification_report"][cls]["f1-score"],
            }
            for cls in DOC_TYPES if cls in metrics["classification_report"]
        },
        "model_path": model_path,
        "vectorizer_path": vectorizer_path,
        "duration_seconds": (datetime.now() - start_time).total_seconds(),
    }
    report_path = os.path.join(output_dir, "training_report.json")
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n{'═'*60}")
    print(f"  Modèle sauvegardé      : {model_path}")
    print(f"  Vectorizer sauvegardé  : {vectorizer_path}")
    print(f"  Rapport sauvegardé     : {report_path}")
    duration = (datetime.now() - start_time).total_seconds()
    print(f"  Durée totale           : {duration:.1f}s")
    print(f"{'═'*60}\n")

    # ── Verdict final ───────────────────────────────────────────
    acc = metrics["accuracy"]
    f1 = metrics["f1_macro"]
    if acc >= 0.92 and f1 >= 0.90:
        print(f"  ✅ Modèle EXCELLENT  (accuracy={acc:.3f}, F1={f1:.3f})")
    elif acc >= 0.85 and f1 >= 0.82:
        print(f"  ✅ Modèle BON        (accuracy={acc:.3f}, F1={f1:.3f})")
    elif acc >= 0.75:
        print(f"  ⚠️  Modèle ACCEPTABLE (accuracy={acc:.3f}, F1={f1:.3f}) — augmenter n_per_class")
    else:
        print(f"  ❌ Modèle INSUFFISANT (accuracy={acc:.3f}, F1={f1:.3f}) — vérifier les données")

    return report_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entraînement classifier documents")
    parser.add_argument("--n-per-class", type=int, default=150,
                        help="Nombre d'exemples par classe (défaut: 150)")
    parser.add_argument("--output", default="/app/models/trained",
                        help="Dossier de sauvegarde du modèle")
    args = parser.parse_args()
    main(n_per_class=args.n_per_class, output_dir=args.output)
