.PHONY: help up down build logs seed train demo clean restart reset-docs

help:
	@echo "DocPlatform — Commandes disponibles"
	@echo "======================================"
	@echo "  make up          — Démarrer tous les services"
	@echo "  make down        — Arrêter tous les services"
	@echo "  make build       — Rebuild les images Docker"
	@echo "  make logs        — Afficher les logs en temps réel"
	@echo "  make seed        — Charger les données de démo"
	@echo "  make train       — Entraîner le modèle de classification"
	@echo "  make reset-docs  — Remettre tous les docs en 'pending' (test Airflow)"
	@echo "  make demo        — Lancer le scénario de démonstration"
	@echo "  make clean       — Supprimer volumes et containers"
	@echo "  make restart     — Redémarrer les services"

up:
	@cp -n .env.example .env 2>/dev/null || true
	docker compose up -d
	@echo "Services démarrés :"
	@echo "  API Backend    : http://localhost:8000"
	@echo "  API Docs       : http://localhost:8000/docs"
	@echo "  CRM            : http://localhost:5173"
	@echo "  Compliance     : http://localhost:5174"
	@echo "  Airflow        : http://localhost:8080 (admin/admin)"
	@echo "  MinIO Console  : http://localhost:9001 (minioadmin/minioadmin)"
	@echo "  Mongo Express  : http://localhost:8081 (admin/admin)"

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

seed:
	docker compose exec backend-api python /app/scripts/seed.py

train:
	docker compose exec backend-api python /app/pipeline/classification/train.py

reset-docs:
	@echo "Remise en pending de tous les documents (pour test Airflow end-to-end)..."
	docker compose exec -T mongo mongosh "mongodb://root:rootpassword@localhost:27017/docplatform?authSource=admin" --eval "db.documents.updateMany({}, {`$set: {status: 'pending', error_message: null}})"
	@echo "Tous les documents sont en 'pending'. Déclenchez le DAG depuis l'UI Airflow."

demo:
	@bash scripts/demo.sh

restart:
	docker compose restart

clean:
	docker compose down -v --remove-orphans
	@echo "Volumes supprimés"
