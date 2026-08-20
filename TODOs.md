# TODO

## Grammar / Tree-sitter Compiler (ts/)

### Status: Full suite green
- [x] All 117 `lib/**/*.crl` files parse with 0 ERROR/MISSING nodes
- [x] Verify all files parse correctly with the new syntax
- [x] Re-verify `lib/embed/mman.crl` (975 lines w/ TLSF) parses cleanly after conflict revert

### Missing Syntax Features (from otherAllocator.md design notes)
- [x] **Trait definitions**: `trait Name { retType method(params); ... }` — trait is the contract/interface; NOT in grammar yet (no `trait` keyword). Design reference: otherAllocator.md line 117
- [ ] **Trait implementation blocks**: `Type::Trait { retType method(params) { ... } }` — trait impl for a type; NOT in grammar yet (`::` is currently only valid in expressions, not declaration position). Design reference: otherAllocator.md line 129
- [x] **Impl blocks**: `Type { retType method(params) { ... } }` — plain method blocks, no keyword needed; IS in grammar (`impl_block`), verified working. Design reference: otherAllocator.md line 151
- [x] **C-style variadic parameters**: `(const char* fmt, ...)` — externs and regular functions, `, ...` after params
- [x] **Generic variadics**: `T...` — in `type_parameter` and `parameter`
- [x] **Compound literals**: `(Type){ .field = v, ... }` and bare `{ ... }` initializers
- [x] **Cast expressions in all contexts**: `(u8*)ptr`, `(const char*)`, `(volatile u8*)`, bare type-values `(Type)` in comparisons; optional operand + const/volatile variants

### Bugs (all resolved)
- [x] **Statement-start generic calls** (`foo<u64>(10);`) — LALR merge dropped `(` continuation after `>`; unified `_generic_type_args` + conflict
- [x] **For-loop relational condition**: `for (u64 i = 0; i < 10; i++)` — same root cause, fixed
- [x] **3 failing files (GLR state explosion)**: `std/io/ios.crl`, `wallvm/ir_types.crl`, `wallvm/rules/asm_rules.crl` — root cause was parse-table defect (not `[$.named_type, $.primary]`); all pass now
- [x] `if`/`while` missing parens around condition; `const char* x;` const vars; `UL` integer suffixes; multi-name/multi-bracket decls; range-for; macro calls `name!(...)`; `extern("c")` + `!return`; `flag default:` bodies; `asm volatile`; typed const type-params `StaticPool<T, u64 N>`; `::`-types (`NoretBare::void`)

### Compiler Pipeline (ts/src/main.crl — to be written)
> Superseded by the self-hosted pipeline (`src/main.crl` + `src/typecheck/`); kept for reference. All six passes land in the self-host in the order below (parse green, typecheck in progress).

## Self-Hosted Compiler (src/main.crl)

### Bugs
- [x] Fix parse error in coral binary when self-compiling — resolved by the parser fixes; corpus green: 147/147 lib files parse, self-host builds round-trip via py
- [x] Fix `alloc<u8>` generic function call segfault (TOK_RANGLE/TOK_GT ordering) — lexer now emits `>` / `>>` (T_GT / T_SHR) with no RANGLE; generic calls (`mman.alloc<u8>`, `vec::new`, `StaticPool<T, u64 N>`) parse cleanly in every corpus file

### Handwritten LALR grammar gaps (src/stmt_parser.crl)
- [x] **File-level attributes**: `@[no_warn_unsafe]` / `@[forced_*]` are *file-level* attributes
  (attached to the whole file, e.g. first line of `lib/std/collections/arr.crl` and
  `lib/embed/mman.crl`), not decl attributes. **Root cause found & fixed** (2026-08-18):
  not a lookahead-propagation bug — the generator is provably correct (differential check
  against a reference canonical-LR(1) implementation: all 342 states, items, and LA sets
  match exactly). It was a shift/reduce conflict at the file start: `PREF -> ε` (prec 3)
  beat the attr-token shift (termPrec was `PREC_ES + 1` = 2) on `@[...]`, so the parser
  committed to the PREF path (struct/enum/... attrs) whose follow set has no `mod`/`pub`.
  Fixed by raising `termPrec[ATTRTOKS]` to `PREC_TYPEKW` (4) in stmtGrammar, so the shift
  into `MODULE -> ATTRS mod IDENT = import(...) ;` wins at the file start.
  The `-g` flag (permanent debug feature, like `-t`) dumps grammar + canonical/LALR states
  + actions; `py` reference generator kept at /tmp/opencode/refgen.py (untracked, scratch).
- [x] Revisit remaining attr patterns after the fix: attr followed by `pub`/`extern` decls
  (e.g. `lib/std/platform/libc.crl` style) — corpus sweeps (147/147) show no stragglers;
  file-level attrs are now also captured on `ast.Program.fattrs` for the checker.
- [ ] **Resolution path** (if further attr gaps remain): record the failing case here and fix
  in a future `src2` that ports the TS-generated grammar and `parser.c` (tree-sitter `ts/`
  suite already parses all `lib/**/*.crl` cleanly) rather than hand-patching the handwritten
  LALR further.

### Lexer
- [x] Comments must be dropped by the lexer — never emitted as tokens. `src/lexer.crl` `skipTrivia()` already skips `//` and `/* */`; keep it that way and verify with a test that no comment text ever reaches the parser/AST (the ts Pass 1 must likewise drop `comment` nodes from the tree)

### Diagnostics (src/error.crl — currently empty)
- [ ] Implement clang-grade error/warning reporting in `src/error.crl`: `file:row:col`, the offending source line with a caret, error/warning codes, notes and fix-it hints, warning categories (with `-W`-style on/off), suppression via `@[no_warn_*]`, and recovery so multiple errors are reported per run — not just "expected this, got that" (src/parser.crl:17)
- [ ] **Real error messages, not "expected X, got ident"**: each diagnostic must name the actual problem in context (`cannot call non-fn value`, `field 'x' has no member 'y'`, `incompatible types: 'Foo' vs 'Bar'`), include the offending expression, and where possible suggest the fix (`did you mean 'push'?`). The "expected X, got Y" shape is only acceptable for pure token-position mismatches in the parser; semantic errors from the checker must be phrased like rustc/clang, not like a tokenizer. Follow the published conventions (rustc-dev-guide "Errors and lints", clang "Diagnostics", PyPy-style catalog roundup): plain simple English; messages start lowercase, no trailing punctuation; the word "illegal" is banned (use "invalid"); concise headline + `note:`/`help:` lines with secondary spans; reduce spans to the smallest extent that still shows the issue; never emit the same error twice for one root cause.
- [ ] **Full diagnostic catalog** — one bespoke message per failure kind, no generic fallback that repeats: enumerate every place the compiler can fail (unresolved name, mis-typed call, arity mismatch, missing/wrong `mod` path, trait-impl mismatch, generics bound failure, drop-while-escape, borrow conflict, NaN/undef findings, type-inference deadlock, unreachable `=`, unclosed delim at EOF …) and give each its own message with the offending code quoted. Reference the rustc error-code model (`E####` + `--explain`-style long description) and the Elm "error message catalog" approach (each error has a unique title + explanation). The goal: no two distinct problems ever print the same text.
- [ ] **ANSI colour in diagnostic output** (term.crl palette has 16 colours: 30–37 + bright 90–97): colour-code error vs warning vs info vs note labels (`error:` red-bold, `warning:` yellow, `info:` cyan, `note:` magenta, per `error.crl` LVL_*). IDE-style token colouring inside the rendered source line and caret block, applied only when stderr is a TTY, modelled on VS Code Dark+:
  - keywords (`pub`, `mod`, `if`, `for`, `flag`, `cast`, `sizeof` …): bright blue (94)
  - **type names** (resolved against checker scope/knows-type set): yellow (93)
  - **function names** (callee positions + known fns in scope): bright cyan (96)
  - variable/parameter names: plain white (37) or brightWhite (97) for `self`/`this`
  - numeric literals: bright green (92); string literals: green (32); char literals: bright magenta (95)
  - operators (`+`, `*`, `==`, `->`, `?`, `=` …): cyan (36) or plain
  - brackets/parens/braces `[` `(` `{` and their closing matches: green (32), with the matched close of the span in question bolded
  - comments: brightBlack (90), dim; unused/error-underlined tokens: red underline (4;31)
  - the caret/underline of the error position: red-bold (1;31)
  Add a `--no-color` escape hatch and env `NO_COLOR`/`CLICOLOR_FORCE` handling.
- [ ] Track error/warning counts; exit non-zero only on errors, warn-only runs stay green

### Features
- [x] `-g` grammar dump flag (permanent, like `-t`): dumps productions + canonical/LALR
  states with item lookaheads + live-state action table + live→canonical state mapping,
  for debugging the handwritten LALR generator / diffing against a reference generator
- [x] Implement `flag` keyword parsing (case labels, `default:`, label lookahead, extern/decl bodies) — codegen lands with the self-host C backend (see C/VM backend items below)
- [ ] Implement direct `for (var i <= len; i++)` syntax
- [ ] Implement range based `for (var i : &len)` syntax
- [ ] Implement chained method calls
- [ ] Implement generic monomorphization
- [ ] Implement comptime evaluation

### Generic variadics: compile-time vs runtime (`!`)
- [ ] Separate runtime and compile-time generic variadics with a bang: `print<T...!args>(T...! args)` is compile-time (bang), plain `T...args` is runtime — lexer/punctuation, parser, typechecker, monomorphizer, and codegen must honor the distinction (compile-time packs are unrolled/constant-folded; runtime packs lower to C varargs)

### Imports, mangling, nested generics
- [ ] Import handling in the self-host: resolve `import("...")`, inline imported declarations, module aliases (`mod x = import(...)`), cycle detection, and apply the module-prefix mangling
- [ ] Mangling must be inherited: the self-host must produce exactly the same names as the ts codegen scheme in `ts/codegen.md`  with a minor change (`_P__` module prefix, `_P__f`, `_P__S__m`, `_S__A__m`, `_P__E__V`, mono suffix) so C emitted by either pipeline links together
- [ ] Nested generics: `Foo<Bar<u8>, Vec<u32>>` (and nested in type params/method receivers) must parse, resolve, monomorphize, and mangle correctly

### Design notes from src/ comments and reason.txt
- [ ] Function fusion: detect functions with 1-1 identical bodies operating on exactly the same types and fuse them into a single named function across modules (src/reason.txt, src/parser.crl:4) — e.g. one `print` instead of `std.print` + `ios.print` copies.
- [ ] Struct fusion: the same struct reachable via different import aliases (`std.String`, `str.String`, `string.string`) must fuse into one type
- [ ] `@detect` flag option in the self-host: detect arch + platform at compile time via the FP-signature mathematics in src/platform.crl, usable as the value of the default flags so the user needn't specify it manually
- [ ] `char` should be `u8` by default but overridable; add an `any` type that is a `void*` under the hood
- [ ] All attributes implemented and used; add `constexpr` for compile-time constants
- [ ] Full analysis: typechecking, semantic checks, static-if where possible, and variable stacking for `defer`
- [ ] C backend (`src/gen/c/reason.txt`): `--emit-c` mode emits a C header with the equivalent type definitions and function declarations (resolved names), NO function bodies — for linking C against Coral code
- [ ] In `--emit-c` mode, packed or reordered structs must be emitted with their final reordered layout (field order as the compiler laid it out in memory, `__attribute__((packed))` where applicable) so the C struct's layout is binary-compatible with Coral's
- [ ] VM backend (`src/gen/vm/reason.txt`): wallvm as backend; borrow-checking and loop unrolling opt-in, NOT default; optimization level O1 by default; O0 only removes unreachable/dead code; `--debug` flag emits debug info (line numbers, variable names) visible in assembly, object, and final exe so gdb can debug

- [ ] All 15 tests pass