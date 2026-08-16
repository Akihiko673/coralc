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

### Cleanup
- [ ] Replace `export` → `pub` across all lib/*.crl files (`_visibility` accepts both, `pub` is canonical)
- [ ] Check `static` in more contexts if lib exercises them
- [ ] Add `grammar.js` to zeditor for Coral syntax highlighting
- [ ] Re-run suite loop when lib grows (reusable: full-suite grep script, `/tmp/r*.crl` regression suite, `/tmp/x*.crl` feature tests, `/tmp/opencode/min3/` repro grammar)

### Compiler Pipeline (ts/src/main.crl — to be written)
- [ ] Pass 1: Parse with Tree-sitter, build symbol table
- [ ] Pass 2: Resolve imports and inline them
- [ ] Pass 3: Resolve `flag()` blocks, evaluate comptime
- [ ] Pass 4: Typecheck all expressions
- [ ] Pass 5: Monomorphize generics
- [ ] Pass 6: Generate C code

### TLSF Allocator (lib/embed/mman.crl)
- [ ] Test TLSF allocator against lib/embed tests (FLI/SLI binning, bitmap search, block split/merge)
- [ ] Cross-check block header layout and O(1) search against Matt Conte reference (otherAllocator.md:19)

## Self-Hosted Compiler (src/main.crl)

### Bugs
- [ ] Fix parse error in coral binary when self-compiling
- [ ] Fix `alloc<u8>` generic function call segfault (TOK_RANGLE/TOK_GT ordering)

### Lexer
- [ ] Comments must be dropped by the lexer — never emitted as tokens. `src/lexer.crl` `skipTrivia()` already skips `//` and `/* */`; keep it that way and verify with a test that no comment text ever reaches the parser/AST (the ts Pass 1 must likewise drop `comment` nodes from the tree)

### Diagnostics (src/error.crl — currently empty)
- [ ] Implement clang-grade error/warning reporting in `src/error.crl`: `file:row:col`, the offending source line with a caret, error/warning codes, notes and fix-it hints, warning categories (with `-W`-style on/off), suppression via `@[no_warn_*]`, and recovery so multiple errors are reported per run — not just "expected this, got that" (src/parser.crl:17)
- [ ] Track error/warning counts; exit non-zero only on errors, warn-only runs stay green

### Features
- [ ] Implement `flag` keyword parsing and codegen
- [ ] Implement direct `for (var i <= len; i++)` syntax
- [ ] Implement chained method calls
- [ ] Implement generic monomorphization
- [ ] Implement comptime evaluation

### Generic variadics: compile-time vs runtime (`!`)
- [ ] Separate runtime and compile-time generic variadics with a bang: `print<T...!args>(T...! args)` is compile-time (bang), plain `T...args` is runtime — lexer/punctuation, parser, typechecker, monomorphizer, and codegen must honor the distinction (compile-time packs are unrolled/constant-folded; runtime packs lower to C varargs)

### Imports, mangling, nested generics
- [ ] Import handling in the self-host: resolve `import("...")`, inline imported declarations, module aliases (`mod x = import(...)`), cycle detection, and apply the module-prefix mangling
- [ ] Mangling must be inherited: the self-host must produce exactly the same names as the ts codegen scheme in `ts/codegen.md` (`P_` module prefix, `P_f`, `P_S_m`, `S_A_m`, `P_E_V`, mono suffix) so C emitted by either pipeline links together
- [ ] Nested generics: `Foo<Bar<u8>, Vec<u32>>` (and nested in type params/method receivers) must parse, resolve, monomorphize, and mangle correctly

### Design notes from src/ comments and reason.txt
- [ ] Function fusion: detect functions with 1-1 identical bodies operating on exactly the same types and fuse them into a single named function across modules (src/reason.txt, src/parser.crl:4) — e.g. one `print` instead of `std.print` + `ios.print` copies
- [ ] Struct fusion: the same struct reachable via different import aliases (`std.String`, `str.String`, `string.string`) must fuse into one type
- [ ] `@detect` flag option in the self-host: detect arch + platform at compile time via the FP-signature mathematics in src/platform.crl, usable as the value of the default flags so the user needn't specify it manually
- [ ] `char` should be `u8` by default but overridable; add an `any` type that is a `void*` under the hood
- [ ] All attributes implemented and used; add `constexpr`/`final` for compile-time constants
- [ ] Full analysis: typechecking, semantic checks, static-if where possible, and variable stacking for `defer`
- [ ] Design question (open): destructors on scope exit automatically, vs a `@builtin_destructor.crl` of destructor declarations per std/lib type auto-injected unless `@[explicit_destructor]`
- [ ] C backend (`src/gen/c/reason.txt`): `--emit-c` mode emits a C header with the equivalent type definitions and function declarations (resolved names), NO function bodies — for linking C against Coral code
- [ ] In `--emit-c` mode, packed or reordered structs must be emitted with their final reordered layout (field order as the compiler laid it out in memory, `__attribute__((packed))` where applicable) so the C struct's layout is binary-compatible with Coral's
- [ ] VM backend (`src/gen/vm/reason.txt`): wallvm as backend; borrow-checking and loop unrolling opt-in, NOT default; optimization level O1 by default; O0 only removes unreachable/dead code; `--debug` flag emits debug info (line numbers, variable names) visible in assembly, object, and final exe so gdb can debug

- [ ] All 15 tests pass
