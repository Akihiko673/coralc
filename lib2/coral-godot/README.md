# examples

Example `.crl` files showing how to use the generated Godot bindings.

## The parts

- `godot/types.crl` — C API types: scalars (`GInt`, `GBool`), distinct pointer
  types, enums, fn-pointer types, and the ABI structs (PropertyInfo,
  ClassInfo6, ...).
- `godot/interface.crl` — the `Interface` struct: one fn-pointer slot per
  engine entry point, filled at load by `grab`/`init()` via `get_proc_address`.
- `godot/classes.crl` — generated from `extension_api.json`:
  - one typed fn-pointer slot + hash const per method (`NodeGetName`,
    `NodeGetNameHash`),
  - class constants (`NodeNotificationReady`), enums (`NodeProcessMode`),
  - singleton slots, utility function slots, `Variant.Type`/`Variant.Operator`.
- `godot/entry.crl` — the symbol the engine dlopens: `gdextension_entry_point`.

## The flow (how it all connects)

1. Godot dlopens your `.so` and calls `gdextension_entry_point`.
2. `inf.init(&g_interface, getProcAddress)` resolves every engine fn-pointer
   from Godot by name — the loader strings are verbatim from the header.
3. Your code resolves method binds from the generated classes with
   `classdb_get_method_bind` + the generated hash, stores them in the generated
   typed slots.
4. You call through the interface with plain pointers. Godot's inheritance is
   engine-side: every class is one `ObjectPtr` at the boundary, so one slot set
   works for the whole hierarchy.

## Files

| file | shows |
| --- | --- |
| `hello_entry.crl` | minimal extension entry point (proven pattern from `entry.crl`) |
| `method_call.crl` | resolving a generated bind and calling it on an object |
| `singleton.crl` | grabbing a global singleton and calling a method on it |
| `register_class.crl` | registering a new engine class via `ClassInfo6` + callbacks |
| `custom_wrapper.crl` | the user-code pattern: trait + composition over a generated class |

Example `.gdextension` (sidecar next to your `.so`):

```
[configuration]
entry_symbol = "gdextension_entry_point"

[libraries]
linux.debug.x86_64   = "libmyext.so"
```