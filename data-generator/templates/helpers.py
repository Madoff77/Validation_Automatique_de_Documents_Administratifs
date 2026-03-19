"""
Utilitaires partagés par tous les templates de documents.

Ne pas mettre _gen_company ici (dépendance à l'API SIRENE dans generator.py).
La factory est injectée via register_company_factory() depuis generator.py.
"""

import random
from datetime import date, timedelta
from faker import Faker

fake = Faker("fr_FR")

# Injection de la factory d'entreprise
_company_factory = None


def register_company_factory(fn):
    """Enregistrer la fonction _gen_company depuis generator.py."""
    global _company_factory
    _company_factory = fn


def get_company() -> dict:
    """Obtenir un dict entreprise. Nécessite register_company_factory() préalable."""
    if _company_factory is None:
        raise RuntimeError(
            "Company factory non enregistrée. "
            "Assurez-vous que generator.py est importé avant de générer des documents."
        )
    return _company_factory()


# Générateurs de données

def _gen_amounts(base_min: float = 500, base_max: float = 50000) -> dict:
    ht = round(random.uniform(base_min, base_max), 2)
    taux = random.choice([20.0, 10.0, 5.5, 2.1])
    tva = round(ht * taux / 100, 2)
    ttc = round(ht + tva, 2)
    return {"ht": ht, "tva": tva, "ttc": ttc, "taux": taux}


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
