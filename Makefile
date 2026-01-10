.PHONY: lint format test docker-build

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check . --fix

test:
	pytest -q

docker-build:
	cd services/notification-api && docker build -t notifii-notification-api:dev .