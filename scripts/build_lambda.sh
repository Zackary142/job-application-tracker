#!/usr/bin/env bash
# zips the api + deps into build/lambda.zip
# pulls arm64 linux wheels so it matches lambda even if you build on a mac
set -euo pipefail

cd "$(dirname "$0")/.."
rm -rf build && mkdir -p build/package

pip install \
  --quiet \
  --requirement api/requirements.txt \
  --target build/package \
  --platform manylinux2014_aarch64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all:

cp -r api/app build/package/
(cd build/package && zip -qr ../lambda.zip . -x '*__pycache__*')
echo "Built build/lambda.zip ($(du -h build/lambda.zip | cut -f1))"
