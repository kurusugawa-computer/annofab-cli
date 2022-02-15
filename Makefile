ifndef FORMAT_FILES
	export FORMAT_FILES:=annofabcli tests
endif
ifndef LINT_FILES
	export LINT_FILES:=annofabcli
endif
.PHONY: docs lint test format publish_test publish


init:
	pip install poetry --upgrade
	poetry install

format:
	poetry run autoflake  --in-place --remove-all-unused-imports  --ignore-init-module-imports --recursive ${FORMAT_FILES}
	poetry run black ${FORMAT_FILES}
	poetry run isort ${FORMAT_FILES}


lint:
	poetry run mypy ${LINT_FILES}
	poetry run flake8 ${LINT_FILES}
	poetry run pylint --jobs=0 ${LINT_FILES}

test:
    # 更新の競合が発生する可能性があるので、並列実行しない
	poetry run pytest --cov=annofabcli --cov-report=html tests

publish:
	poetry publish --build

docs:
	cd docs && poetry run make html
