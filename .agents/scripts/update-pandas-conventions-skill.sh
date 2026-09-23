#!/usr/bin/env bash
set -euo pipefail

readonly repository_url="https://github.com/yuji38kwmt/codex-skills.git"
readonly source_path="skills/pandas-conventions"
readonly destination_path="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)/.agents/skills/pandas-conventions"

temporary_directory=$(mktemp -d)
trap 'rm -rf "$temporary_directory"' EXIT

git clone --depth 1 --filter=blob:none --sparse "$repository_url" "$temporary_directory"
git -C "$temporary_directory" sparse-checkout set "$source_path"

rsync --archive --delete \
    "$temporary_directory/$source_path/" \
    "$destination_path/"

echo "Updated $destination_path from $repository_url"
