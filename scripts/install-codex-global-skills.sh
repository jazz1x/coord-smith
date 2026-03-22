#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
src="$repo_root/docs/codex-global-skills"
dest="${CODEX_HOME:-$HOME/.codex}/skills"

mkdir -p "$dest"

for skill in \
  ez-ax-autonomous-loop \
  ez-ax-task-slicer \
  ez-ax-validation-picker \
  ez-ax-rag-compactor \
  ez-ax-released-scope-guard
do
  mkdir -p "$dest/$skill"
  cp -R "$src/$skill/." "$dest/$skill/"
done

printf '%s\n' "Installed skills into $dest:"
for skill in \
  ez-ax-autonomous-loop \
  ez-ax-task-slicer \
  ez-ax-validation-picker \
  ez-ax-rag-compactor \
  ez-ax-released-scope-guard
do
  printf ' - %s\n' "$skill"
done
