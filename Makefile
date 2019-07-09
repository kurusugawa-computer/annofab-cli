.PHONY: docs lint test format test publish_test publish

init:
	pip install pipenv --upgrade
	pipenv install --dev

format:
	pipenv run isort --verbose --recursive annofabcli tests
	pipenv run yapf --verbose --in-place --recursive annofabcli tests

lint:
	pipenv run flake8 annofabcli
	pipenv run mypy annofabcli --config-file setup.cfg
	pipenv run pylint annofabcli --rcfile setup.cfg

test:
	pipenv run pytest tests -v --cov=annofabcli --cov-report=html

publish_test:
	rm -fr build/ dist/ annofabcli.egg-info
	pipenv run python setup.py check --strict
	pipenv run python setup.py sdist bdist_wheel
	pipenv run twine upload dist/* --repository-url https://test.pypi.org/legacy/ --verbose
	rm -fr build/ dist/ annofabcli.egg-info

publish:
	rm -fr build/ dist/ annofabcli.egg-info
	pipenv run python setup.py check --strict
	pipenv run python setup.py sdist bdist_wheel
	pipenv run twine upload dist/* --repository-url https://upload.pypi.org/legacy/ --verbose
	rm -fr build/ dist/ annofabcli.egg-info

