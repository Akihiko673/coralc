#!/usr/bin/env bash
@[[no_drop]]
# Ordered test suite for the Coral toolchain.
# Run from anywhere: bash lib/tests/run_tests.sh
# Section A: error diagnostics (negative tests, must FAIL with expected message)
# Section B: whole-lib parse sweep (expect 129)
# Section C: full end-to-end build of lib/main.crl
# Section D: runtime tests in feature order (compile + run, expect exit code)
set -u

PYDIR="$(cd "$(dirname "$0")/../../py" && pwd)"
TESTSDIR="$(cd "$(dirname "$0")" && pwd)"
OUTBASE=/tmp/opencode/testout
FLAGS="--flags=platform=LINUX,ARCH=x86_64,ENDIAN=little"
mkdir -p "$OUTBASE"

PASS=0
FAIL=0
failures=()

check() { # check <desc> <0|1 ok? -1 means "command expected to fail">
  local desc="$1" got="$2" want="$3" extra="${4:-}"
  if [ "$got" = "$want" ]; then
    PASS=$((PASS+1)); echo "  ok   $desc"
  else
    FAIL=$((FAIL+1)); failures+=("$desc: expected $want, got $got $extra")
    echo "  FAIL $desc (got $got $extra)"
  fi
}

echo "A. error diagnostics (must fail with the explained messages)"
DIAGS=(
  "e01_keyword:keyword and cannot be used as a name"
  "e02_missemi:missing its trailing ';'"
  "e03_unterm_string:Unterminated string literal"
  "e04_arity:expects 1 argument(s)"
  "e05_unclosed_generic:expected '>' to close the generic argument list"
)
for entry in "${DIAGS[@]}"; do
  name="${entry%%:*}"; want="${entry#*:}"
  out=$(cd "$PYDIR" && timeout 60 python3 main.py -S $FLAGS -o "$OUTBASE/diag" "$TESTSDIR/errors/$name.crl" 2>&1)
  if echo "$out" | grep -q "Traceback"; then
    check "$name (traceback!)" "traceback" "no-traceback"
  elif echo "$out" | grep -qF "$want"; then
    check "$name (rejected, explained)" "rejected" "rejected"
  else
    check "$name (unexpected output)" "unexpected" "rejected"
  fi
done

echo "B. whole-lib parse sweep (-S), expect all files pass"
WANT=129
rm -rf "$OUTBASE/sweep"
N=$(cd "$TESTSDIR/.." && find . -name "*.crl" | grep -v "/tests/" | while read -r f; do
     grep -q "!return" "$f" 2>/dev/null && continue
     if timeout 120 python3 "$PYDIR/main.py" -S $FLAGS -o "$OUTBASE/sweep" "$f" >/dev/null 2>&1; then
    echo pass
     else
    echo "FAIL $f" >&2
     fi
    done | grep -c pass)
check "parse sweep ($N/$WANT files)" "$N" "$WANT"

echo "C. full build of lib/main.crl"
out=$(cd "$PYDIR" && timeout 240 python3 main.py $FLAGS -o "$OUTBASE/lib_bin" "$TESTSDIR/../main.crl" 2>&1)
if [ -x "$OUTBASE/lib_bin/main" ]; then
  check "build main.crl -> main binary" "built" "built"
else
  check "build main.crl -> main binary" "failed" "built"
  echo "$out" | tail -5
fi

echo "D. runtime tests (compile + run, feature order)"
runtime_expect() { # <name> <file> <expected exit>
  local name="$1" file="$2" want="$3"
  local bin="$OUTBASE/$name/$(basename "$file" .crl)"
  local d="$OUTBASE/$name"
  rm -rf "$d"; mkdir -p "$d"
  if ! (cd "$PYDIR" && timeout 90 python3 main.py $FLAGS -o "$d" "$file" >"$d/build.log" 2>&1); then
    check "$name (build)" "build-failed" "built"
    tail -3 "$d/build.log"
    return
  fi
  "$bin" >/dev/null 2>&1
  local got=$?
  check "$name (exit $got)" "$got" "$want"
}
runtime_expect t01_basics    "$TESTSDIR/t01_basics.crl"    0
runtime_expect t02_vec_generic    "$TESTSDIR/t02_vec.crl"    0
runtime_expect t03_hashmap_nested    "$TESTSDIR/t03_hashmap.crl"    0
runtime_expect t04_option    "$TESTSDIR/t04_option.crl"    0
runtime_expect t05_array_int_arg    "$TESTSDIR/t05_array_int_arg.crl" 0
runtime_expect t06_inline    "$TESTSDIR/t06_inline.crl"    0
runtime_expect t07_flag    "$TESTSDIR/t07_flag.crl"     0
runtime_expect t08_extern    "$TESTSDIR/t08_extern.crl"    0
runtime_expect t09_generic_func     "$TESTSDIR/t09_generic_func.crl"   0
runtime_expect t10_mangling     "$TESTSDIR/t10_mangling.crl"    0
runtime_expect lib_main_smoke    "$TESTSDIR/../main.crl"    1

echo "E. wallvm e2e: emitCall arg-staging (build ra_args, emit asm, harness link+run)"
E_OK=1
{
  d="$OUTBASE/ra_args"
  rm -rf "$d"; mkdir -p "$d/out"
  if (cd "$PYDIR" && timeout 120 python3 main.py $FLAGS -o "$d" "$TESTSDIR/../wallvm/tests/ra_args.crl" >"$d/build.log" 2>&1) \
     && "$d/ra_args" "$d/out" \
     && gcc -x assembler -c "$d/out/ra_args.s" -o "$d/out/ra_args.o" \
     && gcc "$d/out/ra_args.o" "$TESTSDIR/../wallvm/tests/ra_args_harness.c" -o "$d/e2e" \
     && "$d/e2e" >/dev/null 2>&1; then
    E_OK=0
  fi
}
if [ "$E_OK" -eq 0 ]; then
  check "wallvm ra_args e2e (gas, at&t)" "pass" "pass"
else
  check "wallvm ra_args e2e (gas, at&t)" "failed" "pass"
  tail -5 "$OUTBASE/ra_args/build.log" 2>/dev/null
fi
E2_OK=1
{
  if [ -x "$OUTBASE/ra_args/ra_args" ] \
     && "$OUTBASE/ra_args/ra_args" "$OUTBASE/ra_args/out" intel \
     && nasm -f elf64 "$OUTBASE/ra_args/out/ra_args.s" -o "$OUTBASE/ra_args/out/ra_args_i.o" \
     && gcc "$OUTBASE/ra_args/out/ra_args_i.o" "$TESTSDIR/../wallvm/tests/ra_args_harness.c" -o "$OUTBASE/ra_args/e2e_intel" \
     && "$OUTBASE/ra_args/e2e_intel" >/dev/null 2>&1; then
    E2_OK=0
  fi
}
if [ "$E2_OK" -eq 0 ]; then
  check "wallvm ra_args e2e (nasm, intel)" "pass" "pass"
else
  check "wallvm ra_args e2e (nasm, intel)" "failed" "pass"
fi

echo
echo ""
echo "  PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '  %s\n' "${failures[@]}"
  exit 1
fi
echo "  everything green."