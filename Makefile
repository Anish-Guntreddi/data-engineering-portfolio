# Green Gates — Data Engineering Portfolio (top-level convenience targets)
# Each project is self-contained; these targets just delegate to it.

.DEFAULT_GOAL := help
PROJECTS := warehouselab streampulse dataguard

.PHONY: help
help: ## Show this help
	@echo "Green Gates — Data Engineering Portfolio"
	@echo ""
	@echo "Per-project unit tests (no Docker):"
	@echo "  make test-warehouselab   make test-streampulse   make test-dataguard"
	@echo "  make test-all            run every project's host unit tests"
	@echo ""
	@echo "End-to-end runs (need Docker) live in each project:"
	@echo "  cd warehouselab && make run"
	@echo "  cd streampulse  && make e2e"
	@echo "  cd dataguard    && make demo"

.PHONY: test-warehouselab
test-warehouselab: ## WarehouseLab host unit tests (generator determinism + golden values)
	$(MAKE) -C warehouselab test

.PHONY: test-streampulse
test-streampulse: ## StreamPulse host unit tests (windowing / metrics / alerting)
	$(MAKE) -C streampulse test

.PHONY: test-dataguard
test-dataguard: ## DataGuard host unit tests (checks / drift / scoring)
	$(MAKE) -C dataguard test

.PHONY: test-all
test-all: test-warehouselab test-streampulse test-dataguard ## Run all host unit tests

.PHONY: clean
clean: ## Tear down every project's docker compose stack
	-@for p in $(PROJECTS); do $(MAKE) -C $$p down 2>/dev/null || true; done
