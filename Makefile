SHELL := /bin/bash
COMPOSE := docker compose
BACKEND := backend
FRONTEND := frontend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help
help: ## Komut listesi
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- canlı ortam

.PHONY: dev
dev: .env ## Tüm ortamı ayağa kaldırır (postgres+redis+api+worker+frontend)
	$(COMPOSE) up -d --build
	@$(MAKE) --no-print-directory wait-healthy
	@$(MAKE) --no-print-directory migrate
	@echo ""
	@echo "  Kavun ayakta:"
	@echo "    Frontend : http://localhost:3000"
	@echo "    API      : http://localhost:8000/docs"
	@echo ""
	@echo "  Demo veri için: make seed-demo"
	@echo ""

.PHONY: wait-healthy
wait-healthy: ## API sağlıklı olana kadar bekler
	@echo "API sağlık kontrolü bekleniyor..."
	@for i in $$(seq 1 60); do \
		if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then echo "API hazır."; exit 0; fi; \
		sleep 2; \
	done; \
	echo "API 120 sn içinde ayağa kalkmadı."; $(COMPOSE) logs --tail=50 api; exit 1

.PHONY: down
down: ## Ortamı durdurur
	$(COMPOSE) down

.PHONY: clean
clean: ## Ortamı ve volume'ları siler
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Servis loglarını izler
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Servis durumları
	$(COMPOSE) ps

.env: ## .env yoksa .env.example'dan üretir
	@test -f .env || (cp .env.example .env && echo ".env oluşturuldu (.env.example'dan)")

# ------------------------------------------------------------ yerel geliştirme

$(VENV): $(BACKEND)/pyproject.toml ## Backend sanal ortamı
	cd $(BACKEND) && (command -v uv >/dev/null && uv venv .venv --python 3.12 && uv pip install -e ".[dev]" \
		|| (python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"))
	@touch $(VENV)

.PHONY: install
install: $(VENV) ## Backend + frontend bağımlılıkları
	cd $(FRONTEND) && npm install

# --------------------------------------------------------------- kalite kapısı

.PHONY: lint
lint: $(VENV) ## ruff + para/float kuralı
	cd $(BACKEND) && .venv/bin/ruff check .
	cd $(BACKEND) && .venv/bin/ruff format --check .
	cd $(BACKEND) && .venv/bin/python -m tools.check_money_float app

.PHONY: format
format: $(VENV) ## Kodu biçimlendirir
	cd $(BACKEND) && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

.PHONY: typecheck
typecheck: $(VENV) ## mypy --strict
	cd $(BACKEND) && .venv/bin/mypy app tools tests

.PHONY: test
test: $(VENV) ## pytest + coverage
	cd $(BACKEND) && .venv/bin/pytest --cov=app --cov-report=term-missing

.PHONY: check
check: lint typecheck test ## CI'nin çalıştırdığı her şey
	cd $(FRONTEND) && npm run typecheck && npm run lint && npm run build

# ------------------------------------------------------------------- yardımcı

.PHONY: migrate
migrate: ## Alembic migration'larını uygular
	$(COMPOSE) exec -T api alembic upgrade head

.PHONY: seed
seed: ## Çekirdek veriyi kurar (tenant, marka, kanal, mağaza)
	$(COMPOSE) exec -T api python -m app.cli seed

.PHONY: seed-demo
seed-demo: ## Demo tenant'ını gerçekçi örnek veriyle doldurur
	$(COMPOSE) exec -T api python -m app.cli seed-demo

.PHONY: wipe-demo
wipe-demo: ## Demo verisini siler (gerçek tenant'a dokunmaz)
	$(COMPOSE) exec -T api python -m app.cli wipe-demo

.PHONY: revision
revision: $(VENV) ## Yeni migration üretir: make revision m="açıklama"
	cd $(BACKEND) && .venv/bin/alembic revision --autogenerate -m "$(m)"

.PHONY: shell
shell: ## API konteynerinde kabuk
	$(COMPOSE) exec api bash

.PHONY: gen-api
gen-api: ## OpenAPI'den frontend tipleri üretir
	cd $(FRONTEND) && npm run gen:api
