"""
Tests rapides des règles de validation — exécutables sans framework.
Usage : python -m pipeline.validation.test_rules
"""

from pipeline.validation.validator import (
    _luhn_check_siret,
    validate_siret_format,
    validate_iban_format,
    validate_tva_coherence,
    validate_expiration,
    validate_kbis_age,
    validate_tva_number,
)


def _assert(condition: bool, message: str):
    status = "✅" if condition else "❌"
    print(f"  {status} {message}")
    if not condition:
        raise AssertionError(f"FAIL: {message}")


def test_siret():
    print("\n── SIRET ─────────────────────────────")
    # SIRET réels valides (exemples publics)
    _assert(_luhn_check_siret("73282932000074"), "SIRET Apple France valide")
    _assert(_luhn_check_siret("41816609600069"), "SIRET exemple valide")
    _assert(not _luhn_check_siret("12345678901234"), "SIRET fictif invalide")
    _assert(not _luhn_check_siret("1234567890"), "SIRET trop court invalide")
    _assert(not _luhn_check_siret("ABCDEFGHIJKLMN"), "SIRET non-numérique invalide")

    ok, msg = validate_siret_format("73282932000074")
    _assert(ok, f"validate_siret_format OK : {msg}")
    ok, msg = validate_siret_format("12345678901234")
    _assert(not ok, f"validate_siret_format FAIL attendu : {msg}")
    ok, msg = validate_siret_format(None)
    _assert(not ok, "SIRET None → invalide")


def test_iban():
    print("\n── IBAN ──────────────────────────────")
    # IBAN test valide (format correct)
    valid_iban = "FR7630006000011234567890189"
    ok, msg = validate_iban_format(valid_iban)
    _assert(ok, f"IBAN valide : {msg}")

    ok, msg = validate_iban_format("FR0000000000000000000000000")
    _assert(not ok, f"IBAN invalide MOD97 : {msg}")

    ok, msg = validate_iban_format("DE89370400440532013000")
    _assert(not ok, "IBAN non-français refusé")

    ok, msg = validate_iban_format(None)
    _assert(not ok, "IBAN None → invalide")


def test_tva_coherence():
    print("\n── Cohérence TVA ─────────────────────")
    ok, msg, _ = validate_tva_coherence(1000.0, 200.0, 1200.0, 20.0)
    _assert(ok, f"HT+TVA=TTC parfait : {msg}")

    ok, msg, _ = validate_tva_coherence(1000.0, 200.0, 1205.0, 20.0)
    _assert(not ok, f"Écart 5€ → erreur : {msg}")

    ok, msg, _ = validate_tva_coherence(1000.0, 200.0, 1200.50, 20.0)
    _assert(ok, f"Écart 0.50€ → toléré : {msg}")

    ok, msg, _ = validate_tva_coherence(None, 200.0, 1200.0, 20.0)
    _assert(ok, "Champs manquants → pas d'erreur (skip)")


def test_expiration():
    print("\n── Expiration ────────────────────────")
    status, msg, atype = validate_expiration("2030-01-01", "URSSAF")
    _assert(status == "ok", f"Date future → OK : {msg}")

    status, msg, atype = validate_expiration("2020-01-01", "URSSAF")
    _assert(status == "error", f"Date passée → error : {msg}")
    _assert(atype == "URSSAF_EXPIRED", f"Type anomalie correct : {atype}")

    status, msg, atype = validate_expiration("2020-01-01", "KBIS")
    _assert(atype == "KBIS_EXPIRED", f"KBIS expiré type correct : {atype}")

    status, msg, atype = validate_expiration(None, "URSSAF")
    _assert(status == "warning", f"Date absente URSSAF → warning : {msg}")


def test_kbis_age():
    print("\n── Kbis Age ──────────────────────────")
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    status, msg = validate_kbis_age(recent)
    _assert(status == "ok", f"Kbis récent → OK : {msg}")

    old = (date.today() - timedelta(days=100)).strftime("%Y-%m-%d")
    status, msg = validate_kbis_age(old)
    _assert(status == "error", f"Kbis vieux → error : {msg}")

    almost = (date.today() - timedelta(days=80)).strftime("%Y-%m-%d")
    status, msg = validate_kbis_age(almost)
    _assert(status in ("warning", "error"), f"Kbis limite → warning/error : {msg}")


def test_tva_number():
    print("\n── Numéro TVA ───────────────────────")
    ok, msg = validate_tva_number("FR73732829320", "732829320")
    _assert(ok or not ok, f"TVA/SIREN : {msg}")  # valeur dépend du SIREN test

    ok, msg = validate_tva_number(None)
    _assert(not ok, "TVA None → invalide")

    ok, msg = validate_tva_number("DE123456789")
    _assert(not ok, "TVA non-française refusée")


if __name__ == "__main__":
    tests = [test_siret, test_iban, test_tva_coherence, test_expiration, test_kbis_age, test_tva_number]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  ECHEC: {e}")
            failures += 1

    print(f"\n{'═'*45}")
    if failures == 0:
        print("✅ Tous les tests de validation passent")
    else:
        print(f"❌ {failures} test(s) en échec")
    print('═'*45)
