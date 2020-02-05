ifndef FORMAT_FILES
	export FORMAT_FILES:=annofabcli tests
endif
ifndef LINT_FILES
	export LINT_FILES:=annofabcli
endif
.PHONY: docs lint test format publish_test publish


init:
	pip install pipenv --upgrade
	pipenv install --dev

format:
	pipenv run autoflake  --in-place --remove-all-unused-imports  --ignore-init-module-imports --recursive ${FORMAT_FILES}
	pipenv run black ${FORMAT_FILES}
	pipenv run isort --verbose --recursive ${FORMAT_FILES}


lint:
	pipenv run mypy ${LINT_FILES} --config-file setup.cfg
	pipenv run flake8 ${LINT_FILES}
	pipenv run pylint ${LINT_FILES} --rcfile setup.cfg

test:
	pipenv run pytest -n auto  --cov=annofabcli --cov-report=html tests

publish_test:
	rm -fr dist/
	pipenv run python setup.py check --strict
	pipenv run python setup.py sdist bdist_wheel
	pipenv run twine upload dist/* --repository-url https://test.pypi.org/legacy/ --verbose
	rm -fr dist/

publish:
	rm -fr dist/
	pipenv run python setup.py check --strict
	pipenv run python setup.py sdist bdist_wheel
	pipenv run twine upload dist/* --repository-url https://upload.pypi.org/legacy/ --verbose
	rm -fr dist/

