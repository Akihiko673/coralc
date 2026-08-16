# wallvm backend status — issues, decisions, todos

Date: 2026-08-14

## Verification status

- **x86_64 backend** (fully rewritten, LSRA-consuming, AT&T/Intel) — **ALL PASS** both syntaxes:
  - AT&T via `gcc -x assembler`: ra_muladd=80, ra_addsub=938, ra_many=13452, ra_mem=42, ra_phi=52, ra_fcast=18
  - Intel via `nasm -f elf64`: same, ALL PASS
  - **emitCall arg-staging now runtime-verified end-to-end** (`ra_args.crl` + `ra_args_harness.c`): 2 reg args → 42, 10 args (6 reg + 4 stack) → 55, 2 float args (xmm0/xmm1 + alignment pad) → 9.0. Both AT&T/gas and Intel/nasm pass.
  - Win64 (SystemV ABI + shadow space) assembles clean with gas
- Driver arg wrap: `sys` = SystemV (AT&T), `win` = Win64, `cdecl` parsed but NOT yet functional (see issues), `a64` parse-only
- Test flow: `./ra_smoke <cc> <outdir> [intel]` writes per-module `.s` files (each module = separate codegen pass, labels restart per module by design)

## Issues found & fixed (this session)

1. `floatHolds`/`intHolds` were NULL when first read (no bounds guard) → SEGV in `floatStore`. Guarded with `ai < holdsCap`.
2. `store()` AT&T spill branch (line ~601) emitted a LOAD (`movq -N(%rbp), %rax`) where a STORE was needed → spilled values never written, wrong results (ra_many=7080). Fixed to `movq %rax, -N(%rbp)`.
3. My "fix" for #2 accidentally applied load-direction change to `load()`/`loadArith()` spill branches (529/565) → doubled stores, acc chain corrupted. Reverted to load direction. Lesson: load = mem→reg (AT&T), store = reg→mem (AT&T) — check direction per function, don't sed blindly.
4. Block labels `.LBB0` collided across modules because each module is a separate `irCodegenX86_64Asm` call with a fresh `labelSeq`. Fixed at driver level: per-module asm files.
5. Float const staging (`floatLoad`) had flipped AT&T operands (`movq xmm0, -8(%rbp)` instead of `movq -8(%rbp), %xmm0`) → fixed; Intel branches were correct throughout (dest-first).
6. `movq rsi, mem` (missing `%`) in AT&T reg→spill stores → fixed with inline `%`.
7. `wallvm_gTracePasses` no longer exists in lib → removed from driver main.
8. x86 ABI tables had EMPTY floatArgRegs for cdecl/stdcall/fastcall → LSRA float pool empty (root cause of slot-based x86). Fixed in `asm_rules.crl`: `X86_SSE_FLOAT_ARG_REGS` xmm0-7, `floatReturnReg="xmm0"`, fastcall patched.
9. `formatForCc(cc)` added to asm_rules: x86_64 CCs → Att, x86 CCs → Intel.
10. gcc builtin-conflict warnings killed: `-ffreestanding` added to default `--cflags` in `py/main.py` (compile freestanding, link libc normally).

## Remaining quality issues (correctness OK, optimization)

- **Register-relay copies**: LSRA doesn't coalesce; phi-adjacent and chain values ping-pong (`mov %rsi, %rdi; ...; mov %rdi, %rsi`). Harmless, noisy. See ra_phi/ra_spill output.
- **Float constants** rematerialized per use via `movabs` + slot staging (3 instrs) — no const pool / rodata yet.
- `movq %xmm0, %xmm3; movq %xmm3, %xmm0` relay around float ops (result home in pool, scratch in xmm0).
- Minor: `mov $0, %rcx; cmp %rcx, %rsi; setg` could be `test %rsi, %rsi`.
- Jumps to conditionally-fallthrough blocks (`jmp .LBB3` after `.LBB1`) — no block reordering.

## Open verification gaps

- **Params**: `IrFunc.nparams/paramTypes` never exercised — no param-loading emission tested in any backend. (Caller-side arg staging IS exercised now via ra_args; the callee reading params from arg regs is still unbuilt in x86_64.)
- **x86 CCs are in `targetConsumesRegAlloc`/`regallocConfigFor` already but the x86 backend is still the OLD slot-based one** → compile with cdecl/stdfastcall today would emit WRONG code (LSRA assignments not decoded). Backend rewrite is REQUIRED before any x86 CC is usable. Latent trap for anyone using `cdecl` now.
- Win64 runtime not verified (assembles only).
- Other backends (arm64/arm/riscv/ppc64/ppc/mips64/mips/sparc64) still slot-based; `irCompileAsm` returns null for all non-x64 CCs.

## Fixed notes for x86 (32-bit) backend rewrite

- NO `sil/dil/bpl/spl` in 32-bit mode — 8-bit encodings only al/cl/dl/bl/ah/ch/dh/bh; esi/edi/ebp have NO 8-bit form (shim via al, or movzx from spill).
- 16-bit forms exist for all (si/di/bp).
- ebp is frame pointer → reserved with eax/ecx/edx; pool = ebx/esi/edi (callee-save) + xmm3-7 floats.
- Backend must push/pop used callee-save regs (ebx/esi/edi) in prologue/epilogue.
- cdecl params at [ebp+8+4i]; floats: no 64-bit gpr↔xmm moves — push twice + `movq xmm, [esp]` for consts.
- Draft parts written to /tmp/opencode/x86_part1.crl + x86_part2.crl (unverified, likely bugs — see the load/store direction lesson above).

## RegAlloc/LSRA contract (fixed)

- valData encoding: bit31 = spill, bit30 = float, else int pool index; mask 0x3FFFFFFF.
- x86_64: int pool rsi/rdi/r8-r11 (rax/rcx/rdx reserved), float pool xmm3-7; `useCalleeSave=false`.
- x86: pool ebx/esi/edi, float xmm3-7; `useCalleeSave=true` (caller-save set is all scratch).
- `backendHandlesSpills` gates IR-level spill rewriting; per-CC in `regallocConfigFor`.

## Build/flow

- `python3 py/main.py --keep-c -o DIR lib/wallvm/tests/ra_smoke.crl` (C WITH debug kept; default flags now include -ffreestanding)
- artifacts: /tmp/opencode/ra/{out,mod,modint,modwin,harness.c}