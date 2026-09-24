START_DATE ?= 2026-02-01
END_DATE ?= 2026-08-01
CAUSAL_DIAGRAM_SOURCE ?= src/mermaid/DUR.mmd
CAUSAL_DIAGRAM_OUTPUT ?= outputs/charts/DUR_detailed.png

.PHONY: setup generate-task-table create-causal-diagram test

setup:
	uv sync

generate-task-table:
	uv run python src/python/generate_task_table.py --start-date "$(START_DATE)" --end-date "$(END_DATE)"

create-causal-diagram:
	mkdir -p "$(dir $(CAUSAL_DIAGRAM_OUTPUT))"
	docker run --rm -v "$(CURDIR):/mermaid" minlag/mermaid-cli -i "/mermaid/$(CAUSAL_DIAGRAM_SOURCE)" -o "/mermaid/$(CAUSAL_DIAGRAM_OUTPUT)" -w 2400 -H 1600

test:
	uv run pytest
