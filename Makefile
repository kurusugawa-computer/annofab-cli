ifndef SOURCE_FILES
	export SOURCE_FILES:=annofabcli scripts
endif
ifndef TEST_FILES
	export TEST_FILES:=tests
endif
.PHONY: docs lint test format publish_test publish


init:
	pip install poetry --upgrade
	poetry install

format:
	poetry run black ${SOURCE_FILES} ${TEST_FILES}
	poetry run ruff check ${SOURCE_FILES} ${TEST_FILES} --fix-only 
	# isortはruffに置き換えられるはずだが、`F811`が修正されなかったので、ruffが以下のissueに対応されるまではisortも実行する
	# https://github.com/charliermarsh/ruff/issues/3477
	poetry run isort ${SOURCE_FILES} ${TEST_FILES}

lint:
	poetry run ruff ${SOURCE_FILES}
	# テストコードはチェックを緩和する
	# pygrep-hooks, flake8-datetimez, line-too-long
	poetry run ruff check ${TEST_FILES} --ignore PGH,DTZ,E501
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
