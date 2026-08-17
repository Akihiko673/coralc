# Coral Gap Analysis: Projection vs Implementation

_Status: snapshot — generated 2026-08-16. Sections marked `[refreshable]` list the exact commands to re-verify._

This document maps the **projected language** — the textbook (docs/textbook/), plus the
design notes that go with it (attributes.txt, structs.md, otherAllocator.md,
wallvm_backend_notes.md, std_api_reference.md) — against what is **actually implemented and
exercised** (lib/ — 149 `.crl` files, plus the working toolchain). It exists so nobody
re-implements something already built, and so the self-host compiler work targets real code.

**Policy note (2026-08-16):** the Python compiler in py/ is frozen. Features that py/ does not
support will **not** be added to it; anything new is implemented in the self-host (src/) only.

Method: full-lib greps + source reading + toolchain inspection. Every claim carries
`file:line` evidence. Three layers of truth, in descending reliability:

1. **lib/** — the implemented dialect, as actually written.
2. **py/ + run_tests.sh** — the working Coral→C pipeline and its green test suite.
3. **src/ + wallvm** — the in-progress self-host compiler and backend.

The textbook is a projection: some of it is built, some is deliberately absent, some is
aspirational. Nothing in the textbook should be assumed "done" — check lib/ first.

---

## 1. Toolchain reality (what actually works today)

| Component | Status | Evidence |
|---|---|---|
| **py/** Coral→C transpiler | Working. tokenize → parse → flag-resolution → import+alias resolution → monomorphise → emit `.c`/`.h` → gcc | py/main.py:309-375 |
| **Tree-sitter grammar** (ts/) | Green: all lib files parse 0 ERROR/MISSING | TODOs.md:6 |
| **lib/tests/run_tests.sh** | Sections A (5 negative diags), B (parse sweep), C (build main.crl), D (10 runtime tests + lib main smoke), E (wallvm ra_args e2e via gcc+gas **and** nasm+intel) | run_tests.sh:30-132 |
| **Self-host src/** | Front-end only: lexer + LALR(1) generator + expr/stmt parsers. **No pipeline** — main.crl only lexes | my earlier audit (src/main.crl) |
| **wallvm** | 53-opcode static IR, ~20 passes, LSRA, 12 targets. **x86_64 verified end-to-end** (AT&T + Intel); cdecl "parsed but NOT yet functional"; a64 parse-only; Win64 assembles clean | docs/wallvm_backend_notes.md |
| **CLI** | `python3 main.py [-o DIR] [--flags K=V,...] [--cc] [--cflags] [-S] [--keep-c] [-I DIR]`. **No** `--asm`, `--asan`, `--emit-c`, `--debug`, subcommands | py/main.py:378-441 |

No `coral` binary exists. The projected CLI (`coral build --asan`, textbook ch1) is
aspirational; ASan has no backend hooks in any pipeline.

**Test-suite drift** `[refreshable]`: run_tests.sh declares `WANT=129` (line 51) but only
**127** non-`tests/` `.crl` files exist today (149 total). Either two files were removed or
two live under `tests/` — the sweep will fail until `WANT` is reconciled.

### x86_64 backend — verified, with known LSRA issues (wallvm_backend_notes.md, 2026-08-14)

Correctness is green: LSRA-consuming x86_64 backend **ALL PASS** in both syntaxes
(AT&T via gas, Intel via nasm), including runtime-verified `emitCall` arg-staging. Win64
assembles clean. Remaining issues:

**Quality (correct code, inefficient):**
- Register-relay copies: LSRA doesn't coalesce → phi-adjacent values ping-pong
  (`mov %rsi,%rdi; ...; mov %rdi,%rsi`). Harmless noise.
- Float constants rematerialized per use (movabs + slot staging, ~3 instrs) — no const
  pool/rodata yet.
- Float relay `movq %xmm0,%xmm3; movq %xmm3,%xmm0` around float ops (result homes in pool,
  scratch in xmm0).
- Minor: `mov $0,%rcx; cmp %rcx,%rsi; setg` could be `test %rsi,%rsi`.
- No block reordering: jumps to conditionally-fallthrough blocks.

**Verification gaps (correctness risk):**
- **Params never exercised**: `IrFunc.nparams/paramTypes` unused — callee-side param loading
  from arg regs is **unbuilt** in x86_64 (only caller-side arg staging verified).
- **x86 (32-bit) CCs are a latent trap**: `cdecl/stdfastcall` are listed in
  `targetConsumesRegAlloc`/`regallocConfigFor` but the x86 backend is still the OLD slot-based
  one → LSRA assignments not decoded; compiling with `cdecl` today emits WRONG code. Backend
  rewrite (draft in /tmp/opencode/x86_part{1,2}.crl, unverified) required first; notes:
  no sil/dil/bpl/spl in 32-bit, pool = ebx/esi/edi + xmm3-7, push/pop callee-saved in
  prologue, cdecl params at [ebp+8+4i].
- Win64 runtime not verified (assembles only).
- Other backends (arm64/arm/riscv/ppc64/ppc/mips64/mips/sparc64) still slot-based;
  `irCompileAsm` returns null for all non-x64 CCs.
- LSRA valData encoding: bit31=spill, bit30=float, else int pool index; mask 0x3FFFFFFF.

### Flags discipline
All builds pass `--flags=platform=LINUX,ARCH=x86_64,ENDIAN=little` (run_tests.sh:13).
`flag (NAME) { CASE: default: }` blocks with **no value for that flag are a hard error**
(py/main.py:98-107). Idiom: mirroring these three flags into a self-host build system is an
early requirement — and the `@detect` plan (TODOs.md:74) removes the manual step.

---

## 2. Feature matrix: what the dialect actually is

Legend: ✅ used in lib/ · ◐ defined but never used in lib/ · ⛔ lexer/grammar knows, nothing else · ❌ deliberately absent (projected stance) · 🔴 absent, projected as future.

### Base syntax & types — all ✅
Type-first decls; `u8..u64/i8..i64/f32/f64/bool/char` (char 766 uses); `void*`; structs;
`enum` (17); `typedef` (signal.crl:36, wallvm.crl:44); `distinct` (fs.crl:25-26, thread.crl:4);
const-generic `arr<T,N>` (arr.crl:3-25); `sizeof` (36 uses); C-style casts `(T)x` everywhere;
ternary; switch/case/default; for/while/`for(;;)`; `loop {}` (startup_templates.crl:468);
`assert` (~10 uses); `inline` as prefix keyword (t06_inline.crl:1, startup_templates.crl:22);
`asm volatile { ... }` with GCC-style operands (mman.crl:154-167, startup_templates.crl:56).

### Modules — ✅ with a twist
`mod alias = import("...")`, 339 statements. Textbook projects `import("std*")` glob form;
**lib/ never uses globs** — exact paths only:
- `import("std/collections/vec.crl")` (main.crl:1) — root-relative from lib/
- `mod any = import("any");` (cast.crl:1) — sibling short name, `.crl` appended
- `import("manglemod.crl")` (t10_mangling.crl:5) — same-dir relative
- `import("lib/embed/mman.crl")` (embed/bioembed.crl:3) — lib/-prefixed

py/ additionally supports the glob (`import("std*")` walks the directory, py/main.py:265-281)
— implemented but unused. Import resolution searches importing file's dir, then ancestors,
then CWD, then `-I`/`std` (py/main.py:39-67).

### Methods & statics — ✅ but note receiver naming
Methods are declared **inside the struct body** with an explicit receiver param called
`self` in most modules but **`this` in option.crl** (option.crl:35) — the receiver name is a
convention, *not a keyword*. Static constructors via `::`: `vec.vec<u64>::withCap(4)`
(main.crl:5), `option.option<u64>::some(5)` (t04.crl:5), `strView::fromCstr(...)`
(string.crl:43). Dotted-module types: `vec.vec<u64> v`. No `state` param keyword (0 uses).

### Generics — ✅, with an open question on variadic packs
Regular generics: `pub struct vec<T>`, `Result<T,E>`, `T* alloc<T>(u64 count)` (mman.crl:1607),
`T cast<T>(any val)` (cast.crl:3). One test uses a bang on the call: `max!<u64>(3, 7)`
(t09_generic_func.crl:13,31). Packs: `pub void print<T...>(T... args)` (ios.crl:299).

🔴 **Undecided**: compile-time vs runtime packs per TODOs.md:63-64 (`print<T...!args>` is "compile-time (bang)", plain is runtime) — but ios.crl:297 comments the syntax open: *"variadics, say, print<T!...args>(T!... args); ion know"*. Must be settled before self-host monomorphization.

### Compile-time machinery — ✅ in meaty but narrow form
- `flag (...) {}` — 39 blocks, 40 sites: endian.crl:2, mman.crl:149-151 (nested flag-in-flag),
  thread.crl (10 sites), startup_templates.crl, t07_flag.crl.
- `comptime` — exactly 2, both type-dispatch in ios.crl:234 (`if (T == i8) ... return;`) and :508.
  All other `T == Type` comparisons are *inside* comptime blocks.
- `@[no_warn_unsafe]` — 96 occurrences opening modules (file-level, line 1).
- `@[noret]` — 31 uses, all in startup_templates.crl (externs + `_start`/`mainCRTStartup`).
- Graded modifiers: `pub / static / inline / const` as prefixes; `export` still accepted but
  `pub` canonical, cleanup pending (TODOs.md:26).

### Error handling — ◐ Result exists, std doesn't use it
`option<T>` (lowercase) is the workhorse: used by hashmap/cache/map/unordered_map/ini; full
monad kit (map/andThen/orElse/take). `Result<T,E>` (capitalized) is **defined but never
instantiated anywhere in lib/**. Actual std failure patterns: sentinels (`return (File)(-1);`
fs.crl:78), bool+out-param (env.crl:23), null (mman.crl:1609), raw negative i64 EOF
(ios.crl:500), `assert` for programmer errors. No `abort`, no panics, no `fatal` beyond a log
level (log.crl:56).

Why: defer/Result and friends were **not supported by the compilers when lib/ was written**,
so std simply doesn't rely on them. That also keeps std compiles fast — no tracking of
variables across scopes for cleanup. The textbook spells this out in ch06/ch08: the library
performs its frees by hand, deliberately, to avoid the compile-time overhead of RAII-style
tracking.

### Traits & Drop — ❌ nothing anywhere
Zero `trait` uses, zero `defer`, zero drop in all 149 files. Grammar side: `trait Name {...}`
(+TODOs), plain impl blocks ✅ (grammar), **`Type::Trait` impl blocks ⛔** (TODOs.md:12 —
`::` not yet valid in declaration position). Design is firm though: a `Drop` trait; compiler
inlines the drop body at scope exit, once per value, every exit path (textbook 09 + the
resolved decision in src/reason.txt — no destructors, no auto-injection, no
`@[explicit_destructor]`).

### Atomics — ◐ narrow menu (deliberate scope)
Only `AtomicU64`/`AtomicU32` with load/store/fetchAdd/fetchSub/compareExchange
(thread.crl:58,444). No `AtomicUsize`, no fence API in std. The IR is far ahead: full atomic
opcodes incl. fence + ordering enums (ir_opcodes.crl:129-152) — but relaxed ordering is
**excluded by projection** (textbook stance). Weak refs: absent by projection.

### Concurrency — ✅ practical subset
mutex, rwlock, semaphore, condition var, threadpools, POSIX signals (signal.crl). Projected:
no green threads, no async/await, no TLS, no thread_local — reflected in lib/.

### Misc/any — ✅ the documented pair
`pub struct any { void* p; T* as<T>() }` + `pub any wrap(void*)` (any.crl:2-22);
`pub T cast<T>(any val)` (cast.crl:3). Consumed in wallvm (ir_types.crl:763, wasm32.crl:212).
Documented as sections 75/76 of docs/std_api_reference.md.

### Types the language reserves but lib/ never uses — ⛔
`isize`, `usize`, `size_type` (lexer: src/token.crl:39) — 0 uses. `constexpr`/`final` — 0,
explicitly "thinking of adding" (limits.crl:1). (`namespace` is **rejected outright** — see
§5; the py/ parser's DeclNamespace is dead weight, never to be exercised.)

### Layout attributes — ◐ planned, not used
`@packed`, `@reorder`, `@reorder_packed`, `@no_null`, `@[forced_unsafe_cast]`,
`@[forced_null_deref]`, `@[forced_pointer]`: all known to the lexer (src/token.crl:44-49),
**zero uses in lib/**. Layout is done manually, field-order + comments (fs.crl:27-29 `Stat`
note; thread.crl:8 `void* impl[6]` raw-reserve idiom).

**Most attributes are not implemented at all.** Only two are real today: `@[no_warn_unsafe]`
(file-level suppression) and `@[noret]`. Everything else on the attributes.txt list —
`@[throw_error]` (needs comptime), `@no_null` (runtime-enforced, arrives with the wallvm
backend), the forced-* set, `@packed`/`@reorder` family — exists only as design.

---

## 3. Dialect deltas (lib practice vs textbook projection)

These are places where *implemented code* diverges from the *textbook image*. Writing new
textbook chapters against lib/ examples will keep them honest; writing self-host features
against lib/ keeps them testable.

1. **Import style**: textbook shows `mod std = import("std*")`; lib/ uses exact per-file
   paths (see §2 Modules). The glob exists in py/ but no file uses it.
2. **Receiver name**: textbook says `self`; option.crl uses `this`. Neither is a keyword.
3. **Layout control**: textbook projects attribute-driven layout; lib/ does manual field
   order with comments (binary-compat with glibc structs handled by hand).
4. **Error style**: textbook centers Result; lib/ std still uses sentinels/null/bool.
   `Result` unused; `option` lowercase name inconsistent with `Result`'s capitalization.
5. **Exit convention**: `i32 main()` returning codes; startup calls `_teardownAllocator()`
   then `exit(code)` (startup_templates.crl:59-61, 431). No `exit()` in user code.
6. **Bang placement**: lib uses plain `T...`; the `!` pack design (TODOs.md:64) is written
   but the syntax is open (ios.crl:297).
7. **`var` scope**: `var` appears only in pack-iteration `for (var arg : args)` (ios.crl:300)
   — not a general keyword anywhere else.
8. **Function pointers read `Type(Params) name`**, not C-style: `pub void(i32) signal(i32 sig, SigHandler* handler)` (signal.crl:38), `pub typedef PassFn = bool(IrFunc*, void*)` (wallvm.crl:44). The type comes first, the name last, which reads naturally for a value.

---

## 4. Not-yet built (in order of dependency)

1. **Self-host pipeline**: tree-sitter Pass 1-6 (parse→symbols→imports→flag/comptime→typecheck→monomorphise→codegen) is "to be written" (TODOs.md:31-37). Current self-host bugs: `alloc<u8>` segfault (TOK_RANGLE/TOK_GT ordering, TODOs.md:47) and self-compile parse error (TODOs.md:46).
2. **Traits + Drop**: grammar almost there (trait def ✅, impl blocks ✅, `Type::Trait` ⛔); runtime semantics and std adoption entirely absent. Drop inlining needs liveness analysis in wallvm ("defer" is listed External/Awaiting IR transform in wallvm/docs/stdlib_compat.md).
3. **Safety suite**: borrow-check pass exists only as an IR pass (wallvm passes/borrowcheck.crl); std is written for the current unchecked world and will need the `@[forced_*]` attributes added (attributes.txt) so it compiles once safety lands. `@no_null` runtime-enforced comes with the wallvm backend (attributes.txt).
4. **Backend completeness**: wallvm cdecl not functional yet, a64 parse-only; those block non-x86_64 targets (wallvm_backend_notes.md).
5. **Planned features** (from TODOs.md + gen/*/reason.txt): function fusion, struct fusion, `@detect`, `char`→u8 default + overridable, `any` (done in lib, self-host needs the type), clang-grade diagnostics (src/error.crl empty), `--emit-c` header mode with final reordered layout for packed structs, wallvm defaults O1 (borrowcheck + unroll opt-in, `--debug` with gdb-visible symbols).
6. **TLSF**: lib/embed/mman.crl TLSF untested against reference (TODOs.md:40-41).

---

## 5. Deliberate absences (stances, not gaps)

Confirmed by textbook + lib consistency: no exceptions (Result/Option only), no
classes/inheritance/subtyping/virtual/overriding, no operator overloading, no closures, no
default/named args, no tuples, no async/await, no green threads/coroutines, no TLS, no
borrow-checker-for-humans/lifetimes (IR pass only, opt-in), no weak refs, **relaxed atomics
excluded**, **namespaces — rejected** (modules + dotted-type names carry the job), no GC —
the leak a tool can find beats the pause no tool can remove.

---

## 6. Open design questions (need an answer before self-host work)

1. **Pack bang syntax** — settle `T...!name` (TODOs.md:64) vs `T!...name` (ios.crl:297 comment).
2. **`@no_drop` (file-level, decided)** — like `@[forced_pointer]` and `@[no_warn_unsafe]`, it is a
   file-top attribute that turns Drop injection off for the whole file. Std files still
   contain their drop definitions; the attribute just stops the compiler from running
   variable/type tracking for cleanup in those modules, which is what keeps the std compile
   fast. User code that imports those modules gets the auto-drop; the std itself skips the
   tracking. Placement: line 1 of the module file, alongside `@[no_warn_unsafe]`.
3. **`option` vs `Option`** — align capitalization of the two data-class names, or enshrine `option<T>` lowercase.
4. **Receiver name** — pick `self` (majority) and enforce, or treat receiver as any convention.
5. **Import canon** — textbook glob `import("std*")` vs lib exact-path; document which is canonical for user-facing code.
6. **`Result` adoption** — migrate std error paths onto `Result`/`option`, or declare sentinel style canonical (textbook currently implies the former).
7. **Test-suite count** — WANT=129 vs 127 files (run_tests.sh:51).

---

## 7. Regeneration commands `[refreshable]`

```bash
rg -c "@\[no_warn_unsafe\]" lib -g "*.crl" | awk -F: '{s+=$2} END {print s}'   # 96
rg -c "flag \("           lib -g "*.crl" | awk -F: '{s+=$2} END {print s}'   # 39
rg -c "^mod .* = import"  lib -g "*.crl" | awk -F: '{s+=$2} END {print s}'   # 339
rg -n "comptime"          lib -g "*.crl"                                     # ios.crl:234,508
rg -L "trait|defer|\bdrop\b" lib -g "*.crl" | head -1                        # expect the same file list (all files)
find lib -name "*.crl" | wc -l                    # 149
find lib -name "*.crl" -not -path "*/tests/*" | wc -l   # 127 (suite says 129!)
```