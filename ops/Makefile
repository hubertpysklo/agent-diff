.PHONY: test test-log test-results

test: ## Run integration tests (output to console)
	docker exec ops-backend-1 python -m pytest tests/integration/ -v

test-log: ## Run tests - save full output to test_results.log
	docker exec ops-backend-1 sh -c "python -m pytest tests/integration/ -v --tb=long 2>&1 | tee /app/test_results.log"
	@echo ""
	@echo "Full test results saved to: backend/test_results.log"
