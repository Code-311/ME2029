up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f backend frontend

test-backend:
	docker compose run --rm backend pytest

test-frontend:
	docker compose run --rm frontend npm test

migrate:
	docker compose run --rm backend alembic upgrade head
