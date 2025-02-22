.PHONY: test help draft

help: ## Show this help message
	@echo 'Usage:'
	@echo '  make [target]'
	@echo ''
	@echo 'Targets:'
	@awk -F ':|##' '/^[^\t].+?:.*?##/ { printf "  %-20s %s\n", $$1, $$NF }' $(MAKEFILE_LIST)

test: ## Run test with sample job posting and compile PDF
	uv run python main.py -j "https://www.itjobs.ch/jobs/software-systems-engineering-business-support-services-technology/121110" -n Test -d test/personal-data

draft: ## Generate LaTeX without compiling to PDF
	uv run python main.py -j "https://www.itjobs.ch/jobs/software-systems-engineering-business-support-services-technology/121110" -n Test -d test/personal-data --no-compile
