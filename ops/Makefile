.PHONY: test test-log reissue-key create-migration

test: ##output to console
	docker exec ops-backend-1 python -m pytest tests/integration/ -v

test-log: ## test_results.log
	docker exec ops-backend-1 sh -c "python -m pytest tests/integration/ -v --tb=long 2>&1 | tee /app/test_results.log"
	@echo ""
	@echo "Full test results saved to: backend/test_results.log"

reissue-key: ## reissue dev API key
	docker exec -w /app ops-backend-1 python utils/reissue_dev_key.py

create-migration: ## create Alembic revision, (usage: make create-migration MESSAGE="add table")
	docker exec -w /app ops-backend-1 alembic revision --autogenerate -m "$(MESSAGE)"
