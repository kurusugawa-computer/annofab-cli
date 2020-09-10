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
	poetry run isort --verbose ${FORMAT_FILES}


lint:
	poetry run mypy ${LINT_FILES}
	poetry run flake8 ${LINT_FILES}
	poetry run pylint ${LINT_FILES}

test:
	poetry run pytest -n auto  --cov=annofabcli --cov-report=html tests

publish:
	poetry publish --build

