## Semantic Differences

```
@reorder        → Rearrange members (largest first) + natural padding
@packed         → No reordering, remove all padding between members
@reorder_packed → Reorder members (largest first), then pack with no padding
```

## Memory Layout Examples

Given:
```
struct S {
    char a;
    int b;
    double d;
}
```

**Default (no attribute):**
```
offset 0:    a (1 byte)
offset 1-3:  padding
offset 4-7:  b (4 bytes)
offset 8-15: d (8 bytes)
Total: 16 bytes
```

**@reorder:**
```
offset 0-7:  d (8 bytes)
offset 8-11: b (4 bytes)
offset 12:   a (1 byte)
offset 13-15: padding
Total: 16 bytes (same size, but reordered)
```

**@packed:**
```
offset 0:    a (1 byte)
offset 1-4:  b (4 bytes, misaligned!)
offset 5-12: d (8 bytes, misaligned!)
Total: 13 bytes (but risky—slow unaligned access)
```

**@reorder_packed:**
```
offset 0-7:  d (8 bytes)
offset 8-11: b (4 bytes)
offset 12:   a (1 byte)
Total: 13 bytes (same as @packed, but no wasted space with reordering)
```

## Implementation Strategy

In your compiler, you need:

### 1. **Parsing Phase**
Store which attribute the struct has:
```
struct_def {
    name: "S"
    layout_mode: @reorder_packed  // or @packed, @reorder, default
    fields: [...]
}
```

### 2. **Layout Calculation Phase**

```pseudocode
function calculate_layout(struct_def, mode):
    fields = struct_def.fields
    
    if mode == @reorder or @reorder_packed:
        fields = sort_by_size_descending(fields)
    
    layout = []
    current_offset = 0
    
    for field in fields:
        alignment = get_alignment(field.type)
        
        if mode == @packed or @reorder_packed:
            // No padding
            field.offset = current_offset
        else:
            // Add padding to alignment boundary
            padding = (alignment - (current_offset % alignment)) % alignment
            current_offset += padding
            field.offset = current_offset
        
        layout.append(field)
        current_offset += field.size
    
    // Struct alignment
    struct_alignment = max(alignment of all fields)
    if mode != @packed and mode != @reorder_packed:
        trailing_padding = (struct_alignment - (current_offset % struct_alignment)) % struct_alignment
        current_offset += trailing_padding
    
    return layout, current_offset
```

### 3. **Code Generation Phase**

When emitting field offsets (for pointer arithmetic, member access):

```c
// For @reorder or @reorder_packed, emit the reordered field offsets
// For @packed, emit tight offsets
// Track alignment for generated load/store instructions
```

### 4. **Semantic Checks**

**Warning for @packed:**
```
⚠️  struct S with @packed: field 'b' is misaligned (offset 1, needs 4-byte alignment)
    This may cause slow unaligned access on some architectures
```

**Consider issuing for @reorder_packed too:**
```
ℹ️  struct S with @reorder_packed: reordered from [a, b, d] to [d, b, a]
    Size reduced from 16 to 13 bytes
```

## Design Considerations

**1. Should @reorder affect field declaration order in source?**
- **Option A**: Yes—users see reordered fields in error messages
- **Option B**: No—preserve declaration order for readability, internally track layout order

I'd recommend **Option B**: keep source order for debugging, track layout order separately.

**2. Can you reorder across visibility boundaries (public/private)?**
```
@reorder
struct S {
    public int x;
    private char y;
}
```

Probably yes—reordering should be transparent to users (they don't rely on order). But document it clearly.

**3. Interaction with arrays?**
```
S arr[10];
```

With `@reorder` or `@reorder_packed`, the struct size changes, so array element spacing changes. This is fine—just ensure element alignment is correct.

**4. Nested structs?**
```
@reorder
struct Outer {
    Inner in;
    int x;
}
```

The `Inner` struct keeps its own layout (respects its own attributes). `Outer` reorders based on its members' *sizes*, not internal structure.

## TL;DR for Your Compiler

- **@reorder**: Sort members by size descending, keep natural alignment + padding
- **@packed**: No reordering, remove all padding (risky but compact)
- **@reorder_packed**: Sort + remove padding (best of both for most cases)

Track layout separately from declaration order. Emit warnings for @packed misalignment. Test with nested structs and arrays.
## Architecture

### 1. AST Representation

```
StructDef {
    name: string
    attributes: [Attribute]  // @reorder, @packed, @reorder_packed
    visibility: Visibility    // pub or private (module-level)
    members: [StructMember]   // original declaration order
    generic_params: [TypeParam]
}

StructMember {
    name: string
    type: Type
    declared_index: int       // source order
}
```

### 2. Layout Calculation Phase

After type checking (you know all member types and sizes):

```pseudocode
function calculate_layout(struct_def):
    members = struct_def.members
    layout_mode = extract_layout_attribute(struct_def.attributes)
    
    // Step 1: Determine member order
    if layout_mode in [@reorder, @reorder_packed]:
        members = sort_by_alignment_desc(members)
        members = stable_sort_by_size_desc(members)  // within same alignment
    
    // Step 2: Assign offsets
    layout = []
    current_offset = 0
    max_alignment = 1
    
    for member in members:
        alignment = get_type_alignment(member.type)
        max_alignment = max(max_alignment, alignment)
        
        if layout_mode not in [@packed, @reorder_packed]:
            // Natural alignment: add padding
            padding_needed = (alignment - (current_offset % alignment)) % alignment
            current_offset += padding_needed
        
        member.offset = current_offset
        layout.append(member)
        current_offset += get_type_size(member.type)
    
    // Step 3: Struct size (trailing padding)
    if layout_mode not in [@packed, @reorder_packed]:
        struct_alignment = max_alignment
        trailing_padding = (struct_alignment - (current_offset % struct_alignment)) % struct_alignment
        total_size = current_offset + trailing_padding
    else:
        total_size = current_offset  // no trailing padding
    
    return {
        layout: layout,
        size: total_size,
        alignment: max_alignment
    }
```

### 3. Store Layout Metadata

```
StructLayout {
    struct_def: StructDef
    member_layouts: Map<member_name, MemberLayout>
    total_size: int
    alignment: int
}

MemberLayout {
    offset: int
    size: int
    alignment: int
    original_index: int    // for debugging
}
```

### 4. Codegen Integration

When generating field access:

```pseudocode
function codegen_field_access(struct_type, field_name, base_ptr):
    layout = get_struct_layout(struct_type)
    member_layout = layout.member_layouts[field_name]
    
    // Emit: base_ptr + member_layout.offset
    return ptr_add(base_ptr, member_layout.offset)
```

For arrays:

```pseudocode
function codegen_array_index(struct_type, index):
    layout = get_struct_layout(struct_type)
    element_size = layout.total_size
    
    // Emit: array_base + (index * element_size)
    return ptr_add(array_base, mul(index, element_size))
```

### 5. Comptime Support

```pseudocode
builtin @offsetof(Type, field_name):
    if not is_struct(Type):
        error("@offsetof requires struct type")
    
    layout = get_struct_layout(Type)
    if field_name not in layout.member_layouts:
        error("field not found in struct")
    
    return const_value(layout.member_layouts[field_name].offset)

builtin @sizeof(Type):
    return const_value(get_type_size(Type))
```

### 6. Diagnostics

**For @packed (warn about misalignment):**
```
for member in layout:
    if member.alignment > 1 and (member.offset % member.alignment) != 0:
        warn("member '%s' is misaligned at offset %d (needs %d-byte alignment)",
             member.name, member.offset, member.alignment)
```

**For @reorder (info about reordering):**
```
if any member moved:
    info("struct '%s': reordered from [%s] to [%s], size %d → %d bytes",
         struct_def.name,
         join(original_order),
         join(reordered),
         original_size,
         new_size)
```

### 7. Edge Cases

**Nested structs:**
```
@reorder
struct Outer {
    Inner inner;  // Inner keeps its own layout
    i32 x;
}
```
The `Inner` type has its own `StructLayout`. `Outer`'s layout treats it as an opaque block of `sizeof(Inner)` bytes with `alignof(Inner)` alignment.

**Generics:**
```
@reorder
struct Vec<T> {
    T* ptr;
    usize len;
    usize cap;
}
```
Each monomorphization (`Vec<i32>`, `Vec<f64>`, etc.) gets layout calculated independently. The pointer type doesn't affect the struct layout calculation (it's always pointer-sized).

**Zero-sized structs:**
```
struct Unit { }
```
Size = 0, alignment = 1. Layout is trivial.

---

That's the full strategy. The key insight: **layout calculation is separate from codegen**—compute it once per struct type, then reuse during code generation and comptime introspection.

the syntax is simply,

"[[reorder]]", or "[[reorder]]", or to use both, "[[reorder, packed]]"

this should already be supported by the fron end? right?