# Coral Standard Library — Compatibility Guide

## WallVM Native Codegen Status

WallVM now generates native code for 10 platforms directly from Coral IR,
bypassing the C bootstrap. All 53 IR opcodes are handled by all codegens.

### Stdlib Feature Support — WallVM

| Feature | WallVM Status | Notes |
|---------|--------------|-------|
| `extern("lib")` | ✅ `ffi/extern.crl` | ExternLib, FfiCtx, linker directives |
| `@noret` / `!return` | ✅ `IrOpcode::Noret` | Platform termination via `noretTemplate()` |
| `@abi("sysv"\|"win64"\|...)` | ✅ `asm_rules.crl` | 20+ calling conventions |
| Function calls | ✅ All codegens | Direct + indirect, extern name passthrough |
| `void _start()` | ✅ `startup_templates.crl` | Per-platform entry points |
| Generic types | External (IR level pending) | Awaiting wallvm IR generics pass |
| Struct methods | External | Awaiting struct layout in IR |
| `defer` | External | Awaiting IR transform pass |
| `asm` inline | External | Awaiting inline asm IR node |
| `const` qualifier | External | Awaiting type system in IR |
| `@packed` / `@align(N)` | External | Awaiting struct layout pass |

### C Bootstrap Compatibility

The `tests/simple/` suite validates the C bootstrap compiler:
modules, exports, functions, arithmetic, control flow, calls, externs.

Phase 2 modules (char, math, mman, option, result) compile under the C
bootstrap but may have issues due to known bugs (monomorphization, struct methods).
