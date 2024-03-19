ifndef SOURCE_FILES
	export SOURCE_FILES:=annofabcli scripts
endif
ifndef TEST_FILES
	export TEST_FILES:=tests
endif
.PHONY: docs lint test format publish_test publish

format:
	poetry run ruff format ${SOURCE_FILES} ${TEST_FILES}
	poetry run ruff check ${SOURCE_FILES} ${TEST_FILES} --fix-only --exit-zero

lint:
	poetry run ruff check ${SOURCE_FILES}
	# テストコードはチェックを緩和する
	# pygrep-hooks, flake8-datetimez, line-too-long, flake8-annotations, unused-noqa
	poetry run ruff check ${TEST_FILES} --ignore PGH,DTZ,E501,ANN,RUF100
	poetry run mypy ${SOURCE_FILES} ${TEST_FILES}
	# テストコードはチェックを緩和するためpylintは実行しない
	poetry run pylint --jobs=0 ${SOURCE_FILES}

test:
    # 更新の競合が発生する可能性があるので、並列実行しない
	# skip対象のmakersを実行しないように"-m"で指定する
	poetry run pytest --cov=${SOURCE_FILES} --cov-report=html ${TEST_FILES} -m "not submitting_job and not depending_on_annotation_specs"

publish:
	poetry publish --build

docs:
	cd docs && poetry run make html
