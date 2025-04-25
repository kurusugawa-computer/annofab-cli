ifndef SOURCE_FILES
	export SOURCE_FILES:=annofabcli scripts
endif
ifndef TEST_FILES
	export TEST_FILES:=tests
endif
.PHONY: docs lint test format publish_test publish

format:
	uv run ruff format ${SOURCE_FILES} ${TEST_FILES}
	uv run ruff check ${SOURCE_FILES} ${TEST_FILES} --fix-only --exit-zero

lint:
	uv run ruff format ${SOURCE_FILES} ${TEST_FILES} --check
	uv run ruff check ${SOURCE_FILES} ${TEST_FILES}
	uv run mypy ${SOURCE_FILES} ${TEST_FILES}
	# テストコードはチェックを緩和するためpylintは実行しない
	uv run pylint --jobs=0 ${SOURCE_FILES}

test:
    # 更新の競合が発生する可能性があるので、並列実行しない
	# skip対象のmakersを実行しないように"-m"で指定する
	uv run pytest --cov=${SOURCE_FILES} --cov-report=html ${TEST_FILES} -m "not submitting_job and not depending_on_annotation_specs"

docs:
	cd docs && uv run make html
