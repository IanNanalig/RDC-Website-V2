#!/usr/bin/env bash
# Optimize images in place (use from repo root).
# Requires: `npm i -g imagemin-cli imagemin-mozjpeg imagemin-pngquant` OR run via npx.

set -euo pipefail

SRC_DIR=${1:-src/assets}
echo "Optimizing images under $SRC_DIR"

# JPG and JPEG
npx imagemin "$SRC_DIR/**/*.{jpg,jpeg}" --plugin=imagemin-mozjpeg@latest --out-dir="$SRC_DIR"

# PNG
npx imagemin "$SRC_DIR/**/*.png" --plugin=imagemin-pngquant@latest --out-dir="$SRC_DIR"

echo "Image optimization complete. Review changes and commit the updated files." 
