.PHONY: up down logs migrate makemigration test demo

up:
	docker compose up --build -d

logs:
	docker compose logs -f api

down:
	docker compose down -v

migrate:
	docker compose exec api alembic upgrade head

makemigration:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

test:
	docker compose exec api pytest -q