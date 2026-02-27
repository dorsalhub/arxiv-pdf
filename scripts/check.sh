#!/bin/sh
# exit immediately if any command fails.
set -e

PYTHON_VERSIONS="3.11 3.12 3.13 3.14"

echo "--- formatting with ruff ---"
uv run --python=3.14 --group dev -- ruff format .

echo "--- linting with ruff ---"
uv run --python=3.14 --group dev -- ruff check .

echo "--- type checking with mypy ---"
uv run --python=3.14 --group dev -- mypy arxiv_pdf

for version in $PYTHON_VERSIONS; do
  echo ""
  echo "--- running tests with pytest on Python $version ---"
  uv run --python="$version" pytest
done

echo ""
echo "--- all checks passed! ---"
