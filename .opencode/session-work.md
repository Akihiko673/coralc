# Coral audit — working context

## Goal
Finish the ~180-item audit of Coral's `lib/` and `wallvm/`: EASY/MED/HARD tiers, WALLVM pass/backend fixes, docs drift, and runtime verification are complete except style cleanups and an optional wallvm end-to-end test.

## Constraints & Preferences
- Parse-verify each file: `python3 py/main.py -S --flags=platform=LINUX,ARCH=x86_64,ENDIAN=little -o /tmp/opencode/sweep <file>` (cwd `/home/cerie/Projects/coral`).
- Full build/run: `cd py` then `python3 py/main.py --flags=platform=LINUX,ARCH=x86_64,ENDIAN=little -o <outdir> <file>`; input files outside the repo need `-I lib`.
- No whole-tree sweeps (user aborted those as time-taking).
- Leave `lib/tests/errors/e01–e05` untouched (intentionally fail).
- Remove mechanical/AI-style comments everywhere unless a human plainly wrote them; never use column-aligned `=` spacing anywhere (user flagged lsra's aligned blocks as the anti-pattern).
- Noret termination lives in the compiler toolchain (wallvm), all OS/arch variants present in the compiler, selected at runtime (if/else chain — string `switch` is invalid in emitted C).

## Progress
### Done
- EASY + MED tiers: complete (utf8/json/toml/csv/xml/regex/string/hashmap/bitset/trie/sort/random/duration/net/fios/log/bloom/pool/mman allocators, option, smart_ptr demoted to docs).
- HARD tier, all parse-checked: embed TLSF (`prevPhysSize` sentinel/first-block, `_tlsfSplitBlock` remainder, 4 `prevPhysSize` sites incl. realloc grow-merge); `mman.crl` `_heapRealloc` `nn->prevPhysSize`; thread `fetchSub`/`fetchAdd` old-value fixes; mutex dead field; semaphore bool init; threadpool guards; `startup_templates.crl` `flag (ARCH)` + `x86_64:` label + `_splitCmdline` backslash runs; bioembed shift guards.
- WALLVM tier, all parse-checked:
  - `domtree.crl` two-phase `_domEval` reusing dead DFS `stack`.
  - `sccp.crl`: Top absorbing in `latticeMeet`; Bottom keeps both edges; phi folds by `(value, block)` pairs + `findBlockIdx`.
  - `tco.crl`: header phis `{ident, &e.base, &e.base, &e.base}`, single `addUser` per distinct operand.
  - `x86_64.crl`: unsupported opcodes emit `; unsupported opcode:<name>` + `unsupported` flag → codegen false.
  - `constfold.crl`: `_signExt` helper for Ashr/SDiv/SRem/SMin/SMax/Abs.
  - `borrowcheck.crl`: Store `ops[0]`=value / `ops[1]`=address fixed at 3 sites (write-capability `ops[1]`, alAdd/global slot `regionOf(ops[1])`, StoreVsLiveLoad `regionsOverlap(load.ops[0], store.ops[1])`), all nops≥2 guarded.
  - `mem2reg.crl`: worklist seeded by loads too; uninitialized-path loads → `ctx.constInt(type,0)`; `renameBlock(ctx)`.
  - `range.crl`: union drops empty intervals (±inf eff bounds); gap check `maxLo-minHi>=2` with one-sided support.
  - `inline.crl`: post-clone remap pass for forward (loop-carried phi) refs via valMap + removeUser/addUser; `countBodyInsts` underflow guard.
  - `dce.crl`: ADCE detach pass nulls unmarked insts' refs from users before erasure.
- Docs tier: `std_api_reference.md` (deinitDefaultAllocator, S_IRUSR/IWUSR/IXUSR, math 28-fn block + `srt2`, Mat4 det, array→arr); `codegen.spec.md` status note (goto/else/for are historical; backend emits structured C); `noreturn.md` implementation-status section.
- `lib/std/math/math.crl`: `tan(x;`→`tan(x)`, `libc.strdod`→`libc.strtod`, `libc.asin };`→`libc.asin(x)`.
- base64 (`lib/std/crypto/base64.crl`): `byteV`→`const u8 _TABLE[]`; `encodeToString` fully qualified + mman import; module-not-found only warns then emits broken C (no unresolved-name check).
- Runtime green: diag suite A 5/5, `lib/main.crl` exit 1 (expected), section D t01–t10 exit 0.
- array→arr rename: `lib/std/collections/arr.crl` (`pub struct arr<T,N>`) replaces deleted `array.crl`; t05 uses `arr.arr<u64,3> a;` (dot access) → exit 0; docs §8 updated.
- b64test (`/tmp/opencode/b64test.crl`, +`b64bin/`) covers encode/decode/encodeToString, exit 0 — hang was a long include chain (~1-2 min), not a compiler bug.
- NORET PLATFORM/OS UNIFICATION (see Recent Completion below).

### In Progress
- (none)

### Blocked
- (none) — wallvm-pipeline end-to-end runtime (lib/main.crl via wallvm backend) still untested; only the C-emission path is runtime-verified.

## Recent Completion (this session, all parse-checked / runtime-verified)
- NORET PLATFORM/OS UNIFICATION (DONE): `noret_x86_64.crl`, `noret_arm64.crl` each now have Linux syscall / Windows ExitProcess / macOS (`0x2000001` or `svc #0x80`) / bare halt + `pub emitNoretPlatform(*, const char* platform)` if/else dispatch + file-scope `static bool platformMatch` (no self param — pure helper, per review). `noret_arm.crl` has Linux/Windows/bare (no macOS arm32) inside the struct, self-less `platformMatch` at file scope after struct. `noret_bare.crl`: `flag (ARCH)` block replaced by `pub emitHalt(, const char* arch)` runtime dispatch with `bareArchMatch` covering x86_64/x86/x86_32/arm64/arm/riscv64/ppc64/ppc/mips64/mips/sparcv9/sparc64 + x86 default. All four codegen clean; no `flag` blocks left. Dispatch is if/else, NOT `switch` — string switch is invalid in emitted C.
- lsra.crl CLEANUP (DONE): removed the one column-aligned `=` block (assignVregs alloc block), unaligned field-doc comment columns; removed mechanical restatement comments; kept non-obvious ones (spansCall callee-save, eviction rules, stale-mapping, skip-defStore caveat, SPILL_BIT/FLOAT_BIT encoding, phi-placement). Parse-checks.
- mman.crl ALIGNMENT (DONE): `alloc->cap  =` and `blockSize / blockCount` aligned blocks → single spaces (only two in whole repo; global grep now shows 0 aligned blocks in lib/ or wallvm/).
- borrowcheck.crl: removed duplicated module doc header (old 7-32 vs new 34-70 kept).
- Wallvm comment audit: remaining comments across dce/inline/mem2reg/range/sccp/tco/constfold/domtree/x86_64.crl are substantive algorithm/invariant docs — kept by design (they document this session's fixes).
- REGRESSION: full `lib/main.crl` std build + run passes (exit 1 expected) after mman edits.

## Key Decisions
- Store operand convention (from ir_builder.crl:172-178 + all asm rules): `ops[0]`=value, `ops[1]`=address.
- mem2reg uninitialized loads → zero constant (never leave loads after alloca erasure).
- inline forward refs fixed by second remap pass (not two-pass cloning).
- ADCE detaches before erasing; DCE `isDead` (nusers==0) path unchanged.
- Range union merges only when `maxLo-minHi<2` after dropping ±inf-empty intervals.
- `arr.arr` dot module access is correct (user-confirmed).
- noret: runtime if/else dispatch, all variants in toolchain files; string `switch` rejected (invalid C).

## Next Steps
1. Optional: end-to-end runtime test through the wallvm pipeline (lib/main.crl via the wallvm backend instead of the C emitter).

## Critical Context
- `replaceAllUses` rewrites ops+user lists on both sides; `removeUser` removes one occurrence; `addSucc` auto-registers the pred; `irOpcodeIsTerminator` covers Br/CondBr/Ret/Unreachable/Noret.
- Import resolution: importer's ancestor dirs → cwd → `search_paths` (`['std']` from cwd + `-I`); no `std` tree at repo root — repo-relative files resolve via ancestors, out-of-tree inputs need `-I lib`.
- base64 runtime path verified: encode → decode → encodeToString, exit 0.
- `lib/std/math/math.crl` exports `srt2`/`sqrt2` + 28 libc fns.
- Static file-scope funcs with explicit first param (self) work; called as `self->name(self, ...)` or plain `name(...)`; methods inside structs called as `self.method(...)`; static pure helpers need NO self param (user review).
- method bodies with anonymous first param use `self` sugar both as receiver (`self.c(...)`) and field carrier (`self->exitCode`).

## Relevant Files
- `lib/wallvm/passes/{borrowcheck,mem2reg,range,inline,dce,sccp,tco,constfold}.crl`, `lib/wallvm/domtree.crl`, `lib/wallvm/target/x86_64/x86_64.crl`: WALLVM fixes, parse-checked.
- `lib/wallvm/noret/{noret_x86_64,noret_arm64,noret_arm,noret_bare}.crl`: platform/arch dispatch unification, codegen-verified.
- `lib/std/crypto/base64.crl`, `lib/std/math/math.crl`, `lib/std/collections/arr.crl`: lib fixes.
- `lib/tests/t05_array_int_arg.crl`, `lib/main.crl`, `py/main.py`: verification (t01–t10 green).
- `docs/{std_api_reference.md,noreturn.md,codegen.spec.md}`: drift fixed + status notes.
- `/tmp/opencode/sweep/` (parse-check output), `/tmp/opencode/b64test.crl` + `b64bin/` (b64 e2e).
- `lib/wallvm/regalloc/lsra.crl`: spacing/comment cleanup pending.
- `py/parser.py:1421-1454`, `py/codegen.py:1694`: switch syntax available (not used for noret — string cases illegal in C).

---

# Session: textbook std.any struct + Drop trait inline (docs + lib/std)

## Goal
Continue the Coral philosophy textbook (docs/textbook/01–10) and introductory compiler work: ch10 written & expanded; Drop-trait memory-safety revision of ch01/05/06/08/09 done; then introduce `std.any` (struct of a `void*` with methods) and use it in non-std examples; make the Drop trait declare `inline void drop();` (body injection, not a call).

## Progress
- **std.any converted typedef → struct**: `lib/std/misc/any.crl` now `@[no_warn_unsafe] pub struct any { void* p; void* ptr(); bool isNull(); T* as<T>(); }` + module-level `pub any wrap(void* value)` (builds via `std.any a; a.p = value;`). `ptr()` fixed to return `void*` (was `any`, broke cast.crl), per user confirmation. `lib/std/misc/cast.crl` updated: `(T)val` → `(T)val.ptr()`.
- **ch10 (10-concurrency-and-parallelism.txt)**: §10.4 intro rewritten for struct-any (wrap/ptr/isNull/as<T>); 20 code sites converted: `any x(any arg)` → `std.any x(std.any arg)`, `(T*)arg` casts → `arg.as<T>()`, `(any)checksum` → `std.any.wrap((void*)checksum)`, `(any)paths[i]` → `std.any.wrap((void*)paths[i])`, `return null;` → `return std.any.wrap(null);` (10×), Timer loop `void(std.any) fn; std.any arg;`, async chain `void(std.any)` sigs.
- **ch9**: pool/scope call sites → `std.any n = std.any.wrap(pool.allocBlock());` + `pool.freeBlock(n.ptr());`, `std.any buf = std.any.wrap(scope.alloc(256u));`; 9.31 Drop trait now `trait Drop { inline void drop(); }` with inline-body-injection prose (no separately emitted function, body duplicated per scope end); summary updated. std pool/Regex struct decls (verbatim std) kept `void*`.
- **ch8**: 8.7 updated — "body of its drop injected", inline contract sentence added.
- **ch7 7.9**: new paragraph + verbatim any.crl snippet (struct + methods + wrap) contrasting struct-any vs typedef (own type, no implicit conversion, surface for operations).
- ch1/ch5/ch6 Drop mentions already injection-styled; no changes needed.

## Key Decisions
- Coral function-signature convention (from real std): return type FIRST (`any wrap(void* value)`, `T* as<T>()`, `void dispose()`), NO `->`, methods NOT `pub`, `self.` receiver; module-relation via `mod x = import(...)`. Textbook snippets must quote any.crl verbatim (user-confirmed).
- Textbooks: `std.any`: struct (not typedef) → own type, explicit wrap/ptr/as<T>/isNull boundaries, still "not protected". Drop: `trait Drop { inline void drop(); }` — body injected at scope end (exactly once, all exit paths, reverse decl order like defers); impl blocks (`MyBuffer::Drop { void drop() {...} }`) stay non-inline.
- std note maintained: Drop implemented/supported across std, but modules use manual frees for fast std compilation.
- **USER IS ACTIVELY EDITING lib/std concurrently** (git shows modified: lib/std/concurrent/thread.crl, lib/std/math/math.crl, lib/std/memory/mman.crl, lib/std/misc/any.crl, lib/std/misc/cast.crl). Do not stomp their lib edits; match their file spellings in docs.

## Next Steps
1. Resume self-host compiler: generics `f<T>` / `a.b<T>` (LT/BANG_LT, `>>` closing-depth; check token.crl BANG_LT), then statements/decls, then `constexpr` + Drop-based `new`.
2. Optional: Drop sweep of ch02/ch04/ch07 remaining; verify any chapter's remaining `void*` are verbatim-std only.

## Relevant Files
- lib/std/misc/any.crl (struct any + wrap), lib/std/misc/cast.crl (adapted).
- docs/textbook/07-type-system.txt (7.9), 09-memory-management.txt (9.11/9.12 code, 9.31 Drop), 10-concurrency-and-parallelism.txt (860 lines, 35 sections, std.any throughout), 08-object-oriented-programming.txt (8.7).

---

# Session: textbook example expansion (ch3 done, ch4 + ch5 in flight)

## Goal
User asked for "more examples and explanations throughout the docs". ch3 fully expanded (with 3.27 Frame Header worked example); ch4 and ch5 expansions this session.

## Progress
- **ch3 (03-operators-and-expressions.txt)**: 801 → 996 lines. New **3.27 A Worked Example: The Frame Header** (pack 3 bytes via shift/OR/narrowing cast, unpack via shift/mask/cast, XOR checksum fold, `%` ring slot, guarded rate division, `busy ^= true` toggle, 2-check valid && chain). ~15 new examples: 3.2 arity trio, 3.3 grid row/col via `k/cols` + `k%cols`, 3.4 `rateOf` zero-elapsed-time guard, 3.5 checkedMul division-identity assert + u8 counter wrap detour (22 rounds), 3.6 `*=`/`%=`/`^=` idioms, 3.8 `f(n, ++n)` argument-order trap + fix, 3.9 signed counter vs `(u64)len` cast, 3.13 bound-guard search loop, 3.14 min + clamp nested ternaries, 3.19 swap, 3.20 row-major pixel index + pointer-walk, 3.23 flags precedence trap (type error in Coral), 3.24 `100/10/2` + `97%15%10` chains. Summary updated with worked-example bullets.
- **ch4 (04-control-flow.txt)**: 846 → 910 lines (+64). Added: guard-clause validator (`validConfig`, 3 checks / 3 exits + short-circuit &&); multi-statement switch cases (log-handler, two actions per case, no-fallthrough prose); linked-list while walk (cur/cur->next, no counting); nested for multiplication table (10x10 grid); running-max loop invariant in 4.27.
- **ch5 (05-functions-and-procedures.txt)**: 686 → 715 lines (+29). Added: composition pipeline example (`mean(fetchAllocations())`); copy-cost visibility (`BigBuf` 2048-byte value vs pointer touch, silent-no-op note); `gcd` (Euclid, tail-position tie-in to 5.16) + `countNodes` (tree structure recursion, null base case) in 5.15.

## Key Decisions
- No new capstone section added to ch5: 5.30 "What a Function Is" is the rhetorical close; per-section examples carry the expansion (ch3-style capstone was right for ch3, not ch5).
- All new examples in established voice: short sentences, ` — ` dashes, std-library references, worked walks with explicit values (gcd(48,18) trace).
- ch4 already had 3 worked examples (4.28 Command Dispatcher, 4.29 Tokenizer, 4.30 Parsing with Defer and Result) — targeted additions instead.
- Recursion examples intentionally mirror the book's own rules: "depth recurses; length iterates" and tail-position tie-in to 5.16 TCO section.

## Next Steps
1. (pending user choice) further expansions: ch1–2, ch6–7, ch8–9 passes.
2. Resume self-host compiler generics `f<T>`/`a.b<T>` (LT/BANG_LT, `>>` closing-depth; token.crl BANG_LT) once textbook passes are done.

## Relevant Files
- docs/textbook/03-operators-and-expressions.txt (996 lines, 3.27 capstone)
- docs/textbook/04-control-flow.txt (910 lines), docs/textbook/05-functions-and-procedures.txt (715 lines)
- .opencode/session-work.md (this block)

---

# Session: textbook example expansion ch6–9

## Goal
Continue the "more examples throughout the docs" series: ch6–7, then ch8–9, then return to the self-host compiler (the real todo).

## Progress
- **ch6 (06-data-structures.txt)**: 1135 → 1172 lines. BFS graph walk with `std.queue` added to 6.8 — fulfills the chapter intro's promised-but-missing canonical example ("a queue walking a graph"); mark-then-enqueue discipline explained (mark records discovered, never enqueue twice, layers in FIFO order, linear cost). Undo-history example in 6.5 (EditorState stack: push on edit, pop most-recent-first) + expression-evaluator LIFO tie-in.
- **ch7 (07-type-system.txt)**: 649 → 679 lines. 7.5: nested-generic composition made concrete (`std.vec<std.Pair<std.strView, JsonValue>> fields;` + inside-out reading). 7.10: FFI boundary cast walk (`(i32)cfg` for libc — distinct `std.File` stays distinct until the written cast). 7.26: real padding arithmetic — `Interleaved` (u8,u64,u8 = 24 bytes) vs `Grouped` (u8,u8,u64 = 16 bytes), 8MB padding in a million-element vec, `sizeof` prints 24/16.
- **ch8 (08-object-oriented-programming.txt)**: 570 → 583 lines. 8.4: implicit vs explicit receiver styles side by side (`void bump()` with `self.value` vs `void bumpExplicit(self*)` with `self->value`); constness rule stated — reads declare `const self*`, mutating methods declare `self*`, written not assumed. (User correction applied twice: explicit receiver is anonymous first param `self*`/`const self*`, NOT `TypeName*`; and mutating receivers must NOT be `const self*`.)
- **ch9 (09-memory-management.txt)**: 596 → 603 lines. 9.29: Valgrind leak walk tied to the 9.30 loader — "definitely lost: 4,096 bytes" names the batch size, allocation stack points at arena init, fix is the missing `arena.reset()` on an early-return path.

## Key Decisions
- ch6/ch7 already dense (worked examples: 6.5 balanced, 6.11 counter, 6.17 fib, 6.25 Point hashes, 6.14 sieve, 7.25 modeling); targeted additions only — fill promises/figure-less prose, not volume.
- ch8/ch9 already complete with worked examples (8.16 Shape Library, 8.18 Repository, 9.30 Loader, 9.31 Drop); one modest addition each + the receiver-style clarification.
- Receiver convention (user-corrected, matches real std): explicit form is an anonymous first parameter typed `self*` (mutating) or `const self*` (read-only) — `bool isOk(const self*)`, `void insert(MemoryRepository* self, Record r)`; body uses the `self->` sugar. Never write `TypeName* self`.

## Next Steps
1. Textbook passes complete (ch3, ch4–5, ch6–7, ch8–9) → RETURN TO SELF-HOST COMPILER: generics `f<T>` / `a.b<T>` (LT/BANG_LT, `>>` closing-depth; check token.crl BANG_LT), then statements/decls, then `constexpr` + Drop-based `new`.
2. Optional later: ch1–2 or ch10 re-pass for examples.

## Relevant Files
- docs/textbook/06-data-structures.txt (1172), 07-type-system.txt (679), 08-object-oriented-programming.txt (583), 09-memory-management.txt (603)
- .opencode/session-work.md (this block)

---

# Session: self-host — generic instantiation `f!<T>` / `a.b!<T>` in the expr parser

## Goal
Start the real todo (self-host compiler): expression-level generic instantiation in the LALR(1) expr parser, mirroring py/parser.py's postfix `!<` sites (1668/1820/1889).

## Progress
- **token.crl**: `"!<"` (BANG_LT) added to OP_TERMS (before 1-char `!`, longest-first) and ANON_TERMS (after `!=`); NUM_ANON 98→99 (terminal ids recompute at runtime; nothing hardcodes them).
- **lexer.crl**: scanPunct loop bound 49→50 (OP_TERMS now 50). Also fixed latent off-by-two: scanWord loop `q<47` → `q<49` — KW_TERMS has 49 entries, so `isize`/`usize` previously lexed as IDENT (casts like `(usize)x` silently broke).
- **parser.crl**: `AC_GENERIC=51`; new nonterminal `N_TARGS=17` (`N_COUNT` → 18); `g.nterms` 104→105, `g.nprods` 79→82 (termPrec alloc/init loop likewise). Three productions appended after the N_T block: `P -> P !< TARGS >` (AC_GENERIC → EX_GENERIC, args stolen from the EX_INIT list node like AC_CALL), `TARGS -> T` (AC_LIST), `TARGS -> TARGS , T` (AC_LISTAPP). Arg types reuse N_T = type keywords + IDENT. `apply()` gains the AC_GENERIC branch.
- **lalr.crl (real bug found)**: `build()`'s BFS loop held `State* s = &self.states[i]` across `gotoState(i, sym)`, whose `findOrAdd → growStates` can realloc the states array — dangling `s` mid-iteration. Latent (didn't manifest at 79 prods; 82 prods crossed the growth threshold → SEGV in Generator_build). Fixed with the same defensive pattern gotoState already used: re-fetch `s = &self.states[i]` after the gotoState call. This is not a workaround — the generator invariant was genuinely violated.
- **expr_harness.crl**: EX_GENERIC dump `(generic <base> ty <arg>...)`; 9 new good tests (`vec!<u32>`, `f!<i32>(1,x)`, `a.b!<u8>`, `f!<Node>()`, `m!<u64>->get()`, `x!<T, u8, Node>`, `vec!<u32> + 1`, `f!<i64>(a) - 2`, `f!<isize, usize>`) + 4 bad (`f!<>`, `f!<u32`, `f!<u32,>`, `m!<v!<u64>>`).

## Verification
- 51 good + 19 bad, ALL PASS (plain, ASAN, static). valgrind `--leak-check=full --error-exitcode=1` static build: clean.
- Build: `cd py && python3 main.py --flags=platform=LINUX,ARCH=x86_64,ENDIAN=little -I ../lib -o /tmp/opencode/exptest --keep-c ../src/expr_harness.crl` (±`--keep-c`; gcc variants from `/tmp/opencode/exptest` — the toolchain deletes emitted .c/.h unless `--keep-c`).

## Key Decisions
- BANG_LT-only generics in the expr grammar: unambiguous terminal, zero conflicts with the comparison layer. Plain `<` (py's `_lt_is_generic` lookahead heuristic) and the `>>` closing-depth split (GTGT closing two nested levels, py's `_gtgt_consumed`) are NOT expressible in the table-driven LALR(1) expr grammar — deferred to the statements/decls phase; bad test `m!<v!<u64>>` documents the limitation.
- EX_GENERIC args stored as Expr*[] of EX_TYPELIT text-only nodes via `args/nargs` (same shape as AC_CALL): ast.crl's `TypeExpr** targs` encode is for the future decl parser.
- Nested generics compose fine at top level: `f!<T>(x)` = EX_CALL over EX_GENERIC; `m!<u64>->get()`, `x!<u32>++` etc. all plain P-level composition.

## Next Steps
1. Statements/decls phase: func generic params (`f<T>` decl side, py 631–637), plain-`<` disambiguation (`_lt_is_generic`), `>>` closing depth in full types (`std.vec<std.vec<u64>>`).
2. Then `constexpr` + Drop-based `new`.
3. Optional: wire main.crl to ExprParser (currently lexer-dump only).

## Relevant Files
- src/parser.crl (grammar now 82 prods; AC_GENERIC/N_TARGS), src/token.crl (BANG_LT), src/lexer.crl (scanPunct 50, scanWord 49), src/lalr.crl (build() dangling-state fix), src/expr_harness.crl (51+19 tests)
- Reference anchors: py/parser.py 1668/1685/1820/1855-1863/1889 (postfix `!<`), 631-637 (decl-side generic params), py/tokenizer.py 327 (BANG_LT 2-char emit)
