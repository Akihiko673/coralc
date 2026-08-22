# HANDOFF — Coral selfhost compiler (coralc → WallVM IR)

Pass this document to any model/engineer continuing the session. It contains full
context, verified state, repro cases, and the remaining task list.

---

## 1. Project context

- Repo: `/home/cerie/Projects/coral`. The compiler is written in its own language
  (**Coral**, files `.crl`) and bootstraps through a C build (`./build` produces
  `./coralc`).
- Pipeline: `src/lexer.crl` → `src/parser.crl` → `src/typecheck/{check,expr}.crl`
  → `src/codegen/emitir.crl` (WallVM IR, `.wir` text output).
- Run: `./coralc <file>.crl --emit-ir -O0` writes `<file>.wir`.
- **lib2 is the live runtime** (`import("std/...")`, wallvm IR types). `lib/` is
  LEGACY — do not fix things there, do not use it as reference for what coralc
  accepts. `src/` must never import `lib2/`.

### Language rules established by the user (NON-NEGOTIABLE)

1. Attributes:
   - Declaration level: `[[attr]]` or comma list `[[reorder, packed]]`. DOUBLE
     brackets, no `@`.
   - Module/file level: `@[[ATTR]]` (double bracket after `@`). This is the ONLY
     valid `@` form.
   - `@[name]` (single bracket) and bare `@name` are **forbidden**. The LEXER must
     reject them (implemented, see §3).
   - There is NO `[[reorder_packed]]` token. Combined mode is `[[reorder, packed]]`
     (both attrs recorded; layoutMode 3).
2. Arrays: 2D arrays supported as `T[N][M]` where the FIRST size is outermost:
   `i32[2][3]` is 2 outer arrays of 3 `i32` (col-major thinking as C). Parser
   collects sizes then wraps in reverse so `i32[2][3]` → `array(array(i32,3),2)`.
   Code at `src/parser.crl:parseType` handles `while([)` loop with `arrSizes[16]`.
   Check `m[1][2]` for `i32[2][3]` is valid; `m[1][2]` with inner 2 would error.
3. Functions: ANY `FOO main()` where `FOO` is not a known primitive/struct (e.g.
   `loo`, `fn`, `xyz`, `int`) is **rejected** via `TC-TYPE "unknown return type
   'FOO'"` in `src/typecheck/expr.crl:typeFunction`. Previously fell through as
   `TY_UNKNOWN` → mapped to `i64`. Also `i32 foo(){}` with no return now emits
   `TC-RETURN "non-void function 'foo' must return a value of type 'i32'"`.
4. Struct layout modes: `[[reorder]]` (sort fields by align/size desc, natural
   padding), `[[packed]]` (no padding), `[[reorder, packed]]` (sorted + tight).
   Parsed in `src/parser.crl` `parseStructDecl` (~line 3170) via
   `self.hasAttr("reorder")` / `hasAttr("packed")` → `d->layoutMode` 1/2/3;
   offsets computed in `src/codegen/emitir.crl` (`structFieldOffset`).
5. Inline asm: `asm [volatile] [inline] { ... }`. Body is ordinary tokens — the
   template MUST be a string literal. Extended GCC style works:
   `asm volatile { "tmpl" : "=a"(out) : "d"(in) : "cc", "memory" }`.
   Parens `asm(...)` are NOT grammar. Do not add raw-text lexer modes.
6. Diagnostics format lives entirely in `src/error.crl` (`diag`):
   ```
   error[CODE]: <summary>
     ┌─► file:line:col
     │
     │  NN │ source line
     │     ▲
     │     ╰─ help text        <- only rendered if help non-empty
   ```
   Entry points: `diag`, `reportCode`, `reportLevel`, `report`. ANSI colors built
   with raw ESC byte (27) + suffix strings because the bootstrap C compiler must
   accept the literals (no `\x` escapes in Coral string literals).

---

## 2. What was completed this session (verified working)

1. **Lexer rejects bad attr forms** — `src/lexer.crl` `scanPunct()` (~line 438):
   when matching `"@"` (len==1 op), if next two chars are not `[` `[`, emits
   `LEX-0007 "invalid attribute syntax"` with help "attributes are [[attr]] on
   declarations or @[[ATTR]] at module level", advances 1 char, returns.
   - `@[reorder]` → LEX-0007 ✓
   - `@noret` → LEX-0007 ✓
   - `@[[no_warn_unsafe]]` → accepted ✓
   - `lib2/` was grepped: zero `@[` or bare-`@` usages remain, nothing broke.
2. **Parser struct attrs** — `parseStructDecl`: `isReorder`/`isPacked` via
   `hasAttr`; both → mode 3; reorder → 1; packed → 2; else 0.
   `parseAttachedAttrs()` records comma-separated names inside `[[...]]`, so
   `[[reorder, packed]]` works. Verified sorted offsets d@0 b@8 a@12.
3. **Inline asm lowering** — `genAsm` in `src/codegen/emitir.crl`:
   - parses `s->text` captured by `parseAsmStmt` (parser.crl ~1706, braces form);
   - splits template/output/input/clobber sections on `:` outside quotes;
   - constraint strings parsed from `"=a"(expr)` pairs; MAXOP 16; constraint
     storage is FLAT char arrays `char outConstr[192]` indexed `k*12+q`
     (Coral parser does not accept 2D local arrays);
   - operand expressions are parsed by re-running the real lexer+parser on the
     snippet (`parseExprSnippet` using `lex.Lexer` + `parse.Parser`);
   - outputs bound to allocas via `findLocal`; inputs evaluated with `genExpr`;
   - emits `fg.bd.inlineAsm(...)`; appends `# clobber:` comment line to template;
   - first `=a`/`=r` output stored back to its local slot.
   - Verified: `asm { "movq $3, %%rax\n\t" }` → `inlineasm void [...]`;
     extended form with clobbers → `inlineasm i64 ["...", %3, %9, %10]` +
     `store [%12, %3]`.
4. Build is green (`./build` no errors).

---

## 3. VERIFIED GAPS — FIXED THIS SESSION

### G1. `fn` / `loo` / any unknown return type — FIXED
Now correctly emits `TC-TYPE "unknown return type 'fn'"` from
`src/typecheck/expr.crl:typeFunction`. All `FOO main()` cases (fn, loo, xyz,
loin, int) now error. Helped added: "declare it or use a primitive like i32…".
`new.crl` fixed: `int main` → `i32 main`, `loin` cases would now error.

### G2. Non-void function with no return — FIXED
Now emits `TC-RETURN "non-void function 'foo' must return a value of type
'i32'"` with help "add a return statement on every path, or change the return
type to void" (check in `typeFunction` after `typeStmt`).

### G2b. 2D arrays — FIXED
`i32[2][3]` now parses correctly. Same for `T[N][M]` on vars/params/fields.
Parser fix in `src/parser.crl:parseType` collects `arrSizes[16]` then wraps
in reverse so `i32[2][3]` → outer 2 inner 3 (C semantics).

### G2c. Extern IR — FIXED
`extern("C") T name(...)` now emitted as `extern func name -> T {}` with
`isExtern=true` and `externLib` set, so `dumpIR` prints `extern func @name`
and wallvm assembly backends emit `.globl`. Previously skipped (`DT_EXTERN`
filtered out at `buildModule:1366`).

### G3. Empty help lines — FIXED (typecheck/expr.crl)
41 `str.strView::empty()` help args replaced with per-code helps
(TC-RESOLVE → "declare it…", TC-RETURN → "make the return type…", etc.).
Remaining gaps: `src/typecheck/check.crl` still has some TC-RESOLVE sites with
empty helps (flag handling) — low priority.

### G4 (was) — new.crl/new.wir truncation — FIXED
Flag bodies (platform=LINUX, ARCH=x86_64) now work. Root cause was
`flagValueEmit` with `nflags==0` in `emitir.crl` — added fallback defaults
(LINUX/x86_64) and case-insensitive compare. `new.wir` now correct at -O0..-O3
(verified 2 funcs, 1 inlineasm, full _mmap syscall, correct `call` args).

### G3. Empty help lines everywhere in typecheck
Dozens of `errAt(..., str.strView::empty())` / `errTwoStr(..., "", ...)` calls in
`src/typecheck/expr.crl` (~40 sites: TC-ARGS 277/301, TC-MEMBER 692,
TC-RESOLVE 781, TC-INDEX 805, TC-ARITH 890/1149/1151/1163/1191, TC-COND
899/951/1100/1102/1729, TC-EXPR 816/1315/1328/1341/1655/1671/1689/1630,
TC-SWITCH 1751, TC-UNUSED 1372, TC-REDECL 1386, TC-ASSIGN 1596, TC-RETURN
1615/1620, TC-ENUM 1247, TC-STRUCT 1264/1303/1311/1337, duplicate-self 1929) and
in `check.crl`. Every one needs a concrete one-line help string (what caused it +
how to fix). The user explicitly rejected "decent" — make each message specific
(include the offending names/types, which most already interpolate) and every
help actionable.

### G4. User-reported: "unresolved" errors + empty text — PARTIALLY FIXED
41 helps filled; TC-TYPE/TC-RETURN now have messages. Remaining: a few
`check.crl` flag TC-RESOLVE sites still have empty middle strings, and any
`opaqueType` fallback that never got a diagnostic (e.g. `X.y` where X is an
unknown module) still silently becomes TY_UNKNOWN then later "unresolved" —
next model should finish the sweep (see §5).

### G5. Dead parser code after lexer change — STILL PENDING
`skipFileAttrs` dead branch for `@[`/`@name` was fixed at the lexer (now
unreachable); `parseAttachedAttrs` second loop for `@[[` still present but
needed for attached module attrs (kept). No further stripping required unless
lexer is audited.

### G6. error.crl caret alignment — STILL PENDING (low priority)
`caretSpaces = prefixLen + col - 4` counts BYTE columns. Tabs or multi-byte
UTF-8 before the error column will misalign the `▲`. Fix by clamping or
tab-expanding the extracted line before render.

---

## 4. Remaining task list (priority order)

| # | Task | Where | Status |
|---|------|-------|--------|
| 1 | G1+G2 fixes verified (TC-TYPE, missing return, 2D arrays, extern, new.wir flags) — see G1-G3 above | typecheck/expr.crl, parser.crl, codegen/emitir.crl | **DONE** |
| 2 | Finish empty-help sweep in `check.crl` + any remaining `expr.crl` opaque paths | check.crl, expr.crl | TODO |
| 3 | Sweep silent glosses: parser `advance()` past garbage, `opaqueType` without diagnostic, emitir null-guards | parser.crl, typecheck/*, emitir.crl | TODO |
| 4 | G5/G6 polish (dead branches, caret alignment) | parser.crl, error.crl | TODO |
| 5 | Regression pass: all §3 repros + `lib2/wallvm/tests/ra_smoke.crl` + `new.wir` -O0..-O3 + full build | — | TODO |

## 5. Style constraints for edits

- Coral quirks: 2D local arrays NOW supported (`T[N][M]`), but older bootstrap
  code flattens like `char outConstr[192]` (kept for compat); no `\x`
  escapes in string literals (use raw ESC byte pattern from error.crl); multiple
  declarators on one line with mixed arrays fail to parse (split lines).
- Comments only where explaining non-obvious rationale; match existing terse
  comment style.
- After every change: `./build 2>&1 | grep -E "error" | head` must be clean, then
  rerun the §3 repro battery.
- Never touch `lib/` for fixes (legacy). lib2 mirrors exist for runtime parity work.

## 6. Key file map

- `src/error.crl` — all rendering; `diag(code,file,src,line,col,lvl,msg,help)`.
- `src/token.crl` — OP_TERMS/KW_TERMS/ANON_TERMS + T_* ids (id = index-based; DO
  NOT reorder OP_TERMS/ANON_TERMS without updating constants).
- `src/lexer.crl` — `scanPunct` (LEX-0007 hook), `scanWord`, `lex()` main loop;
  errors LEX-0001..0007.
- `src/parser.crl` — `errorMsg(code,msg,help)` helper at :352; `skipFileAttrs`
  :488; `hasAttr` :520; `parseAttachedAttrs` :529; `parseAsmStmt` :1706;
  `parseStructDecl` :3172; top-level dispatch ~2960-2980 (SYN-1998/-1003).
- `src/typecheck/expr.crl` — `typeExpr`, `typeStmt` (ST_RETURN :1605), 
  `typeFunction` :1897, TC-* sites listed in G3.
- `src/codegen/emitir.crl` — `genAsm`, `parseExprSnippet`, `structFieldOffset`,
  `dumpIR`, `emitIR`, `buildModule`.
