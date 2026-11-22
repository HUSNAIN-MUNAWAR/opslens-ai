.PHONY: up down api web seed animation real-runtime migrate test lint typecheck screenshots
up:
	docker compose up --build

down:
	docker compose down -v

api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

migrate:
	cd apps/api && alembic upgrade head

seed:
	cd apps/api && python -m app.seed --reset

animation:
	python scripts/generate_opslens_animation.py

real-runtime:
	python scripts/generate_real_runtime_video.py

test:
	cd apps/api && pytest -q

lint:
	cd apps/api && ruff check .
	cd apps/web && npm run lint

typecheck:
	cd apps/api && mypy app
	cd apps/web && npm run typecheck

screenshots:
	cd apps/web && npm run screenshots
