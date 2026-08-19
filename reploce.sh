#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || ! -d "${1:-}" ]]; then
  echo "Usage: $0 <directory>"
  exit 1
fi
dir="$1"

while IFS= read -r -d '' f; do
  if grep -qF -- '@[[no_warn_unsafe]]' "$f"; then
    # file has the marker → add all four
    {
      head -n 1 "$f"
      printf '@[[no_drop]]\n@[[forced_pointer]]\n@[[forced_unsafe_cast]]\n@[[forced_null_deref]]\n'
      tail -n +2 "$f"
    } > "$f.tmp" && mv "$f.tmp" "$f"
    echo "Updated (full): $f"
  else
    # no marker → add only @[[no_drop]]
    {
      head -n 1 "$f"
      printf '@[[no_drop]]\n'
      tail -n +2 "$f"
    } > "$f.tmp" && mv "$f.tmp" "$f"
    echo "Updated (no_drop only): $f"
  fi
done < <(find "$dir" -type f -print0)
