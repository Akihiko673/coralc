I read through the wallvm files. Here are the issues I found, with a focus on generic-related problems and a few other bugs:

---

### 1. **Generic `dealloc<T>` under-frees every array in wallvm** (systematic, affects every file)

`std/memory/mman.crl` defines:

```coral
pub void dealloc<T>(T* ptr)
{
    munmap(ptr, sizeof(T));
}
```

But `alloc<T>` takes a **count**:

```coral
pub T* alloc<T>(u64 count)
{
    return (T*)mmap(null, count * sizeof(T), ...);
}
```

`dealloc<T>` only unmaps `sizeof(T)` bytes — **one element** — but wallvm uses it to free entire arrays everywhere. Every growable vector pattern is broken:

- `ir_types.crl`: `mman.dealloc<IrType*>(self.types)` — allocated `newCap * sizeof(IrType*)`, freed `sizeof(IrType*)`
- `ir_builder.crl`: `mman.dealloc<ir_types.IrValue*>(ops)` — allocated `nops * sizeof(IrValue*)`, freed `sizeof(IrValue*)`
- `lsra.crl`: `mman.dealloc<u32>(self.regForVreg)`, `mman.dealloc<LiveInterval>(self.intervals)`, etc. — all under-free
- `x86_64.crl`: `mman.dealloc<u32>(self.stackSlots)`, `mman.dealloc<u32>(self.intHolds)` — same
- `domtree.crl`: `mman.dealloc<u32>(stack)`, `mman.dealloc<u32>(state)` — same

`mman.realloc<T>` has the same bug internally (it calls `dealloc<T>(ptr)` at the end).

---

### 2. **`mman.free` does not exist — called in `asm_rules.crl`**

In `lib2/wallvm/rules/asm_rules.crl`:

```coral
void deinit()
{
    mman.free(self.rules);
    ...
}
```

`mman` has no `free` function. It has `dealloc`, `alloc`, `copy`, and `realloc`. `libc.free` exists in `std/platform/libc.crl`, but this is calling `mman.free`. This should be `mman.dealloc<AsmRule>(self.rules)` (which would still under-free due to issue #1, but at least it would compile).

---

### 3. **Parser ambiguity / GLR state explosion from generic syntax**

The TODOs explicitly list `wallvm/ir_types.crl` and `wallvm/rules/asm_rules.crl` as two of the three files causing GLR state explosion. The reason is obvious once you read them: generic instantiations like

```coral
mman.alloc<IrType*>(newCap)
mman.copy<IrType*>(newTypes, self.types, self.ntypes)
```

use `<` immediately after an identifier. The parser cannot tell whether `<` starts a generic argument list or is a less-than comparison without unbounded lookahead. These files are dense with both patterns (`if (a < b)` and `foo<T>(x)`), so the GLR parser explodes.

---

### 4. **Inconsistent explicit-`self` method signatures in `lsra.crl`**

Most methods in Coral use implicit `self`, e.g.:

```coral
void grow(u32 n) { ... self.outCap ... }
```

But in `lsra.crl`, several methods inside `LinearScanRegAlloc` declare the receiver type as an explicit unnamed parameter:

```coral
void ensureVregs(LinearScanRegAlloc*, u32 vreg)
void ensureIntervals(LinearScanRegAlloc*)
void ensureSlotAllocas(LinearScanRegAlloc*, i32 slot)
void assignVregs(LinearScanRegAlloc*, ir_types.IrFunc* func)
```

while other methods in the same struct (like `scanClass`, `linearScan`, `destroy`) do **not** declare it. This inconsistency is either a syntax error or a half-finished migration to explicit receiver parameters.

---

### 5. **Float register allocation bug in `lsra.crl`**

In `linearScan`:

```coral
self.scanClass(cur, self.floatRegIsFree, self.floatActive,
               &self.numFloatActive, self.numFloatRegs, self.numFloatRegs);
```

The last argument is `calleeStart`. For integers it is `self.numCallerSave`; for floats it is `self.numFloatRegs`. Inside `scanClass`:

```coral
u32 searchStart = cur->spansCall ? calleeStart : 0;
```

When `calleeStart == regCount == self.numFloatRegs`, the search loop  
`for (u32 r = searchStart; r < regCount; r++)` never executes. So **any float value live across a call is always spilled**, even when free float registers exist. There are no callee-save float registers in the ABI tables, so `calleeStart` should be `0` (or the split between caller-save and callee-save should be tracked for floats too).

---

### 6. **Missing `dealloc` of old arrays in `x86_64.crl` `externSym`**

```coral
void externSym(const char* name)
{
    ...
    if (self.externNamesLen == self.externNamesCap)
    {
        u32 nc = ...;
        const char** nb = mman.alloc<const char*>(nc);
        for (u32 i = 0; i < self.externNamesLen; i++) nb[i] = self.externNames[i];
        self.externNames = nb;
        self.externNamesCap = nc;
    }
    ...
}
```

The old `self.externNames` array is reassigned without `mman.dealloc<const char*>(self.externNames)` first. Memory leak on every resize. Same pattern appears in `setIntHold` and `setFloatHold` (though those use `mman.alloc<u32>` and orphan the old array).

---

### Summary

The biggest issue is **#1**: `dealloc<T>` is fundamentally mismatched with `alloc<T>(count)`. Because Coral's generics are monomorphized, `sizeof(T)` is a compile-time constant inside `dealloc`, but the runtime count is lost. Every vector/growable-array pattern in wallvm is affected. The fix would be either:
- Make `dealloc` take a count: `dealloc<T>(T* ptr, u64 count)`
- Or add a separate `deallocArray<T>(T* ptr, u64 count)` and use it everywhere arrays are freed.