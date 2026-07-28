.PHONY: up down logs migrate bootstrap backend-check frontend-check check

up:
	docker compose --profile core up -d --build

down:
	docker compose --profile core down

logs:
	docker compose --profile core logs -f

migrate:
	docker compose --profile core run --rm backend alembic upgrade head

bootstrap:
	docker compose --profile core run --rm backend python -m cyrvanta.bootstrap_admin --tenant-name "$(TENANT)" --email "$(EMAIL)" --password "$(PASSWORD)"

backend-check:
	cd backend && ruff check . && ruff format --check . && mypy && pytest

frontend-check:
	cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test

check: backend-check frontend-check
