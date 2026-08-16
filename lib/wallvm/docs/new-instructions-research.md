# Cross-Platform Instructions — Research for IR Addition

Research into instructions present across **x86, ARM, RISC-V, PowerPC, and MIPS**
architectures, gathered for potential addition to the compiler IR.

 

## Principles

- "Present" means the instruction exists as a single hardware opcode on
  **at least two** of the major ISAs (x86, ARM, RISC-V, PowerPC, MIPS).
- Vector/SIMD variants are noted but the primary focus is scalar operations.
- Each candidate lists the mnemonics per architecture so the IR opcode can
  be mapped to a single native instruction on each backend.

 

## 1. Bit Manipulation

### 1.1 Population Count — `ctpop` (Count Set Bits / Hamming Weight)

Present on all modern architectures.

| Arch    | Mnemonic  | Since                                |
|   |   --|            --|
| x86     | `POPCNT`  | SSE4.2 (Nehalem), AMD Barcelona      |
| ARM     | `VCNT`    | NEON (A/R profile), A64 `CNT`       |
| RISC-V  | `CPOP`    | Zbb extension (B 1.0)               |
| PowerPC | `POPCNTD` | ISA 2.06 (POWER7)                    |
| MIPS    | `POP`     | MIPS32/64 Release 6                  |

**Semantics:** Returns the number of 1-bits in the input.
**Example:** `ctpop i32 %x` → `i8`

### 1.2 Count Leading Zeros — `ctlz`

Present on every modern architecture.

| Arch    | Mnemonic  | Since                                |
|   |   --|            --|
| x86     | `LZCNT`   | BMI1 / ABM (AMD Barcelona, Intel Haswell) |
| ARM     | `CLZ`     | ARMv5T and later, A64               |
| RISC-V  | `CLZ`     | Zbb extension (B 1.0)               |
| PowerPC | `CNTLZD`  | ISA 1.00 (original POWER)           |
| MIPS    | `CLZ`     | MIPS32/64 Release 1                 |

**Semantics:** Returns the number of leading zero bits. For input 0, returns the
operand width (32 or 64).
**Example:** `ctlz i32 %x` → `i8`

### 1.3 Count Trailing Zeros — `cttz`

| Arch    | Mnemonic  | Since                                |
|   |   --|            --|
| x86     | `TZCNT`   | BMI1 (Haswell, AMD Barcelona)       |
| ARM     | `RBIT` + `CLZ` | ARMv6T2+ (RBIT available)     |
| RISC-V  | `CTZ`     | Zbb extension (B 1.0)               |
| PowerPC | `CNTTZD`  | ISA 3.0 (POWER9)                     |
| MIPS    | —         | No direct; uses `CLZ` subtract       |

**Semantics:** Returns the number of trailing zero bits. For input 0, returns the
operand width.
**Example:** `cttz i32 %x` → `i8`

### 1.4 Rotate Left / Right — `rotl` / `rotr`

| Arch    | Mnemonic       | Since                                |
|   |     -|            --|
| x86     | `ROL` / `ROR`  | 8086 (always present)               |
| ARM     | — via barrel shifter, or `EXTR` | Always present      |
| RISC-V  | `ROL` / `ROR`  | Zbb extension (B 1.0)               |
| PowerPC | `ROTL` / `ROTR`| Always present                      |
| MIPS    | `ROTR` / `ROTRV`| MIPS32 Release 2                  |

**Semantics:** Bitwise rotation of the first operand by the second.
**Example:** `rotl i32 %x, %y`

### 1.5 Byte Swap / Reverse Bytes — `bswap`

| Arch    | Mnemonic  | Since                                |
|   |   --|            --|
| x86     | `BSWAP`   | 80486                                 |
| ARM     | `REV` / `REV16` / `REV32` / `REV64` | ARMv6+ |
| RISC-V  | `GREVI` with imm | Zbb extension (B 1.0)          |
| PowerPC | `STBYX` / `LDBRX` etc. | Always present              |

**Semantics:** Reverses the byte order within each word of the input.
**Example:** `bswap i32 %x`

 

## 2. Min / Max

### 2.1 Signed Integer Min/Max — `smin`, `smax`

| Arch    | Mnemonic         | Since                                |
|   |      |            --|
| x86     | `PMINSD/B` / `PMAXSD/B` | SSE2/SSE4.1 (128-bit), AVX2 (256-bit) |
| ARM     | `SMIN` / `SMAX`  | NEON, A64                            |
| RISC-V  | `MIN` / `MAX`    | Zbb extension (B 1.0), also scalar   |
| PowerPC | `XSMINDP` / `XSMAXDP` | scalar via FP; `PMINSW`/`PMAXSW` vector |

**Semantics:** Returns the smaller/larger of two signed integer values.
**Example:** `smin i32 %a, %b` → `i32`

### 2.2 Unsigned Integer Min/Max — `umin`, `umax`

| Arch    | Mnemonic          | Since                                |
|   |      -|            --|
| x86     | `PMINUB` / `PMAXUB` | SSE2, MMX                         |
| ARM     | `UMIN` / `UMAX`   | NEON, A64                            |
| RISC-V  | `MINU` / `MAXU`   | Zbb extension (B 1.0)               |
| PowerPC | `PMINUW` / `PMAXUW` | vector via AltiVec               |

**Semantics:** Returns the smaller/larger of two unsigned integer values.
**Example:** `umin i32 %a, %b` → `i32`

### 2.3 Floating-Point Min/Max — `fmin`, `fmax`

Two variants per architecture. Architecture behavior differs on NaN
and signed zero:

| Arch    | Non-NaN preserving | NaN propagating   |
|   |      -|      -|
| x86     | `MINSS`/`MAXSS`  | —                 |
| ARM     | `FMIN`/`FMAX`    | `FMINNM`/`FMAXNM`| 
| RISC-V  | `FMIN.S`/`FMAX.S` | follows same (returns non-NaN) |
| PowerPC | `XSMINDP`/`XSMAXDP` | `XSMAXDP`/`XSMINDP` (NaN → QNaN) |

**Semantics:** Returns the minimum/maximum of two float values.
Behavior on NaN and signed zero is implementation-defined.
**Example:** `fmin float %a, %b` → `float`

 

## 3. Fused Multiply–Add — `fma`

| Arch    | Mnemonic            | Since                                |
|   |       |            --|
| x86     | `VFMADD132SS`/`SD`  | FMA3 (Haswell, AMD Piledriver)       |
| ARM     | `FMLA` (vec), `FMADD` (scalar A64) | NEON, A64, VFPv4 |
| RISC-V  | `FMADD.S`/`FMADD.D` | Single/Double precision always        |
| PowerPC | `XSMADDADP` / `XVMADDASP` | VSX, VMX                     |
| MIPS    | `MADD.S` / `MADD.D` | MIPS-3D, MSA                         |

**Semantics:** Computes `a * b + c` with a single rounding step (no
intermediate overflow/underflow). Four-operand fused multiply-add
variants (`fma(a, b, c, d) = a * b + c * d`) also exist.
**Example:** `fma float %a, %b, %c` → `float`

 

## 4. Saturating Arithmetic

### 4.1 Signed Saturating Add/Sub — `sadd_sat`, `ssub_sat`

Result clamps to `[INT_MIN, INT_MAX]` instead of wrapping.

| Arch    | Mnemonic        | Since                                |
|   |     --|            --|
| x86     | `PADDSB/W`      | MMX/SSE (vector)                     |
| ARM     | `QADD` / `QSUB` | ARMv5E and later, NEON `VQADD`/`VQSUB` |
| RISC-V  | —               | Not in scalar (vector `VSADDU`/`VSSUB` in V) |
| PowerPC | —               | Not scalar; vector via AltiVec `VPADDSW` etc. |

**Present on x86 and ARM.**
**Example:** `sadd_sat i16 %a, %b` → `i16`

### 4.2 Unsigned Saturating Add/Sub — `uadd_sat`, `usub_sat`

Result clamps to `[0, UINT_MAX]`.

| Arch    | Mnemonic         | Since                                |
|   |      |            --|
| x86     | `PADDUSB/W`      | MMX/SSE                              |
| ARM     | `UQADD` / `UQSUB`| ARMv5E, NEON `VQADD`/`VQSUB`         |
| RISC-V  | —                | Not scalar; vector usable            |
| PowerPC | —                | AltiVec `VPADDUW` etc.               |

**Present on x86 and ARM.**
**Example:** `uadd_sat i16 %a, %b` → `i16`

 

## 5. Absolute Value

### 5.1 Integer Absolute Value — `abs`

| Arch    | Mnemonic        | Since                                |
|   |     --|            --|
| x86     | via `NEG` + `CMOV`, or `PABSB/W/D` (SSSE3 vector) | All |
| ARM     | `ABS`           | ARMv4+, NEON `VABS`                  |
| RISC-V  | —               | Not scalar; `NEG` + `MAX` or `MIN` sequence. Vector in V. |
| PowerPC | `ABS` / `NABS`  | Always present                       |
| MIPS    | `ABS`           | MIPS32/64                            |

**Present on x86, ARM, PowerPC, MIPS.**
**Semantics:** Returns the absolute value (two's complement). Result for
`INT_MIN` is `INT_MIN` (undefined behavior for some ISAs).
**Example:** `abs i32 %x` → `i32`

### 5.2 Floating-Point Absolute Value — `fabs`

| Arch    | Mnemonic        | Since                                |
|   |     --|            --|
| x86     | `ANDPS` with mask, or `VANDPS` | Always |
| ARM     | `FABS`          | VFP, NEON, A64                       |
| RISC-V  | `FABS.S` / `FABS.D` | Always (via FSGNJ)                |
| PowerPC | `XSABSDP`       | VSX, always                          |
| MIPS    | `ABS.S` / `ABS.D` | MIPS-3D, MSA                       |

**Semantics:** Clears the sign bit. `fabs(-3.14)` = `3.14`.
**Example:** `fabs float %x` → `float`

 

## 6. Floating-Point Square Root — `fsqrt`

| Arch    | Mnemonic     | Since                                |
|   |    --|            --|
| x86     | `SQRTSD` / `SQRTSS` | SSE, x87                    |
| ARM     | `FSQRT`      | VFP, A64                             |
| RISC-V  | `FSQRT.S` / `FSQRT.D` | Always present               |
| PowerPC | `XSSQRTDP`  | VSX                                 |
| MIPS    | `SQRT.S` / `SQRT.D` | MIPS-3D, MSA               |

**Example:** `fsqrt float %x` → `float`

 

## 7. Floating-Point Rounding — `floor`, `ceil`, `trunc`, `round`, `nearbyint`

| Op         | x86          | ARM A64     | RISC-V        | PowerPC       |
|    |    -|    -|     |     |
| `floor`    | `ROUNDSS/SD` (SSE4.1) | `FRINTM` | via `FROUND` or FE environment | `XSRDPI` / `XSRDPIM` |
| `ceil`     | `ROUNDSS/SD` | `FRINTP`   | same          | `XSRDPIP`     |
| `trunc`    | `ROUNDSS/SD` | `FRINTZ`   | same          | `XSRDPIZ`     |
| `round`    | `ROUNDSS/SD` | `FRINTA`   | same          | `XSRDPIC`     |
| `nearbyint`| — (via `FRNDINT`) | `FRINTI` | same        | `XSRDPIN`     |

**Semantics:** Each rounds a float to an integer float according to the
specified rounding mode.

 

## 8. Memory Ordering / Fences — `fence`

| Arch    | Mnemonic            | Semantics                           |
|   |       |            --|
| x86     | `MFENCE` / `SFENCE` / `LFENCE` | Full/store/load barrier  |
| ARM     | `DMB` / `DSB`       | Data memory barrier / data sync      |
| RISC-V  | `FENCE` / `FENCE.I` | Ordering + instruction fence         |
| PowerPC | `SYNC` / `ISYNC`    | Synchronize / instruction sync       |
| MIPS    | `SYNC`              | Sync                                 |

**Semantics:** Orders memory operations. Takes ordering arguments:
load-load, load-store, store-store, store-load.
**Example:** `fence` (full barrier), `fence load-store`

 

## 9. Atomic Read-Modify-Write — `atomicrmw`

Full compare-and-swap is present everywhere. Simpler atomic RMW operations
(atomic add, and, or, xor, xchg) are also universally available.

| Operation   | x86              | ARM            | RISC-V         | PowerPC      |
|    -|      |     -|     -|    --|
| `cmpxchg`   | `CMPXCHG`        | `LDREX`/`STREX`, `CAS` (A64) | `LR`/`SC` / `AMOCAS` | `LWARX`/`STWCX` |
| `atomic add`| `XADD` / `LOCK ADD` | `LDREX`/`STREX` or A64 `LDADD` | `AMOADD` | `LARX`/`STCX` loop |
| `atomic and`| `LOCK AND`       | `LDCLR` (A64)   | `AMOAND`       | loop          |
| `atomic or` | `LOCK OR`        | `LDSET` (A64)   | `AMOOR`        | loop          |
| `atomic xor`| `LOCK XOR`       | `LDEOR` (A64)   | `AMOXOR`       | loop          |
| `xchg`      | `XCHG`           | `SWP` (A64)     | `AMOSWAP`      | loop          |

**Example:** `cmpxchg i32* %ptr, %expected, %desired` → `{i32, bool}`

 

## 10. Sign Extension Helpers

### 10.1 Sign Extend — `sext`

Already in the IR as a cast operation (`IR_SEXT`). Present on all ISAs.

### 10.2 Zero Extend — `zext`

Already in the IR as a cast operation (`IR_ZEXT`). Present on all ISAs.

 

## 11. Summary: Recommended Additions to the IR

Based on cross-platform presence analysis, the following instructions
are present on **multiple** major architectures and would be valuable
additions to the IR:

| Priority | Opcode          | Category        | Present On                    |
|   -|     --|     --|          -|
| P0       | `ctpop`         | Bit manipulation| x86, ARM, RISC-V, PPC, MIPS  |
| P0       | `ctlz`          | Bit manipulation| x86, ARM, RISC-V, PPC, MIPS  |
| P0       | `cttz`          | Bit manipulation| x86, ARM, RISC-V, PPC        |
| P0       | `rotl`/`rotr`   | Bit manipulation| x86, ARM, RISC-V, PPC, MIPS  |
| P0       | `bswap`         | Bit manipulation| x86, ARM, RISC-V, PPC        |
| P0       | `smin`/`smax`   | Integer min/max | x86, ARM, RISC-V, PPC        |
| P0       | `umin`/`umax`   | Integer min/max | x86, ARM, RISC-V, PPC        |
| P0       | `fma`           | Float FMA       | x86, ARM, RISC-V, PPC, MIPS  |
| P0       | `abs`           | Integer abs     | x86, ARM, PPC, MIPS          |
| P0       | `fabs`          | Float abs       | x86, ARM, RISC-V, PPC, MIPS  |
| P0       | `fsqrt`         | Float sqrt      | x86, ARM, RISC-V, PPC, MIPS  |
| P0       | `fence`         | Memory barrier  | x86, ARM, RISC-V, PPC, MIPS  |
| P1       | `fmin`/`fmax`   | Float min/max   | x86, ARM, RISC-V, PPC, MIPS  |
| P1       | `floor`/`ceil`/`trunc`/`round` | Float rounding | all |
| P1       | `sadd_sat`/`ssub_sat` | Saturating arith | x86, ARM          |
| P1       | `uadd_sat`/`usub_sat` | Saturating arith | x86, ARM          |
| P1       | `cmpxchg`       | Atomic CAS      | x86, ARM, RISC-V, PPC, MIPS  |
| P1       | `atomicrmw`     | Atomic RMW      | x86, ARM, RISC-V, PPC, MIPS  |
| P2       | `copysign`      | Float sign op   | x86, ARM, RISC-V, PPC        |
| P2       | `ctlz`/`cttz`   | (word variants) | all                           |

### Priority Legend

- **P0** — Present on 5/5 or 4/5 major ISAs; widely used in optimization.
- **P1** — Present on 3+/5 major ISAs; useful but with narrower scope.
- **P2** — Present on 2+/5; niche or available via decomposition.

 

## References

1. Intel SDM Vol. 2 — `POPCNT`, `LZCNT`, `TZCNT`, `BSWAP`, `ROL`/`ROR`,
   `PADDSB/W`, `PADDUSB/W`, `PMINSD/B`, `PMAXSD/B`, `PMINUB`, `PMAXUB`,
   `VFMADD132SS/SD`, `ROUNDSS/SD`, `SQRTSD`, `MFENCE`, `CMPXCHG`, `XADD`

2. ARM ARM (Arm Architecture Reference Manual) — `CLZ`, `RBIT`, `REV`,
   `SMIN`/`SMAX`, `UMIN`/`UMAX`, `FMIN`/`FMAX`, `FMINNM`/`FMAXNM`,
   `FMLA`/`FMADD`, `FRINT*`, `FSQRT`, `FABS`, `DMB`/`DSB`,
   `LDREX`/`STREX`, `LDADD`/`SWP`/`CAS`

3. RISC-V Unprivileged Spec v20250508 — `CPOP`/`CLZ`/`CTZ`/`ROL`/`ROR`
   (Zbb), `GREVI` (Zbb), `MIN`/`MAX`/`MINU`/`MAXU` (Zbb),
   `FMIN.S`/`FMAX.S`, `FMADD.S`, `FSQRT.S`, `FABS.S` (via FSGNJ),
   `AMOADD`/`AMOAND`/`AMOOR`/`AMOXOR`/`AMOSWAP`/`AMOCAS` (A),
   `FENCE` (Ztso)

4. Power ISA v3.1 — `POPCNTD`, `CNTLZD`/`CNTTZD`, `ROTL`/`ROTR`,
   `XSMINDP`/`XSMAXDP`, `XSMADDADP`, `XSABSDP`, `XSSQRTDP`,
   `XSRDPIM/IP/IZ/IC`, `SYNC`/`ISYNC`, `LWARX`/`STWCX`

5. MIPS64 Release 6 — `CLZ`, `POP`, `ROTR`/`ROTRV`, `ABS`,
   `ABS.S`/`ABS.D`, `MADD.S`/`MADD.D`, `SQRT.S`/`SQRT.D`, `SYNC`

6. LLVM Language Reference — `llvm.ctpop.*`, `llvm.ctlz.*`, `llvm.cttz.*`,
    `llvm.bswap.*`, `llvm.fma.*`, `llvm.smin.*`/`llvm.smax.*`, `llvm.umin.*`/
    `llvm.umax.*`, `llvm.fabs.*`, `llvm.sqrt.*`, `llvm.fmuladd.*`,
    `llvm.sadd.sat.*`/`llvm.uadd.sat.*`, `llvm.ssub.sat.*`/`llvm.usub.sat.*`,
    `llvm.fshl`/`llvm.fshr` (generalized rotate), `fence`, `cmpxchg`,
    `atomicrmw`

## Second Wave Instructions

### Multiply High (P0)

Multiply high returns the upper half of a full-width product. Present on 4/5
ISAs (x86, ARM, RISC-V, PowerPC); absent on scalar MIPS64.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `umulhi` | `(a*b) >> N` (unsigned) | `MUL` (RDX) | `UMULH` | `MULHU` (M) | `MULHWU` | — |
| `smulhi` | `(a*b) >> N` (signed) | `IMUL` (RDX) | `SMULH` | `MULH` (M) | `MULHW` | — |
| `mulhi` | signed, single return | — | `SMULH` | `MULH` (M) | `MULHW` | — |

x86 stores the high half in RDX after a widening multiply. ARM AArch64 has
dedicated `SMULH`/`UMULH` (64→128→high 64). RISC-V provides `MULH`/`MULHU`/
`MULHSU` as part of the M extension. PowerPC has `MULHW`/`MULHWU`. Note that
x86 and older ARM (AArch32) produce two separate results (low + high), so a
single-result `umulhi` would require an extra mov or is extractable from the
widening MUL. This is P0 because the operation is impossible to express
efficiently without it (a widening mul + extract high half cannot be
pattern-matched if lowering happens before the full multiply is visible).

### Funnel Shift (P1)

Funnel shift concatenates two values and shifts the combined double-width
value. Present on 3/5 ISAs (x86, ARM, RISC-V Zbb); absent on PowerPC and
MIPS64 scalar.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `fshl` | `fshl(a,b,i) = (a << i) \| (b >> (N-i))` | `SHLD` | `EXTR` | `FSL` (Zbb) | — | — |
| `fshr` | `fshr(a,b,i) = (a >> i) \| (b << (N-i))` | `SHRD` | `EXTR` | `FSR` (Zbb) | — | — |

x86 `SHLD`/`SHRD` takes three registers (dst, src, shift). ARM `EXTR` extracts
an arbitrary bitfield from a concatenated pair. RISC-V Zbb `FSL`/`FSR` are
single-instruction funnel shifts for XLEN. Without a native opcode, funnel
shifts decompose to shifts + or + and, so this is P1 rather than P0.

### Add/Subtract with Carry (P1)

Extended-precision arithmetic using carry-in and carry-out. Present on 3/5
ISAs (x86, ARM, PowerPC); absent on RISC-V scalar and MIPS64.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `adc` | `a + b + carry_in` → (result, carry_out) | `ADC` | `ADCS` | — | `ADDE` | — |
| `sbb` | `a - b - borrow_in` → (result, borrow_out) | `SBB` | `SBCS` | — | `SUBFE` | — |
| `addc` | `a + b` → (result, carry_out) [carry *generate*] | `ADD` (CF) | `ADDS` | — | `ADD.` (CA) | — |
| `subb` | `a - b` → (result, borrow_out) | `SUB` (CF) | `SUBS` | — | `SUBF.` (CA) | — |

x86 sets CF on every ADD/SUB and reads CF via ADC/SBB. ARM sets flags on
`ADDS`/`SUBS` and uses `ADCS`/`SBCS`. PowerPC uses carry bits (`CA`/`CARRY`)
with `ADDE`/`SUBFE` for extended precision. RISC-V scalar explicitly omitted
flags. LLVM does not have scalar `adc`/`sbb` intrinsics at the IR level (it
relies on `addcarry`/`subborrow` only for `i8` via `@llvm.uadd.with.overflow`
patterns). This is P1 because the primary use case is big-integer and crypto
code, which is narrower than general-purpose.

### Absolute Difference (P1)

Compute the absolute value of the difference between two values:
`abs(a - b)`. Present on 2/5 ISAs (ARM with NEON, RISC-V with V extension);
available on x86 via custom sequences or `PSADBW` (only byte- wide sum of
absolute differences, not general elementwise). LLVM added `G_ABDS`/`G_ABDU`
for GlobalISel in late 2024.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `abds` | `abs(a - b)` (signed operands) | — | `SABD` (NEON) | `vabd` (V) | — | — |
| `abdu` | `abs(a - b)` (unsigned operands) | `PSADBW` (byte only) | `UABD` (NEON) | `vabd` (V) | — | — |

On x86, `PSADBW` only sums absolute differences across byte lanes (not
elementwise), and general `abds`/`abdu` requires SUB + ABS or SUB + CMOV +
NEG. Without SIMD or vector registers, this is a multi-instruction sequence.
P2 for scalar, P1 for vector-capable.

### Overflow-Checked Arithmetic (P2)

Perform an operation and also return whether the result overflowed. Present on
2/5 ISAs (x86 and ARM via flag bits); RISC-V and MIPS64 scalar lack overflow
flags; PowerPC has SO/OV but requires `mtxer`/`mfxer`.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `sadd_overflow` | signed add + overflow bit | `ADD` + `JO` | `ADDS` (V) | — | `ADD.` + `MFXER` | — |
| `uadd_overflow` | unsigned add + overflow bit | `ADD` + `JC` | `ADDS` (C) | — | `ADD.` + `MFXER` | — |
| `ssub_overflow` | signed sub + overflow bit | `SUB` + `JO` | `SUBS` (V) | — | `SUBF.` + `MFXER` | — |
| `usub_overflow` | unsigned sub + overflow bit | `SUB` + `JC` | `SUBS` (C) | — | `SUBF.` + `MFXER` | — |
| `smul_overflow` | signed mul + overflow bit | `IMUL` + `JO` | `MUL` + `ADDS`? | — | `MULLW` + check | — |
| `umul_overflow` | unsigned mul + overflow bit | `MUL` + `JC` | `MUL` + check | — | `MULLW` + check | — |

LLVM exposes these as `@llvm.sadd.with.overflow.*` family of intrinsics that
return an `{result, overflow}` struct. On x86 these are efficient because the
overflow flag is a free byproduct of ADD/SUB/MUL (checked with `JO`/`JC`). On
ARM, the V and C flags from `ADDS`/`SUBS` provide the same. RISC-V requires
explicit comparisons (e.g., `add a0,a1,a2; sltu a3,a0,a1` for unsigned
overflow), which is 2-3 instructions. P2 because the lowering is always
expressible but the IR node would prevent the optimizer from reasoning about
the decomposed form.

## Summary Table

| Instruction | Priority | x86 | ARM64 | RISC-V | PPC | MIPS | LLVM IR |
| | | | | | | | |
| `umulhi`/`smulhi` | P0 | ✓ (RDX) | ✓ | ✓ (M) | ✓ | ✗ | extract high from `mul` |
| `fshl`/`fshr` | P1 | ✓ | ✓ | ✓ (Zbb) | ✗ | ✗ | `@llvm.fshl`/`@llvm.fshr` |
| `adc`/`sbb` | P1 | ✓ | ✓ | ✗ | ✓ | ✗ | `@llvm.uadd.with.overflow` + extract |
| `abds`/`abdu` | P1 | ✗ (partial) | ✓ (NEON) | ✓ (V) | ✗ | ✗ | `G_ABDS`/`G_ABDU` (GISel) |
| `*_overflow` | P2 | ✓ | ✓ | ✗ | ✗ | ✗ | `@llvm.*.with.overflow` |

## Updated Recommendation

Same as before: implement **P0 first** (`umulhi`/`smulhi` alongside the earlier
P0 batch), then evaluate **P1** (`fshl`/`fshr`, `adc`/`sbb`, `abds`/`abdu`)
for the second wave based on downstream compiler needs. **P2** (`*_overflow`)
is lowest priority since the decomposition is straightforward and leaving it
visible may hamper optimization.

 

# Privileged (Supervisor-Only) Instructions

These instructions are general-purpose operations that are only available in
supervisor/kernel privilege mode. They must be **gated behind a flag** in the IR
(e.g. `IR_OP_ENABLE_PRIVILEGED` or a separate builder target), since they
cannot be used in user-mode code. Only instructions present as a single native
opcode on **at least 2 of 5** major ISAs (x86, ARM, RISC-V, PowerPC, MIPS) in
privileged mode qualify.

## TLB Invalidate (P0)

Invalidate entries in the translation lookaside buffer. Present on **5/5 ISAs**.
Privileged on **5/5 ISAs**.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `tlb_inval_va` | Invalidate TLB for one VA | `INVLPG` | `TLBI VAE1` | `SFENCE.VMA` | `TLBIEL` | `TLBP` + `TLBWI` |
| `tlb_inval_all` | Invalidate entire TLB | `MOV CR3` | `TLBI VMALLE1` | `SFENCE.VMA` | `TLBIA` | `TLBWR` (walk) |
| `tlb_inval_asid` | Invalidate TLB for one ASID | `INVPCID` | `TLBI ASIDE1` | `SFENCE.VMA` | — | `TLBWI` (mask) |

Each ISA names its TLB-invalidation instruction differently, but the core
operation — *remove stale virtual-to-physical mappings from the hardware cache*
— is universal. The architectural mechanism differs:

- **x86**: `INVLPG` invalidates TLB entries for the page containing the given
  address. `INVPCID` provides finer-grained control (all, single PCID, etc.).
  `MOV CR3` implicitly invalidates non-global TLB entries.
- **ARM**: `TLBI VAE1` invalidates by VA and ASID at EL1. Rich family of
  variants: `VMALLE1` (all), `ASIDE1` (all by ASID), `VAAE1` (all ASIDs by
  VA), with `IS`/`OS` shareability suffixes, and `RVA*` range variants.
- **RISC-V**: `SFENCE.VMA rs1, rs2` acts as both a memory fence and TLB
  invalidate. `rs1=x0` means all addresses; `rs2=x0` means all ASIDs.
  `Svinval` extension adds `SINVAL.VMA` (invalidate without fence) and
  `SFENCE.W.INVAL`/`SFENCE.INVAL.IR` for finer-grained ordering.
- **PowerPC**: `TLBIEL` invalidates a TLB entry for a given effective page
  number. `TLBIA` invalidates all entries. `TLBSYNC` synchronizes TLB
  invalidations across harts.
- **MIPS**: `TLBP` probes the TLB, `TLBR` reads an entry, `TLBWI` writes an
  entry by index, `TLBWR` writes to a random slot. MIPS has a software-managed
  TLB, so TLB invalidation is done by rewriting entries.

This is P0 because TLB shootdown is a fundamental OS primitive that cannot be
expressed without it. Every non-trivial kernel (Linux, FreeBSD, etc.) executes
these instructions thousands of times per second.

## Interrupt Flag Control (P0)

Enable or disable maskable interrupts on the current hart. Present on **5/5
ISAs**. Privileged on **5/5 ISAs**.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `int_disable` | Mask all interrupts | `CLI` | `MSR DAIFSet` | `CSRRSI sstatus.SIE` | `MTMSR` (clear EE) | `DI` |
| `int_enable` | Unmask all interrupts | `STI` | `MSR DAIFClr` | `CSRRCI sstatus.SIE` | `MTMSR` (set EE) | `EI` |
| `int_save_disable` | Read+disable (atomically) | `PUSHF` + `CLI` | `MRS` + `MSR DAIFSet` | `CSRRS sstatus` | `MFMSR` + `MTMSR` | `DI` (returns previous) |

- **x86**: `CLI` clears IF (interrupt flag) at CPL=0. `STI` sets it. Uses
  `PUSHF`/`POPF` to save/restore. Serializing after `STI` (one-instruction
  delay).
- **ARM**: `MSR DAIFSet` with `#2` masks IRQs (I bit). `MSR DAIFClr` with
  `#2` unmasks. Read `DAIF` via `MRS` to save.
- **RISC-V**: S-mode controls `sstatus.SIE` via `CSRRS`/`CSRRC`. Reading
  `sstatus` captures current state atomically. M-mode uses `mstatus.MIE`.
- **PowerPC**: `MTMSR` writes the full MSR; EE bit (bit 15) controls external
  interrupts. `MFMSR` reads the current value. Requires `SYNC`/`ISB` on some
  implementations to take effect.
- **MIPS**: `DI` (disable interrupts) atomically clears IE in CP0 Status and
  returns the previous value. `EI` atomically sets it.

This is P0 because interrupt control is a fundamental kernel primitive. Every
spinlock, critical section, and IRQ handler depends on it.

## Page Table Base / Address Space Switch (P1)

Load the root page-table pointer and (optionally) the address space identifier.
Present on **5/5 ISAs**. Privileged on **5/5 ISAs**.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `write_pt_base` | Set page table base register | `MOV CR3` | `MSR TTBR0_EL1` | `CSRW SATP` | `MTSPR SDR1` | `MTC0 EntryHi`+`Context` |
| `write_asid` | Set address space ID | `MOV CR3` (incl.) | `MSR TTBR0_EL1` (incl.) | `CSRW SATP` (incl.) | `MTSPR PID` | `MTC0 EntryHi` |

- **x86**: `MOV CR3` loads the page-table base address (and optionally a PCID
  in bits 11:0). Implicitly flushes non-global TLB entries.
- **ARM**: `MSR TTBR0_EL1` sets the translation table base for EL1/0. ASID is
  in the lower bits. `TTBR1_EL1` holds the kernel-space table.
- **RISC-V**: `CSRW SATP` writes the supervisor address translation and
  protection register, which includes the page-table base (PPN), ASID, and MODE
  (Sv39/Sv48/etc).
- **PowerPC**: `MTSPR SDR1` sets the page table base address.
  `MTSPR PID` sets the process ID. Book III-S has `PTCR` for process table.
- **MIPS**: No single "page table base" register in classic MIPS (software TLB).
  Instead, `MTC0 EntryHi` sets the VPN/ASID, and individual TLB entries are
  filled via `TLBWI`. `MTC0 Context` provides the page table entry pointer
  for the TLB refill handler.

This is P1 because while all ISAs have it, the semantics diverge
significantly — x86/ARM/RISC-V have a unified page-table base, while MIPS (and
older PowerPC) use a software-managed TLB model. A single IR opcode can
abstract the "start a new address space" concept, but the lowering is
architecture-specific.

## Cache Line Management by Virtual Address (P1)

Flush, clean, or invalidate a single cache line by virtual address. Present on
**5/5 ISAs**. Privileged on **3/5** (ARM, RISC-V, MIPS); available to user
mode on x86 and PowerPC.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `dcache_flush` | Write back + invalidate line | `CLFLUSH` | `DC CIVAC` | `CBO.FLUSH` | `dcbf` | `CACHE` (Hit_Writeback_Inv_D) |
| `dcache_clean` | Write back line (keep valid) | `CLFLUSHOPT` | `DC CVAC` | `CBO.CLEAN` | `dcbst` | `CACHE` (Hit_Writeback_D) |
| `dcache_inval` | Invalidate line (drop data) | (via `CLFLUSH`+ `MFENCE`) | `DC IVAC` | `CBO.INVAL` | `dcbi` | `CACHE` (Hit_Invalidate_D) |
| `icache_sync` | Sync instruction cache | `SERIALIZE` | `IC IVAU` | `FENCE.I` | `icbi` | `CACHE` (Hit_Invalidate_I) |

- **x86**: `CLFLUSH`/`CLFLUSHOPT` are **unprivileged** (available to usermode).
  `CLWB` writes back without invalidating. x86 does not have a direct cache
  invalidate-by-VA (the closest is writing back and relying on coherence).
  `INVD`/`WBINVD` (privileged) operate on the entire cache hierarchy.
- **ARM**: `DC CIVAC`/`DC CVAC`/`DC IVAC` are **privileged** (EL1).
  Operate by virtual address to the Point of Coherency/Unification.
  `IC IVAU` invalidates the instruction cache (EL1).
- **RISC-V**: `CBO.CLEAN`/`CBO.FLUSH`/`CBO.INVAL` (Zicbom extension) are
  **privileged** by default but can be delegated to U-mode via `envcfg` CSRs.
  `FENCE.I` synchronizes the instruction and data streams (not privileged).
- **PowerPC**: `dcbf` (flush) and `dcbst` (clean) are **unprivileged** (Book I
  user-level). `dcbi` (invalidate) is **privileged** (supervisor-level).
  `icbi` is unprivileged.
- **MIPS**: The `CACHE` instruction (CP1) performs various cache operations
  and is **privileged** (kernel mode).

This is P1 because the most common use case — DMA buffer maintenance — is an
OS-level concern. The privilege asymmetry across ISAs means the opcode should
be available but gated: user-mode targets would reject it, kernel-mode targets
would lower it directly.

## Halt CPU (P2)

Stop the processor until the next interrupt. Present on **5/5 ISAs**.
Privileged on **4/5** (x86, RISC-V, PowerPC, MIPS); ARM `WFI` is typically
available but can be trapped.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `halt` | Halt until interrupt | `HLT` | `WFI` | `WFI` | `nap` | `WAIT` |

- **x86**: `HLT` is **privileged** (ring 0). Halts until any enabled
  interrupt, NMI, SMI, or reset. Used in the OS idle loop.
- **ARM**: `WFI` (Wait For Interrupt) is **not privileged** (available from
  EL0), though many OSes trap it from userspace. Halts until any interrupt.
- **RISC-V**: `WFI` is typically **privileged** (S-mode or M-mode), though
  implementations may treat it as a NOP at U-mode. More a hint than a command.
- **PowerPC**: `nap`/`doze`/`sleep` are entered via `MTMSR` power
  management bits. **Privileged**.
- **MIPS**: `WAIT` is **privileged** (kernel mode). Enters a low-power state.

This is P2 because the idle loop is a small piece of kernel code, and the
instruction sequence is trivially short (2-3 instructions inline). Only worth
adding if the compiler is doing kernel-level optimization or code generation.

## Whole-Cache Management (P2)

Operate on all or large portions of the cache hierarchy. Present on **4/5
ISAs** (no RISC-V standard). Privileged on **4/4**.

| Mnemonic | Semantics | x86 | ARM | RISC-V | PPC | MIPS |
| | | | | | | |
| `cache_wbinvd` | Write back + invalidate all caches | `WBINVD` | `DC CISW` | — | `dcbf` (all) | `CACHE` (Index_Writeback_Inv_D) |
| `cache_invd` | Invalidate all caches (no writeback) | `INVD` | — | — | `dcbi` (all) | `CACHE` (Index_Invalidate_D) |

- **x86**: `WBINVD` writes back all modified cache lines then invalidates.
  `INVD` invalidates without writeback (data loss risk). Both **privileged**.
- **ARM**: `DC CISW` performs clean+invalidate by set/way. Must iterate over
  all sets and ways. **Privileged** (EL1).
- **RISC-V**: No standard whole-cache flush instruction. Use `CBO.FLUSH`
  per-line in a loop.
- **PowerPC**: `dcbf` with `RA=0` and `RB` holding the effective address can
  flush all lines. `dcbi` invalidates (supervisor-level).
- **MIPS**: `CACHE` with index operations iterates by set/way.
  **Privileged** (kernel mode).

This is P2 because `WBINVD`/`DC CISW` are tremendously expensive
(millions of cycles) and used only in suspend/resume, crash recovery, or
firmware code.

# Privileged Summary Table

| Instruction | Priority | x86 | ARM64 | RISC-V | PPC | MIPS | Privileged (count) |
| | | | | | | | |
| `tlb_inval_va` | P0 | ✓ | ✓ | ✓ | ✓ | ✓ | 5/5 |
| `int_disable`/`int_enable` | P0 | ✓ | ✓ | ✓ | ✓ | ✓ | 5/5 |
| `write_pt_base` | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | 5/5 |
| `dcache_flush`/`dcache_clean`/`dcache_inval` | P1 | ✓ (unpriv) | ✓ | ✓ | ✓ (unpriv) | ✓ | 3/5 |
| `icache_sync` | P1 | ✓ (unpriv) | ✓ | ✓ (unpriv) | ✓ (unpriv) | ✓ | 2/5 |
| `halt` | P2 | ✓ | ✓ (unpriv) | ✓ | ✓ | ✓ | 4/5 |
| `cache_wbinvd`/`cache_invd` | P2 | ✓ | ✓ | — | ✓ | ✓ | 4/4 |

# Updated Recommendation (with privileged ops)

The implementation plan expands to three waves, with the privileged flag
(`IR_PRIVILEGED` or similar) gating the latter:

1. **Wave 1 — P0 unprivileged**: `ctpop`, `ctlz`, `cttz`, `rotl`/`rotr`,
   `bswap`, `smin`/`smax`, `umin`/`umax`, `fma`, `abs`, `fabs`, `fsqrt`,
   `fence`, `umulhi`/`smulhi`.
2. **Wave 2 — P1 unprivileged + P0 privileged**:
   - Unprivileged: `fshl`/`fshr`, `adc`/`sbb`, `abds`/`abdu`.
   - Privileged (behind `IR_PRIVILEGED`): `tlb_inval_va`, `int_disable`/
     `int_enable`, `write_pt_base`.
   - Both: `dcache_flush`/`dcache_clean`/`dcache_inval` (non-privileged
     backends can lower as inline sequences).
3. **Wave 3 — P2 everything else**: `*_overflow`, `halt`, `cache_wbinvd`,
   `icache_sync`.

The privileged opcodes should coexist in `IrOpcode` but the builder /
frontend should reject them unless `ir_builder_set_privileged(b)` has been
called. The printer should annotate them (e.g. `[priv] tlb_inval_va %0`).