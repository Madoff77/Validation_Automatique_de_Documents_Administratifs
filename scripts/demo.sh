#!/usr/bin/env bash
# =============================================================================
# DocPlatform — Scénario de démo complet
# Usage: ./scripts/demo.sh
# =============================================================================
set -euo pipefail

API="http://localhost:8000"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}>> $1${RESET}"; }
ok()   { echo -e "  ${GREEN}[OK] $1${RESET}"; }
warn() { echo -e "  ${YELLOW}[WARN] $1${RESET}"; }
info() { echo -e "  ${CYAN}→ $1${RESET}"; }

# ===========================================================================
echo -e "\n${BOLD}╔══════════════════════════════════════════════════════════╗"
echo -e "║      DocPlatform — Démonstration Pipeline Complet        ║"
echo -e "╚══════════════════════════════════════════════════════════╝${RESET}"
# ===========================================================================

# ---------------------------------------------------------------------------
step "1/6 — Vérification de l'API"
# ---------------------------------------------------------------------------
if ! curl -sf "$API/health" > /dev/null 2>&1; then
  echo -e "${RED}API non accessible. Lancer 'make up' d'abord.${RESET}"
  exit 1
fi
ok "API disponible sur $API"

# ---------------------------------------------------------------------------
step "2/6 — Authentification (admin)"
# ---------------------------------------------------------------------------
AUTH=$(curl -sf -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

TOKEN=$(echo "$AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
ok "Token JWT obtenu"
info "Rôle: admin"

H="Authorization: Bearer $TOKEN"

# ---------------------------------------------------------------------------
step "3/6 — État initial de la base"
# ---------------------------------------------------------------------------
STATS=$(curl -sf "$API/stats/dashboard" -H "$H")
echo "$STATS" | python3 -c "
import sys, json
s = json.load(sys.stdin)
print(f'  Fournisseurs: {s.get(\"total_suppliers\",0)}')
print(f'  Documents: {s.get(\"total_documents\",0)}')
print(f'  Anomalies non résolues: {s.get(\"unresolved_anomalies\",0)}')
print(f'  Anomalies critiques: {s.get(\"critical_anomalies\",0)}')
print(f'  Documents expirant bientôt: {s.get(\"documents_expiring_soon\",0)}')
"

# ---------------------------------------------------------------------------
step "4/6 — Upload et traitement d'un document de démonstration"
# ---------------------------------------------------------------------------

# Générer un document de test via le générateur
DOC_FILE="/tmp/demo_facture_$(date +%s).pdf"
python3 -c "
import sys
sys.path.insert(0, '/app/data-generator')
from generator import generate_text, _text_to_pdf
text = generate_text('FACTURE')
pdf_bytes = _text_to_pdf(text, title='FACTURE')
if pdf_bytes:
    with open('$DOC_FILE', 'wb') as f:
        f.write(pdf_bytes)
    print(f'Fichier généré ({len(pdf_bytes)} bytes)')
" 2>/dev/null || {
  # Fallback: créer un PDF minimal
  python3 -c "
from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.set_font('Helvetica', size=12)
pdf.cell(0, 10, 'FACTURE N FA-2024-001', ln=True)
pdf.cell(0, 10, 'SIRET: 73282932000074', ln=True)
pdf.cell(0, 10, 'Montant HT: 1000.00 EUR', ln=True)
pdf.cell(0, 10, 'TVA 20%: 200.00 EUR', ln=True)
pdf.cell(0, 10, 'Montant TTC: 1200.00 EUR', ln=True)
pdf.output('$DOC_FILE')
print('Document de démonstration généré')
" 2>/dev/null || warn "Impossible de générer un fichier PDF, utilisation d'un fichier texte"
}

# Récupérer le premier fournisseur
SUPPLIER_ID=$(curl -sf "$API/suppliers?limit=1" -H "$H" | \
  python3 -c "import sys,json; suppliers=json.load(sys.stdin); print(suppliers[0]['supplier_id'] if suppliers else '')")

if [ -z "$SUPPLIER_ID" ]; then
  warn "Aucun fournisseur trouvé — utilisation du seed"
  SUPPLIER_ID="demo-supplier"
fi

info "Fournisseur cible: $SUPPLIER_ID"

if [ -f "$DOC_FILE" ]; then
  UPLOAD=$(curl -sf -X POST "$API/documents/upload" \
    -H "$H" \
    -F "file=@$DOC_FILE;type=application/pdf" \
    -F "supplier_id=$SUPPLIER_ID" \
    -F "doc_type=facture" 2>/dev/null || echo '{}')

  DOC_ID=$(echo "$UPLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('document_id',''))" 2>/dev/null || echo "")

  if [ -n "$DOC_ID" ] && [ "$DOC_ID" != "null" ]; then
    ok "Document uploadé: $DOC_ID"
    info "Pipeline Airflow déclenché"

    # Attendre le traitement (max 30s)
    echo "  Attente du traitement..."
    for i in $(seq 1 10); do
      sleep 3
      STATUS=$(curl -sf "$API/documents/$DOC_ID" -H "$H" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
      if [ "$STATUS" = "processed" ] || [ "$STATUS" = "failed" ]; then
        break
      fi
      echo -n "."
    done
    echo ""

    DOC_DETAIL=$(curl -sf "$API/documents/$DOC_ID" -H "$H")
    STATUS=$(echo "$DOC_DETAIL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
    DOC_TYPE=$(echo "$DOC_DETAIL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('doc_type',''))")
    CONFIDENCE=$(echo "$DOC_DETAIL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('classification_confidence',''))")

    ok "Statut final: $STATUS"
    ok "Type classifié: $DOC_TYPE (confiance: $CONFIDENCE)"
  else
    warn "Upload échoué ou Airflow non disponible"
  fi
  rm -f "$DOC_FILE"
fi

# ---------------------------------------------------------------------------
step "5/6 — Analyse des anomalies"
# ---------------------------------------------------------------------------
ANOMALIES=$(curl -sf "$API/anomalies?resolved=false&limit=20" -H "$H")
COUNT=$(echo "$ANOMALIES" | python3 -c "import sys,json; a=json.load(sys.stdin); print(len(a))")
ok "$COUNT anomalies non résolues détectées"

echo "$ANOMALIES" | python3 -c "
import sys, json
anomalies = json.load(sys.stdin)
by_severity = {}
for a in anomalies:
    s = a.get('severity','?')
    by_severity[s] = by_severity.get(s, 0) + 1
for sev, count in sorted(by_severity.items()):
    tag = '[ERR]' if sev == 'error' else '[WARN]' if sev == 'warning' else '[INFO]'
    print(f'  {tag} {sev}: {count}')
" 2>/dev/null || true

# Afficher les 3 premières
echo "$ANOMALIES" | python3 -c "
import sys, json
anomalies = json.load(sys.stdin)[:3]
for a in anomalies:
    print(f'  [{a[\"severity\"]}] {a[\"message\"][:70]}')
    if a.get('supplier_name'):
        print(f'    → Fournisseur: {a[\"supplier_name\"]}')
" 2>/dev/null || true

# ---------------------------------------------------------------------------
step "6/6 — Résumé de conformité fournisseurs"
# ---------------------------------------------------------------------------
SUPPLIERS=$(curl -sf "$API/suppliers?limit=50" -H "$H")
echo "$SUPPLIERS" | python3 -c "
import sys, json
suppliers = json.load(sys.stdin)
status_counts = {}
for s in suppliers:
    st = s.get('compliance_status', 'pending')
    status_counts[st] = status_counts.get(st, 0) + 1

total = len(suppliers)
compliant = status_counts.get('compliant', 0)
rate = round(compliant / total * 100) if total > 0 else 0

print(f'  Total fournisseurs: {total}')
print(f'  Conformes: {compliant}')
print(f'  Non conformes: {status_counts.get(\"non_compliant\", 0)}')
print(f'  Avertissements: {status_counts.get(\"warning\", 0)}')
print(f'  En attente: {status_counts.get(\"pending\", 0)}')
print(f'  Taux de conformité global: {rate}%')
" 2>/dev/null || true

# ---------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗"
echo -e "║                    Démo terminée avec succès              ║"
echo -e "╚══════════════════════════════════════════════════════════╝${RESET}"
echo -e ""
echo -e "  ${CYAN}Frontend CRM:        ${BOLD}http://localhost:3000${RESET}"
echo -e "  ${CYAN}Frontend Compliance: ${BOLD}http://localhost:3001${RESET}"
echo -e "  ${CYAN}API Swagger:         ${BOLD}http://localhost:8000/docs${RESET}"
echo -e "  ${CYAN}Airflow:             ${BOLD}http://localhost:8080${RESET}"
echo -e "  ${CYAN}MinIO Console:       ${BOLD}http://localhost:9001${RESET}"
echo -e ""
