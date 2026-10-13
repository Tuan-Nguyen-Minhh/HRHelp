.PHONY: run test lint format typecheck check clean compose-desktop compose-desktop-down compose-desktop-logs

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

compose-desktop:
	docker compose -f docker-compose.yml -f docker-compose.desktop.yml up --build --force-recreate --remove-orphans

compose-desktop-down:
	docker compose -f docker-compose.yml -f docker-compose.desktop.yml down

compose-desktop-logs:
	docker compose -f docker-compose.yml -f docker-compose.desktop.yml logs -f backend
