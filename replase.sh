#!/usr/bin/env bash
set -euo pipefail
dir="$1"; search="$2"; replace="$3"

export S="$search" R="$replace"
count=0
while IFS= read -r -d '' f; do
  perl -pi -e 'BEGIN{$s=$ENV{S};$r=$ENV{R}} s/\Q$s\E/$r/g' "$f"
  echo "Updated: $f"
  count=$((count+1))
done < <(grep -rlZF -- "$search" "$dir" || true)

echo "Done. Files updated: $count"
