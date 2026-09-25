START_DATE ?= 2026-02-01
END_DATE ?= 2026-08-01
USER_ID ?= 319402689
REDRAW_ONLY ?= 0
REDRAW ?= 0
CAUSAL_DIAGRAM_SOURCE ?= src/mermaid/DUR.mmd
CAUSAL_DIAGRAM_OUTPUT ?= outputs/charts/DUR_detailed.png

.PHONY: setup generate-task-table generate-task-intersection-table generate-task-sequence-table drop-task-table create-causal-diagram create-task-based-distributions create-task-time-bucket-distribution create-task-intersection-duration-distributions create-part-number-analysis user-performance-analysis test

setup:
	uv sync

generate-task-table:
	uv run python -m src.python.generate_task_table --start-date "$(START_DATE)" --end-date "$(END_DATE)"

generate-task-intersection-table:
	uv run python -m src.python.generate_task_intersection_table --user-id "$(USER_ID)"

generate-task-sequence-table:
	uv run python -m src.python.generate_task_sequence_table

drop-task-table:
	uv run python -m src.python.drop_task_table

create-causal-diagram:
	mkdir -p "$(dir $(CAUSAL_DIAGRAM_OUTPUT))"
	docker run --rm -v "$(CURDIR):/mermaid" minlag/mermaid-cli -i "/mermaid/$(CAUSAL_DIAGRAM_SOURCE)" -o "/mermaid/$(CAUSAL_DIAGRAM_OUTPUT)" -w 2400 -H 1600

create-task-based-distributions:
	uv run python -m src.python.create_task_based_distributions $(if $(filter 1 true yes,$(REDRAW_ONLY)),--redraw-only,)

create-task-time-bucket-distribution:
	uv run python -m src.python.create_task_time_bucket_distribution $(if $(filter 1 true yes,$(REDRAW_ONLY)),--redraw-only,)

create-task-intersection-duration-distributions:
	uv run python -m src.python.create_task_intersection_duration_distributions $(if $(filter 1 true yes,$(REDRAW_ONLY)),--redraw-only,)

create-part-number-analysis:
	uv run python -m src.python.create_part_number_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

user-performance-analysis:
	uv run python -m src.python.create_user_performance_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

test:
	uv run pytest
