#!/usr/bin/env bash
# Optimize PDFs in place using Ghostscript. Requires `gs` installed.

set -euo pipefail

SRC_DIR=${1:-frontend/src/assets/Documents}
OUT_DIR=${2:-frontend/dist/assets/optimized_pdfs}
mkdir -p "$OUT_DIR"

for f in "$SRC_DIR"/*.pdf; do
  [ -e "$f" ] || continue
  bn=$(basename "$f")
  echo "Optimizing $bn"
  gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook \
    -dNOPAUSE -dQUIET -dBATCH -sOutputFile="$OUT_DIR/$bn" "$f"
done

echo "PDF optimization complete. Optimized files in $OUT_DIR" 
