.PHONY: up down logs migrate makemigration

up:
	docker compose up --build -d

logs:
	docker compose logs -f api

down:
	docker compose down

migrate:
	docker compose exec api alembic upgrade head

makemigration:
	docker compose exec api alembic revision --autogenerate -m "$(m)"