.PHONY: install run test lint audit check docker-build up down smoke kind-deploy

install:        ## Create the virtualenv and install dependencies
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

run:            ## Run the API locally on http://127.0.0.1:8000
	DATABASE_PATH=./tasks.db .venv/bin/python wsgi.py

test:           ## Unit tests with coverage
	.venv/bin/pytest --cov=app --cov-report=term-missing

lint:           ## Static analysis
	.venv/bin/ruff check .

audit:          ## Known vulnerabilities in dependencies
	.venv/bin/pip-audit -r requirements.txt --strict

check: lint test audit  ## Everything the pipeline checks before building

docker-build:   ## Build the container image
	docker build -t tasks-api:local --build-arg APP_VERSION=local .

up:             ## API + Prometheus + Grafana
	docker compose up --build -d

down:
	docker compose down

smoke:          ## Exercise the running API end to end
	bash scripts/smoke_test.sh http://localhost:8000

kind-deploy: docker-build  ## Deploy to a local kind cluster
	kind create cluster --name demo || true
	kind load docker-image tasks-api:local --name demo
	kubectl apply -k k8s
	kubectl -n tasks-api rollout status deployment/tasks-api --timeout=120s
