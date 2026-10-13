START_DATE ?= 2026-02-01
END_DATE ?= 2026-08-01
USER_ID ?= 319402689
REDRAW_ONLY ?= 0
REDRAW ?= 0
CAUSAL_DIAGRAM_SOURCE ?= src/mermaid/DUR.mmd
CAUSAL_DIAGRAM_OUTPUT ?= outputs/charts/DUR_detailed.png
TASK_GROUPING_ANALYSIS_MD := task_grouping_analysis/progress.md
TASK_GROUPING_ANALYSIS_LATEX := src/latex/task_grouping_analysis.latex
TASK_GROUPING_ANALYSIS_PDF := outputs/reports/pdf/task_grouping_analysis.pdf

.PHONY: setup generate-task-table generate-task-intersection-table generate-task-sequence-table drop-task-table generate-valid-dur-task-table drop-valid-dur-task-table create-causal-diagram create-task-based-distributions create-task-time-bucket-distribution create-task-intersection-duration-distributions create-part-number-analysis create-mc3-analysis create-purchase-brand-analysis create-initiation-channel-analysis create-prescription-source-analysis create-approval-channel-analysis create-pettype-analysis create-npet-conditions-analysis create-ncorrection-fields-analysis create-prior-approved-rx-analysis create-prior-approved-non-vet-diet-rx-analysis create-correction-field-analysis create-mc3-pettype-analysis create-mc3-coh-pettype-final-model create-santhosh-analysis create-santhosh-analysis-one-sided create-santhosh-analysis-user create-santhosh-analysis-user-one-sided estimate-differences-reml user-performance-analysis create-task-grouping-analysis test

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

generate-valid-dur-task-table:
	uv run python -m src.python.generate_valid_dur_task_table --start-date "$(START_DATE)" --end-date "$(END_DATE)"

drop-valid-dur-task-table:
	uv run python -m src.python.drop_valid_dur_task_table

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

create-mc3-analysis:
	uv run python -m src.python.create_mc3_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-purchase-brand-analysis:
	uv run python -m src.python.create_purchase_brand_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-initiation-channel-analysis:
	uv run python -m src.python.create_initiation_channel_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-prescription-source-analysis:
	uv run python -m src.python.create_prescription_source_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-approval-channel-analysis:
	uv run python -m src.python.create_approval_channel_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-pettype-analysis:
	uv run python -m src.python.create_pettype_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-npet-conditions-analysis:
	uv run python -m src.python.create_npet_conditions_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-ncorrection-fields-analysis:
	uv run python -m src.python.create_ncorrection_fields_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-prior-approved-rx-analysis:
	uv run python -m src.python.create_prior_approved_rx_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-prior-approved-non-vet-diet-rx-analysis:
	uv run python -m src.python.create_prior_approved_non_vet_diet_rx_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-correction-field-analysis:
	uv run python -m src.python.create_correction_field_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-mc3-pettype-analysis:
	uv run python -m src.python.create_mc3_pettype_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-mc3-coh-pettype-final-model:
	uv run python -m src.python.fit_mc3_coh_pettype_final_model $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-santhosh-analysis:
	uv run python -m src.python.santhosh_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-santhosh-analysis-one-sided:
	uv run python -m src.python.santhosh_analysis --one-sided $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-santhosh-analysis-user:
	uv run python -m src.python.santhosh_analysis_user $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-santhosh-analysis-user-one-sided:
	uv run python -m src.python.santhosh_analysis_user --one-sided $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

estimate-differences-reml:
	uv run python -m src.python.estimating_differences_using_reml $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

user-performance-analysis:
	uv run python -m src.python.create_user_performance_analysis $(if $(filter 1 true yes,$(REDRAW)),--redraw-only,)

create-task-grouping-analysis: $(TASK_GROUPING_ANALYSIS_PDF)

$(TASK_GROUPING_ANALYSIS_LATEX): $(TASK_GROUPING_ANALYSIS_MD) src/latex/task_grouping_analysis.lua src/latex/task_grouping_analysis_header.tex
	pandoc "$<" --from=gfm+tex_math_dollars --to=latex --standalone --lua-filter=src/latex/task_grouping_analysis.lua --include-in-header=src/latex/task_grouping_analysis_header.tex -V geometry:margin=0.7in -o "$@"

$(TASK_GROUPING_ANALYSIS_PDF): $(TASK_GROUPING_ANALYSIS_LATEX)
	mkdir -p build/task-grouping-analysis "$(dir $@)"
	latexmk -xelatex -interaction=nonstopmode -halt-on-error -file-line-error -outdir=build/task-grouping-analysis "$(TASK_GROUPING_ANALYSIS_LATEX)"
	cp build/task-grouping-analysis/task_grouping_analysis.pdf "$@"

test:
	uv run pytest
