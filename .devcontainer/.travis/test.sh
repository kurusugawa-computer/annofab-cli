#!/bin/bash
poetry run pytest -n auto -m "not access_webapi"
