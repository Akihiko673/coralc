# Coral Programming Language

Coral is a systems programming language that combines C's mental model, hardware access, and predictable performance with modern features like type safety, generics, traits, and explicit error handling—all without introducing hidden control flow or an intrusive runtime.

---

## Language Philosophy and Core Constraints

Every feature in Coral must satisfy three primary constraints:

* **Preserve the C mental model:** If a feature requires unlearning how memory and the machine work, it does not belong in Coral.
* **No hidden machinery:** Nothing runs behind your back. There are no implicit allocations, invisible control flow paths, or garbage collection pauses.
* **Visible cost:** The price of a feature—whether a copy, an allocation, a dynamic dispatch, or a check—is explicitly written in the source code.

---

## Key Features

* **Type-First Syntax:** Variable and function declarations place the type before the identifier, aligning with standard C declaration styles to emphasize contracts and type readability.
* **Zero-Cost Abstractions:** Struct methods, monomorphized generics, and trait-based polymorphism compile down to direct, specialized machine code with zero runtime overhead.
* **Explicit Error Handling:** Uses `Result<T, E>` and `Option<T>` types instead of exceptions or `null` values, ensuring control flow and potential failures are always visible.
* **Manual and Safe Memory Control:** Offers full control over stack and heap allocations, custom allocators, explicit smart pointer types, and automated scope cleanup via the `Drop` trait.
* **No Hidden Runtime:** Compiles directly to native machine code without a garbage collector, virtual machine, or mandatory background thread system.
* **Modern Tooling Built In:** Built-in module system, compile-time evaluation (`comptime`), and a comprehensive standard library for graphics, networking, data structures, and cross-platform abstractions.

---

## Getting Started

### Prerequisites

* A C-compatible compiler toolchain or the official `coralc` compiler executable.
* Supported Operating Systems: Linux, macOS, Windows, FreeBSD.

### Hello World Example

Create a file named `main.crl`:

```coral
mod std = import("std*");

i32 main()
{
    std.print("Hello from Coral.\n");
    return 0;
}

```

### Compiling and Running

Build and execute the binary using the Coral toolchain:

```bash
coralc main.crl -o main
./main

```

---

## Language Overview

### Type-First Declarations

Coral places the type first in all variable and function declarations to keep types aligned and easily scannable along the left margin.

```coral
pub struct Circle
{
    f64 radius;
    f64 center_x;
    f64 center_y;
}

pub u32 clamp(u32 value, u32 low, u32 high)
{
    if (value < low)
    {
        return low;
    }
    if (value > high)
    {
        return high;
    }
    return value;
}

```

### Methods on Structs

Methods are defined within the body of a `struct`. The receiver instance, `self`, is explicitly defined and passed like any other parameter, avoiding hidden `this` pointers.

```coral
pub struct Rect
{
    f64 left;
    f64 right;
    f64 bottom;
    f64 top;

    pub bool contains(f64 x, f64 y)
    {
        return x >= self.left && x <= self.right &&
               y >= self.bottom && y <= self.top;
    }
}

```

### Explicit Error Handling

Instead of throwing exceptions, functions return a `std.Result<T, E>` type. Errors are treated as normal values that must be inspected or propagated explicitly.

```coral
mod std = import("std*");

pub std.Result<u64, std.strView> parse_count(std.strView text)
{
    bool ok = false;
    u64 value = std.parseU64(text, &ok);
    if (!ok)
    {
        return std.Result<u64, std.strView>::err("the text is not a number");
    }
    return std.Result<u64, std.strView>::ok(value);
}

i32 main()
{
    var result = parse_count("42");
    if (result.isOk())
    {
        std.print("parsed the count\n");
    }
    else
    {
        std.print("the count was invalid\n");
    }
    return 0;
}

```

### Traits and Monomorphized Generics

Polymorphism in Coral is capability-based via traits, rather than inheritance-based. Generics are fully monomorphized at compile time to produce specialized code identical to hand-written functions.

```coral
trait Shape
{
    f64 area();
    f64 perimeter();
}

pub f64 total_area!<Shape T>(vec.vec<T> shapes)
{
    f64 total = 0.0;
    for (u64 i = 0u; i < shapes.len; i = i + 1u)
    {
        total = total + shapes.at(i).area();
    }
    return total;
}

```

---

## Cost Model

Coral operates on a strict "you get what you write" guarantee:

| Operation | Implementation | Visible Cost |
| --- | --- | --- |
| **Method Call** | Direct function call with `self` parameter | Zero vtable lookup or dispatch indirection |
| **Generics** | Monomorphized compile-time templates | Increased binary size, zero runtime overhead |
| **Memory Allocation** | Explicit allocator call | Tracked directly at the call site |
| **Control Flow** | Standard branches, loops, and function returns | No unwinding, hidden throws, or GC interruptions |
