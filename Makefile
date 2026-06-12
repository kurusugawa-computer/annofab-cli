ifndef SOURCE_FILES
	export SOURCE_FILES:=annofabcli scripts
endif
ifndef TEST_FILES
	export TEST_FILES:=tests
endif
GITLEAKS_VERSION := v8.30.1
GITLEAKS_DOCKER_CONFIG ?= /tmp/annofab-cli-docker-config

.PHONY: docs lint test format publish_test publish gitleaks

format:
	uv run ruff format ${SOURCE_FILES} ${TEST_FILES}
	uv run ruff check ${SOURCE_FILES} ${TEST_FILES} --fix-only --exit-zero

lint:
	uv run ruff format ${SOURCE_FILES} ${TEST_FILES} --check
	uv run ruff check ${SOURCE_FILES} ${TEST_FILES}
	uv run mypy ${SOURCE_FILES} ${TEST_FILES}
	$(MAKE) gitleaks

gitleaks:
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks git --redact --verbose .; \
	elif command -v docker >/dev/null 2>&1; then \
		mkdir -p "${GITLEAKS_DOCKER_CONFIG}"; \
		DOCKER_CONFIG="${GITLEAKS_DOCKER_CONFIG}" docker run --rm -v "$$(pwd):/repo" -w /repo ghcr.io/gitleaks/gitleaks:${GITLEAKS_VERSION} git --redact --verbose .; \
	else \
		echo "gitleaksまたはdockerをインストールしてください。" >&2; \
		exit 127; \
	fi

test:
    # 更新の競合が発生する可能性があるので、並列実行しない
	# skip対象のmakersを実行しないように"-m"で指定する
	uv run pytest ${TEST_FILES} -m "not submitting_job and not depending_on_annotation_specs"

docs:
	cd docs && uv run make html
