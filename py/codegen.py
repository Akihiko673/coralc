import os
import re
from coral_ast import *

TYPE_MAP = {
    'i8': 'int8_t',
    'i16': 'int16_t',
    'i32': 'int32_t',
    'i64': 'int64_t',
    'u8': 'uint8_t',
    'u16': 'uint16_t',
    'u32': 'uint32_t',
    'u64': 'uint64_t',
    'f32': 'float',
    'f64': 'double',
    'bool': 'bool',
    'char': 'char',
    'void': 'void',
    'string': 'String',
    'strView': 'strView',
}

BUILTIN_INCLUDES = {}

INTRINSIC_MAP = {
    'snprintf': 'snprintf',
    'strlen': 'strlen',
    'memcpy': 'memcpy',
    'memmove': 'memmove',
    'memset': 'memset',
    'memcmp': 'memcmp',
    'fflush': 'fflush',
    'strcmp': 'strcmp',
    'strcpy': 'strcpy',
    'rename': 'rename',
}

HEADER = '''\
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <assert.h>
'''

# libc functions the generated code may call. We never include their
# headers — the prototypes below are emitted into the generated .c and
# the symbols are resolved by linking libc. `unsigned long` matches
# size_t on all supported platforms without needing stddef.h.
LIBC_FUNC_PROTOS = {
    'memcmp': 'int memcmp(const void* s1, const void* s2, unsigned long n);',
    'memcpy': 'void memcpy(void* dst, const void* src, unsigned long n);',
    'memmove': 'void memmove(void* dst, const void* src, unsigned long n);',
    'memset': 'void memset(void* dst, int c, unsigned long n);',
}

_ASM_TYPE_RE = re.compile(
    r'\b(' + '|'.join(sorted(TYPE_MAP, key=len, reverse=True)) + r')\b')


def _asm_type_fix(text):
    """Replace Coral type names in inline asm operand casts
    (e.g. `(u64)addr` -> `(uint64_t)addr`)."""
    return _ASM_TYPE_RE.sub(lambda m: TYPE_MAP[m.group(1)], text)

class CodegenError(Exception):
    pass

class Codegen:
    def __init__(self, module_name='main', output_dir='.'):
        self.module_name = module_name
        self.output_dir = output_dir
        self.header_lines = []
        self.source_lines = []
        self.indent_level = 0
        self._structs_seen = set()
        self._structs_emitted = set()
        self._funcs_declared = set()
        self._funcs_defined = set()
        self._globals_declared = set()
        self._current_struct = None
        self._loop_depth = 0
        self._var_types = {}
        self._ptr_vars = set()
        self._func_return_types = {}
        self._struct_field_types = {}
        self._struct_methods = {}
        self._struct_static_methods = {}  # struct name -> set of method names
        self._method_arities = {}  # (struct, method) -> set of C param counts
        self._imports = set()
        self._builtin_types_used = set()
        self._defer_stack = []  # stack of (stmt_body, indent)
        self._all_structs = {}  # name -> DeclStruct
        self._structs_methods_emitted = set()
        self._func_forward_decls = []  # (ret_type, fn_name, param_str) tuples
        self._extern_forward_decls = []  # same format
        self._method_forward_decls = []  # (ret_type, fn_name, param_str) for struct methods
        self._func_param_types = {}  # fn_name -> list of C type strings
        self._module_aliases = set()  # import aliases (e.g. 'vec', 'mman')
        self._const_names = set()  # names of compile-time const decls
        self._exported_vars = []  # (header_line, ) deferred until structs emitted
        self._uses_mem_builtins = False  # memcpy/memmove/memset/memcmp used
        self._used_libc_funcs = set()  # libc funcs called by generated code
        self._extern_names = set()  # extern decl names (never mangled)
        self._extern_declared = set()  # externs already emitted as prototypes
        self._enum_names = set()
        self._enum_base_names = {}  # bare enum name -> mangled name  # mangled enum names for variant access
        self._fnptr_typedefs = set()  # mangled names of fn-pointer typedefs
        self._struct_field_c = {}  # (struct, field) -> C type string
        self._var_type_exprs = {}  # local/param name -> type expression
        self._struct_ptr_fields = set()  # (struct, field) pointer/array fields

    def indent(self):
        return '    ' * self.indent_level

    def emit_h(self, line=''):
        self.header_lines.append(line)

    def emit_c(self, line=''):
        self.source_lines.append(self.indent() + line)

    def emit_raw_c(self, line):
        self.source_lines.append(line)

    def resolved_type_name(self, typ):
        if isinstance(typ, TypePointer):
            return self.resolved_type_name(typ.base)
        if isinstance(typ, TypeIdent):
            if typ.name == 'self':
                return self._current_struct or 'void*'
            return typ.name
        if isinstance(typ, TypeArray):
            return self.resolved_type_name(typ.base)
        if isinstance(typ, TypeGeneric):
            parts = [typ.name.replace('::', '_').replace('.', '_')]
            for a in typ.args:
                parts.append(self._type_suffix(a))
            return '_'.join(parts)
        return ''

    # Type Translation

    _CONSTRUCTOR_NAMES = ('new', 'fromView', 'fromCstr', 'fromParts', 'withCap', 'fromParts', 'some', 'none')

    def _method_def_arity(self, sn, m):
        """Number of C parameters a method definition takes (incl. implicit self)."""
        params = m.params or []
        has_explicit_self = any(p.name in ('self', 'this') for p in params)
        is_constructor = m.name in self._CONSTRUCTOR_NAMES
        # Coral methods may declare self as an unnamed first param
        # (e.g. `void ensureVregs(LinearScanRegAlloc*, u32 vreg)`).
        first_unnamed = bool(params) and not (params[0].name or '').strip()
        explicit_self = has_explicit_self or (
            first_unnamed and not getattr(m, 'static', False) and not is_constructor)
        implicit_self = bool(sn) and not getattr(m, 'static', False) and not explicit_self and not is_constructor
        return len(params) + (1 if implicit_self else 0)

    def _register_method_arity(self, sn, m):
        self._method_arities.setdefault((sn, m.name), set()).add(
            self._method_def_arity(sn, m))

    def _method_c_name(self, sn, method, arity=None):
        """C name for a struct method. Overloaded method names get an
        `_N` arity suffix so distinct signatures don't collide."""
        base = f'{sn}_{method}'
        arities = self._method_arities.get((sn, method))
        if arities and len(arities) > 1:
            return f'{base}_{arity}'
        return base

    def type_to_c(self, typ):
        if isinstance(typ, TypeIdent):
            name = typ.name
            if name == 'self':
                return self._current_struct or 'void*'
            if name in TYPE_MAP:
                self._builtin_types_used.add(name)
                return TYPE_MAP[name]
            return name.replace('::', '_').replace('.', '_')
        if isinstance(typ, TypePointer):
            base = self.type_to_c(typ.base)
            # fn-pointer typedefs (typedef bool (*PassFn)(...)) already
            # contain the pointer: `PassFn*` in Coral is the same thing.
            if isinstance(typ.base, TypeIdent) and typ.base.name in self._fnptr_typedefs:
                return base
            if typ.const:
                return f'const {base}*'
            return f'{base}*'
        if isinstance(typ, TypeArray):
            base = self.type_to_c(typ.base)
            if typ.size:
                return f'{base}[{self.expr_to_c(typ.size)}]'
            return f'{base}*'
        if isinstance(typ, TypeGeneric):
            base = typ.name.replace('::', '_').replace('.', '_')
            args = '_'.join(self._type_suffix(a) for a in typ.args)
            return f'{base}_{args}'
        if isinstance(typ, TypeFunc):
            ret = self.type_to_c(typ.return_type) if typ.return_type else 'void'
            params = ', '.join(self.type_to_c(p) for p in typ.param_types)
            return f'{ret}(*)({params})'
        return 'void*'

    def decl_type_str(self, typ, name):
        if isinstance(typ, TypeArray):
            dims = []
            inner = typ
            while isinstance(inner, TypeArray):
                if inner.size:
                    dims.append(f'[{self.expr_to_c(inner.size)}]')
                else:
                    dims.append('[]')
                inner = inner.base
            base = self.type_to_c(inner)
            return f'{base} {name}{"".join(dims)}'
        if isinstance(typ, TypeFunc):
            ret = self.type_to_c(typ.return_type) if typ.return_type else 'void'
            params = ', '.join(self.type_to_c(p) for p in typ.param_types)
            return f'{ret} (*{name})({params})'
        return f'{self.type_to_c(typ)} {name}'

    def expr_to_c(self, expr):
        if isinstance(expr, ExprInt):
            return str(expr.value) + getattr(expr, 'suffix', '')
        if isinstance(expr, ExprFloat):
            return str(expr.value)
        if isinstance(expr, ExprString):
            escaped = expr.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
            return f'"{escaped}"'
        if isinstance(expr, ExprChar):
            v = expr.value
            if v == 0: return "'\\0'"
            if v == 9: return "'\\t'"
            if v == 10: return "'\\n'"
            if v == 13: return "'\\r'"
            if v == 39: return "'\\''"
            if v == 92: return "'\\\\'"
            if 32 <= v < 127: return f"'{chr(v)}'"
            return f"'\\x{v:02x}'"
        if isinstance(expr, ExprBool):
            return 'true' if expr.value else 'false'
        if isinstance(expr, ExprNull):
            return 'NULL'
        if isinstance(expr, ExprIdent):
            parts = expr.name.split('::')
            if len(parts) > 1:
                if parts[-1] in self._extern_names:
                    return parts[-1]  # externs keep their original C name
                if parts[0] in self._enum_base_names:
                    # same-module enum variant: IrTypeKind::Int ->
                    # ir_types_IrTypeKind_Int (enum name was module-mangled)
                    rest = '_'.join(p.replace('.', '_') for p in parts[1:])
                    return f'{self._enum_base_names[parts[0]]}_{rest}'
                if parts[0] in TYPE_MAP:
                    parts[0] = TYPE_MAP[parts[0]]
            return '_'.join(p.replace('.', '_') for p in parts)
        if isinstance(expr, ExprUnary):
            op = expr.op
            op_map = {'++': '++', '--': '--'}
            coral_op = op_map.get(op, op)
            if getattr(expr, 'is_postfix', False):
                return f'({self.expr_to_c(expr.operand)}{coral_op})'
            return f'({coral_op}{self.expr_to_c(expr.operand)})'
        if isinstance(expr, ExprBinary):
            if expr.op in ('==', '!='):
                lt = self._var_type(expr.left)
                rt = self._var_type(expr.right)
                # Only struct values (not pointers) use memcmp; comparing
                # pointers must stay pointer identity.
                if (lt and lt in self._all_structs and rt and rt in self._all_structs
                        and self._expr_stars(expr.left) == 0
                        and self._expr_stars(expr.right) == 0):
                    lc = self.expr_to_c(expr.left)
                    rc = self.expr_to_c(expr.right)
                    self._uses_mem_builtins = True
                    self._used_libc_funcs.add('memcmp')
                    eq = f'(memcmp(&{lc}, &{rc}, sizeof({lt})) == 0)'
                    return eq if expr.op == '==' else f'(!{eq})'
                # strView/String vs string literal: wrap the literal side in
                # the mangled type's fromCstr constructor (Zig: no implicit
                # conversion, but this is the bootstrap convenience the rest
                # of codegen relies on).
                if isinstance(expr.right, ExprString) and self._needs_str_wrap(lt):
                    lc = self.expr_to_c(expr.left)
                    rc = self._str_wrap(lt, self.expr_to_c(expr.right))
                    return f'({lc} {expr.op} {rc})'
                if isinstance(expr.left, ExprString) and self._needs_str_wrap(rt):
                    lc = self._str_wrap(rt, self.expr_to_c(expr.left))
                    rc = self.expr_to_c(expr.right)
                    return f'({lc} {expr.op} {rc})'
            return f'({self.expr_to_c(expr.left)} {expr.op} {self.expr_to_c(expr.right)})'
        if isinstance(expr, ExprTernary):
            return f'({self.expr_to_c(expr.condition)} ? {self.expr_to_c(expr.then_expr)} : {self.expr_to_c(expr.else_expr)})'
        if isinstance(expr, ExprCall):
            translated = self._translate_call(expr)
            if translated:
                return translated
            callee = self.expr_to_c(expr.callee)
            args = self._call_args_list(callee, expr.args)
            return f'{callee}({args})'
        if isinstance(expr, ExprDot):
            # Module member access: vec.push(...) -> vec_push(...)
            obj = expr.object
            while isinstance(obj, ExprParen):
                obj = obj.expr
            if isinstance(obj, ExprIdent) and obj.name in self._module_aliases:
                if expr.member in self._extern_names:
                    return expr.member  # externs keep their original C name
                return f'{obj.name}_{expr.member}'
            # Enum variant access: ir_opcodes_IrOpcode.Neg -> the enum C
            # name is module-mangled but the Variant is `enum_Variant`.
            if isinstance(obj, ExprIdent) and obj.name in self._enum_names:
                return f'{obj.name}_{expr.member}'
            # Type-qualified access parsed as nested module dot:
            # ir_opcodes_IrOpcode.Neg (from ir_opcodes.IrOpcode::Neg).
            if isinstance(obj, ExprDot):
                mobj = obj.object
                while isinstance(mobj, ExprParen):
                    mobj = mobj.expr
                if isinstance(mobj, ExprIdent) and mobj.name in self._module_aliases:
                    tname = f'{mobj.name}_{obj.member}'
                    if tname in self._enum_names:
                        return f'{tname}_{expr.member}'
            # Pointer-valued objects need `->` (incl. pointer fields and
            # index expressions over pointer arrays).
            if self._expr_stars(obj) >= 1:
                return f'{self.expr_to_c(expr.object)}->{expr.member}'
            return f'{self.expr_to_c(expr.object)}.{expr.member}'
        if isinstance(expr, ExprArrow):
            return f'{self.expr_to_c(expr.object)}->{expr.member}'
        if isinstance(expr, ExprIndex):
            return f'{self.expr_to_c(expr.object)}[{self.expr_to_c(expr.index)}]'
        if isinstance(expr, ExprDeref):
            return f'(*{self.expr_to_c(expr.operand)})'
        if isinstance(expr, ExprAddrOf):
            if isinstance(expr.operand, ExprCall):
                inner = self.expr_to_c(expr.operand)
                vt = self._call_return_type(expr.operand)
                if vt:
                    rt = TYPE_MAP.get(vt, vt)
                    return f'(&({rt}){{{inner}}})'
            return f'(&{self.expr_to_c(expr.operand)})'
        if isinstance(expr, ExprCast):
            return f'({self.type_to_c(expr.type_expr)}){self.expr_to_c(expr.operand)}'
        if isinstance(expr, ExprSizeof):
            return f'sizeof({self.type_to_c(expr.type_expr)})'
        if isinstance(expr, ExprParen):
            return f'({self.expr_to_c(expr.expr)})'
        if isinstance(expr, ExprTypeLiteral):
            return f'({self.type_to_c(expr.type_expr)})'
        if isinstance(expr, ExprModulePath):
            return '_'.join(expr.parts)
        if isinstance(expr, ExprGenericInst):
            if isinstance(expr.base, ExprIdent):
                parts = expr.base.name.split('::')
                base = parts[-1]
            else:
                b = expr.base
                while isinstance(b, ExprParen):
                    b = b.expr
                if isinstance(b, ExprDot):
                    mo = b.object
                    while isinstance(mo, ExprParen):
                        mo = mo.expr
                    # Module-qualified generic (mman.realloc<T>): the full
                    # module-mangled name is needed; the plain member may be
                    # an extern name (e.g. libc's realloc) that would lose
                    # the module prefix.
                    if isinstance(mo, ExprIdent) and mo.name in self._module_aliases:
                        base = f'{mo.name}_{b.member}'
                    else:
                        base = self.expr_to_c(expr.base)
                else:
                    base = self.expr_to_c(expr.base)
            parts = []
            for a in expr.type_args:
                if isinstance(a, (TypeIdent, TypePointer, TypeArray, TypeGeneric, TypeFunc)):
                    parts.append(self._type_suffix(a))
                else:
                    parts.append(self.expr_to_c(a))
            return f'{base}_{"_".join(parts)}'
        if isinstance(expr, ExprInitializer):
            parts = []
            for f in expr.fields:
                if isinstance(f, tuple) and len(f) == 2:
                    parts.append(f'.{f[0]}={self.expr_to_c(f[1])}')
                else:
                    parts.append(self.expr_to_c(f))
            return '{' + ', '.join(parts) + '}'
        return '/* unknown expr */'

    # Entry Point

    def _infer_const_type(self, value):
        if isinstance(value, ExprInt):
            v = value.value
            if v < 0:
                if v >= -128: return 'int8_t'
                if v >= -32768: return 'int16_t'
                if v >= -2147483648: return 'int32_t'
                return 'int64_t'
            else:
                if v <= 255: return 'uint8_t'
                if v <= 65535: return 'uint16_t'
                if v <= 4294967295: return 'uint32_t'
                return 'uint64_t'
        if isinstance(value, ExprFloat):
            # Check if it's f32 range or f64
            return 'double'
        if isinstance(value, ExprString):
            return 'strView'
        if isinstance(value, ExprBool):
            return 'bool'
        return 'int'

    def generate(self, program):
        """Generate C code for the program."""
        self.emit_h(HEADER)

        mod_name = self.module_name.replace('::', '_').replace('.', '_')
        guard = f'CORAL_{mod_name.upper()}_H'
        self.emit_h(f'#ifndef {guard}')
        self.emit_h(f'#define {guard}')
        self.emit_h()
        self.emit_h(f'// Generated from {program.filename or "unknown"}')
        self.emit_h()

        self.emit_c(f'// Generated from {program.filename or "unknown"}')
        self.emit_c(f'#include "{mod_name}.h"')
        self.emit_c()

        # Collect imports before generating code
        for decl in program.decls:
            if isinstance(decl, DeclImport):
                inc = decl.path.split('::')[-1]
                self._imports.add(inc)
                for a in decl.names:
                    self._module_aliases.add(a)

        # Skip import includes — all imports are merged into the same output

        # First pass: collect struct declarations and function declarations
        # Pre-scan method arities so overloaded methods (same name, different
        # parameter counts) get distinct C names from the very first decl.
        for decl in program.decls:
            if isinstance(decl, DeclStruct):
                for m in decl.methods:
                    self._register_method_arity(decl.name, m)
            elif isinstance(decl, DeclMethodBlock):
                for m in decl.methods:
                    self._register_method_arity(decl.struct_name, m)
        for decl in program.decls:
            self._collect_decls(decl)
            self._scan_builtin_types(decl)
            if isinstance(decl, DeclEnum):
                self._enum_names.add(decl.name)
                bare = decl.name
                if decl.alias and decl.name.startswith(f'{decl.alias}_'):
                    bare = decl.name[len(decl.alias) + 1:]
                self._enum_base_names.setdefault(bare, decl.name)
            elif isinstance(decl, DeclTypedef) and isinstance(decl.type_expr, TypeFunc):
                self._fnptr_typedefs.add(decl.name)

        # Add includes for built-in types used (scanned above)
        for builtin in sorted(self._builtin_types_used):
            inc = BUILTIN_INCLUDES.get(builtin)
            if inc:
                self.emit_h(f'#include "{inc}.h"')
        if self._builtin_types_used:
            self.emit_h()
        # Emit enum, const, and typedef declarations first (structs depend on them)
        # Struct forward declarations must precede struct-typed typedefs
        # (e.g. wallvm_PassFn references ir_types_IrFunc*).
        self._emit_struct_fwd_decls()
        self._const_names = {d.name for d in program.decls
                             if isinstance(d, DeclConst)}
        for decl in program.decls:
            if isinstance(decl, DeclEnum):
                self._generate_enum(decl)
            elif isinstance(decl, DeclConst):
                self._generate_const(decl)
            elif isinstance(decl, DeclTypedef):
                self._generate_typedef(decl)
            elif isinstance(decl, DeclDistinct):
                self._generate_distinct(decl)

        # Emit module-level variables after constants, in dependency order
        # so initializers only reference already-declared globals.
        self._emit_globals_sorted(
            [d for d in program.decls if isinstance(d, DeclVar)],
            const_names={d.name for d in program.decls
                         if isinstance(d, DeclConst)})

        # Emit struct definitions in dependency order
        self._emit_structs_sorted()

        # Exported globals reference struct types; emit their extern
        # declarations now that all structs are defined.
        for line in self._exported_vars:
            self.emit_h(line)
        if self._exported_vars:
            self.emit_h()

        # Emit function and extern forward declarations (after all structs are defined)
        for ret_type, fn_name, param_str in self._func_forward_decls:
            self.emit_h(f'{ret_type} {fn_name}({param_str});')
        for ret_type, fn_name, sig_str in self._extern_forward_decls:
            self._extern_declared.add(fn_name)
            if ret_type is None:
                self.emit_h(f'extern {sig_str};')
            else:
                self.emit_h(f'extern {ret_type} {sig_str};')
        for ret_type, fn_name, param_str in self._method_forward_decls:
            self.emit_h(f'{ret_type} {fn_name}({param_str});')
        if self._func_forward_decls or self._extern_forward_decls or self._method_forward_decls:
            self.emit_h()

        # Second pass: generate remaining code (struct methods, functions, etc.)
        for decl in program.decls:
            if isinstance(decl, (DeclEnum, DeclTypedef, DeclDistinct, DeclConst, DeclVar)):
                continue  # already emitted
            self._generate_decl(decl)

        self.emit_h()
        self.emit_h('#endif')
        self.header_lines.append('')

        h_content = '\n'.join(self.header_lines)
        c_content = '\n'.join(self.source_lines)

        # libc functions used by the generated code (possibly synthesized
        # during generation, e.g. memcmp for struct equality). We never
        # include their headers; the symbols are resolved by linking libc.
        missing = [proto for name, proto in LIBC_FUNC_PROTOS.items()
                   if name in self._used_libc_funcs
                   and name not in self._funcs_declared
                   and name not in self._extern_declared]
        if missing:
            first_newline = c_content.find('\n')
            insert_at = first_newline + 1 if first_newline >= 0 else 0
            block = '\n'.join(missing) + '\n'
            c_content = c_content[:insert_at] + block + c_content[insert_at:]

        return h_content, c_content

    def _collect_decls(self, decl):
        if isinstance(decl, DeclStruct):
            self._collect_struct(decl)
        elif isinstance(decl, DeclMethodBlock):
            self._collect_method_block(decl)
        elif isinstance(decl, DeclFunc):
            self._collect_function(decl)
        elif isinstance(decl, DeclExtern):
            self._collect_extern(decl)

    def _collect_method_block(self, decl):
        sn = decl.struct_name
        if sn not in self._struct_methods:
            self._struct_methods[sn] = set()
        for m in decl.methods:
            self._struct_methods[sn].add(m.name)
            if getattr(m, 'static', False):
                self._struct_static_methods.setdefault(sn, set()).add(m.name)
            fn_name = f'{self._method_c_name(sn, m.name, self._method_def_arity(sn, m))}'
            if m.return_type:
                if isinstance(m.return_type, TypeIdent):
                    self._func_return_types[fn_name] = m.return_type.name
                elif isinstance(m.return_type, TypePointer) and isinstance(m.return_type.base, TypeIdent):
                    self._func_return_types[fn_name] = m.return_type.base.name

    def _collect_function(self, decl):
        if decl.generic_params:
            return
        if decl.inline:
            return  # static inline functions get their own prototype from
            # the definition site; a plain forward decl would CONFLICT
            # with the 'static inline' one in the header
        if decl.extern:
            self._extern_names.add(decl.name)
            return  # extern decls are prototypes, not definitions
        ret_type = self.type_to_c(decl.return_type) if decl.return_type else 'void'
        sn = decl.struct_name
        fn_name = f'{sn}_{decl.name}' if sn else decl.name
        params = []
        param_types = []
        for p in decl.params:
            p_name = p.name or ''
            params.append(self.decl_type_str(p.type_expr, p_name))
            param_types.append(self.type_to_c(p.type_expr))
        param_str = ', '.join(params)
        self._func_forward_decls.append((ret_type, fn_name, param_str))
        self._func_param_types[fn_name] = param_types

    def _collect_extern(self, decl):
        vargs = ', ...' if decl.variadic else ''
        fn_name = decl.name
        self._extern_names.add(fn_name)
        if decl.is_var:
            ret_type = self.type_to_c(decl.return_type) if decl.return_type else 'void'
            self._extern_forward_decls.append((ret_type, fn_name, fn_name))
            return
        params = []
        for p in decl.params:
            p_name = p.name or ''
            params.append(self.decl_type_str(p.type_expr, p_name))
        param_str = ', '.join(params)

        if isinstance(decl.return_type, TypeFunc):
            inner_ret = self.type_to_c(decl.return_type.return_type) if decl.return_type.return_type else 'void'
            inner_params = ', '.join(self.type_to_c(p) for p in decl.return_type.param_types)
            # Store as: (inner_ret, fn_name, params_part, inner_params) — special handling
            self._extern_forward_decls.append((None, fn_name, f'{inner_ret} (*{fn_name}({param_str}{vargs}))({inner_params})'))
        else:
            ret_type = self.type_to_c(decl.return_type) if decl.return_type else 'void'
            self._extern_forward_decls.append((ret_type, fn_name, f'{fn_name}({param_str}{vargs})'))

    def _collect_struct(self, decl):
        if decl.name in self._structs_seen:
            return
        self._structs_seen.add(decl.name)
        self._all_structs[decl.name] = decl
        self._struct_methods[decl.name] = {m.name for m in decl.methods}
        self._struct_static_methods[decl.name] = {m.name for m in decl.methods if getattr(m, 'static', False)}
        if decl.generic_params:
            return
        # Register field types (unwrapping all pointer/array levels so
        # method calls on `self.ops[i]` resolve to the element struct).
        for f in decl.fields:
            if isinstance(f.type_expr, (TypePointer, TypeArray)):
                self._struct_ptr_fields.add((decl.name, f.name))
            te = f.type_expr
            while isinstance(te, (TypePointer, TypeArray)):
                te = te.base
            if isinstance(te, TypeIdent):
                self._struct_field_types[(decl.name, f.name)] = (
                    te.name.replace('::', '_').replace('.', '_'))
            self._struct_field_c[(decl.name, f.name)] = self.type_to_c(f.type_expr)
        # Register methods and collect their forward declarations
        saved_struct = self._current_struct
        self._current_struct = decl.name
        for m in decl.methods:
            if m.generic_params:
                continue
            fn_name = self._method_c_name(decl.name, m.name, self._method_def_arity(decl.name, m))
            if m.return_type:
                if isinstance(m.return_type, TypeIdent):
                    self._func_return_types[fn_name] = m.return_type.name
                elif isinstance(m.return_type, TypePointer):
                    base = m.return_type.base
                    if isinstance(base, TypeIdent):
                        self._func_return_types[fn_name] = base.name
            # Collect method forward declaration
            ret_type = self.type_to_c(m.return_type) if m.return_type else 'void'
            params = []
            param_types = []
            is_constructor = m.name in ('new', 'fromView', 'fromCstr', 'fromParts', 'withCap', 'fromParts', 'some', 'none')
            first_unnamed = bool(m.params) and not (m.params[0].name or '').strip()
            has_explicit_self = (any(p.name in ('self', 'this') for p in m.params)
                                 or (first_unnamed and not m.static and not is_constructor))
            if decl.name and not m.static and not has_explicit_self and not is_constructor:
                self_type = f'{decl.name}*'
                params.append(f'{self_type} self')
                param_types.append(self_type)
            for i, p in enumerate(m.params):
                p_name = p.name or ''
                if i == 0 and first_unnamed and not m.static and not is_constructor:
                    p_name = 'self'
                params.append(self.decl_type_str(p.type_expr, p_name))
                param_types.append(self.type_to_c(p.type_expr))
            param_str = ', '.join(params)
            self._method_forward_decls.append((ret_type, fn_name, param_str))
            self._func_param_types[fn_name] = param_types
        self._current_struct = saved_struct

    def _scan_builtin_types(self, decl):
        if isinstance(decl, (DeclFunc, DeclExtern)):
            for p in decl.params:
                self._scan_type(p.type_expr)
            self._scan_type(decl.return_type)
            if isinstance(decl, DeclFunc) and decl.body:
                for s in decl.body.stmts:
                    self._scan_stmt_mem_builtins(s)
        elif isinstance(decl, DeclConst):
            self._scan_type(decl.type_anno)
        elif isinstance(decl, DeclVar):
            self._scan_type(decl.type_anno)
        elif isinstance(decl, DeclStruct):
            for f in decl.fields:
                self._scan_type(f.type_expr)
            for m in decl.methods:
                if m.body:
                    for s in m.body.stmts:
                        self._scan_stmt_mem_builtins(s)

    _MEM_BUILTINS = {'memcpy', 'memmove', 'memset', 'memcmp'}

    def _scan_expr_mem_builtins(self, expr):
        if expr is None:
            return
        if isinstance(expr, ExprIdent):
            base_name = expr.name.split('::')[-1].split('.')[-1]
            if base_name in self._MEM_BUILTINS:
                self._uses_mem_builtins = True
                self._used_libc_funcs.add(base_name)
        elif isinstance(expr, (ExprCall, ExprGenericInst)):
            self._scan_expr_mem_builtins(expr.callee if isinstance(expr, ExprCall) else expr.base)
            for a in expr.args if isinstance(expr, ExprCall) else expr.type_args:
                self._scan_expr_mem_builtins(a)
        elif isinstance(expr, ExprDot):
            self._scan_expr_mem_builtins(expr.object)
        elif isinstance(expr, ExprArrow):
            self._scan_expr_mem_builtins(expr.object)
        elif isinstance(expr, ExprUnary):
            self._scan_expr_mem_builtins(expr.operand)
        elif isinstance(expr, ExprBinary):
            self._scan_expr_mem_builtins(expr.left)
            self._scan_expr_mem_builtins(expr.right)
        elif isinstance(expr, ExprTernary):
            self._scan_expr_mem_builtins(expr.condition)
            self._scan_expr_mem_builtins(expr.then_expr)
            self._scan_expr_mem_builtins(expr.else_expr)
        elif isinstance(expr, ExprParen):
            self._scan_expr_mem_builtins(expr.expr)
        elif isinstance(expr, ExprIndex):
            self._scan_expr_mem_builtins(expr.object)
            self._scan_expr_mem_builtins(expr.index)
        elif isinstance(expr, ExprCast):
            self._scan_expr_mem_builtins(expr.operand)
        elif isinstance(expr, ExprAddrOf):
            self._scan_expr_mem_builtins(expr.operand)
        elif isinstance(expr, ExprDeref):
            self._scan_expr_mem_builtins(expr.operand)
        elif isinstance(expr, ExprInitializer):
            for f in expr.fields:
                if isinstance(f, tuple) and len(f) == 2:
                    self._scan_expr_mem_builtins(f[1])
                else:
                    self._scan_expr_mem_builtins(f)

    def _scan_stmt_mem_builtins(self, stmt):
        if stmt is None:
            return
        if isinstance(stmt, StmtBlock):
            for s in stmt.stmts:
                self._scan_stmt_mem_builtins(s)
        elif isinstance(stmt, StmtVar):
            self._scan_expr_mem_builtins(stmt.value)
        elif isinstance(stmt, StmtAssign):
            self._scan_expr_mem_builtins(stmt.target)
            self._scan_expr_mem_builtins(stmt.value)
        elif isinstance(stmt, StmtReturn):
            self._scan_expr_mem_builtins(stmt.value)
        elif isinstance(stmt, StmtIf):
            self._scan_expr_mem_builtins(stmt.condition)
            self._scan_stmt_mem_builtins(stmt.then_block)
            self._scan_stmt_mem_builtins(stmt.else_block)
        elif isinstance(stmt, StmtExpr):
            self._scan_expr_mem_builtins(stmt.expr)
        elif isinstance(stmt, StmtFor):
            self._scan_expr_mem_builtins(stmt.init)
            self._scan_expr_mem_builtins(stmt.condition)
            self._scan_expr_mem_builtins(stmt.increment)
            self._scan_stmt_mem_builtins(stmt.body)
        elif isinstance(stmt, StmtForIn):
            self._scan_expr_mem_builtins(stmt.iterable)
            self._scan_stmt_mem_builtins(stmt.body)
        elif isinstance(stmt, StmtWhile):
            self._scan_expr_mem_builtins(stmt.condition)
            self._scan_stmt_mem_builtins(stmt.body)
        elif isinstance(stmt, StmtLoop):
            self._scan_stmt_mem_builtins(stmt.body)
        elif isinstance(stmt, StmtAssert):
            self._scan_expr_mem_builtins(stmt.condition)
        elif isinstance(stmt, StmtDefer):
            self._scan_stmt_mem_builtins(stmt.body)

    def _scan_type(self, typ):
        if typ is None:
            return
        if isinstance(typ, TypeIdent):
            if typ.name in TYPE_MAP:
                self._builtin_types_used.add(typ.name)
        elif isinstance(typ, TypePointer):
            self._scan_type(typ.base)
        elif isinstance(typ, TypeArray):
            self._scan_type(typ.base)
        elif isinstance(typ, TypeGeneric):
            for a in typ.args:
                self._scan_type(a)
        elif isinstance(typ, TypeFunc):
            self._scan_type(typ.return_type)
            for p in typ.param_types:
                self._scan_type(p)

    def _type_to_suffix(self, typ):
        if isinstance(typ, TypeIdent):
            return typ.name.replace('::', '_').replace('.', '_')
        if isinstance(typ, TypePointer):
            return self._type_to_suffix(typ.base) + '_ptr'
        if isinstance(typ, TypeGeneric):
            base = typ.name.replace('::', '_').replace('.', '_')
            args = '_'.join(self._type_to_suffix(a) for a in typ.args)
            return f'{base}_{args}'
        if isinstance(typ, TypeArray):
            return self._type_to_suffix(typ.base) + '_arr'
        if isinstance(typ, ExprInt):
            return str(typ.value)
        if isinstance(typ, ExprFloat):
            return str(typ.value).replace('.', '_')
        return 'unknown'

    def _get_struct_deps(self, name):
        deps = set()
        decl = self._all_structs.get(name)
        if not decl:
            return deps
        for f in decl.fields:
            ft = f.type_expr
            if isinstance(ft, TypeIdent):
                if ft.name in self._all_structs:
                    deps.add(ft.name)
            elif isinstance(ft, TypeArray):
                base = ft.base
                if isinstance(base, TypeIdent) and base.name in self._all_structs:
                    deps.add(base.name)
            elif isinstance(ft, TypePointer):
                base = ft.base
                if isinstance(base, TypeIdent) and base.name in self._all_structs:
                    deps.add(base.name)
            elif isinstance(ft, TypeGeneric):
                mname = self._type_to_suffix(ft)
                if mname in self._all_structs:
                    deps.add(mname)
                for a in ft.args:
                    if isinstance(a, TypeIdent) and a.name in self._all_structs:
                        deps.add(a.name)
                    elif isinstance(a, TypePointer):
                        pname = self._type_to_suffix(a)
                        if pname in self._all_structs:
                            deps.add(pname)
        return deps

    def _emit_struct_fwd_decls(self):
        names = list(self._all_structs.keys())
        ordered = []
        visited = set()
        def visit(n):
            if n in visited:
                return
            visited.add(n)
            for d in self._get_struct_deps(n):
                visit(d)
            if n not in ordered:
                ordered.append(n)
        for n in names:
            visit(n)
        for n in ordered:
            cn = n.replace('.', '_')
            self.emit_h(f'typedef struct {cn} {cn};')
        return ordered

    def _emit_structs_sorted(self):
        ordered = self._emit_struct_fwd_decls()
        for n in ordered:
            self._emit_struct_body(self._all_structs[n])

    def _global_deps(self, expr):
        """Names of top-level consts/vars referenced by `expr`."""
        out = set()

        def walk(e):
            if e is None:
                return
            if isinstance(e, ExprIdent):
                if e.name != 'self':
                    out.add(e.name)
            elif isinstance(e, ExprDot):
                obj = e.object
                while isinstance(obj, ExprParen):
                    obj = obj.expr
                if isinstance(obj, ExprIdent) and obj.name in self._module_aliases:
                    out.add(f'{obj.name}_{e.member}')
                else:
                    walk(obj)
            elif isinstance(e, ExprArrow):
                walk(e.object)
            elif isinstance(e, ExprUnary):
                walk(e.operand)
            elif isinstance(e, ExprBinary):
                walk(e.left)
                walk(e.right)
            elif isinstance(e, ExprTernary):
                walk(e.condition)
                walk(e.then_expr)
                walk(e.else_expr)
            elif isinstance(e, ExprCall):
                walk(e.callee)
                for a in e.args:
                    walk(a)
            elif isinstance(e, ExprIndex):
                walk(e.object)
                walk(e.index)
            elif isinstance(e, ExprDeref):
                walk(e.operand)
            elif isinstance(e, ExprAddrOf):
                walk(e.operand)
            elif isinstance(e, ExprCast):
                walk(e.operand)
            elif isinstance(e, ExprParen):
                walk(e.expr)
            elif isinstance(e, ExprGenericInst):
                walk(e.base)
            elif isinstance(e, ExprConditional):
                walk(e.condition)
                walk(e.then_expr)
                walk(e.else_expr)

        walk(expr)
        return out

    def _emit_globals_sorted(self, decls, const_names=()):
        """Emit module-level variables in dependency order so initializers
        only reference globals already declared above them."""
        remaining = list(decls)
        emitted = set()
        const_names = set(const_names)
        while remaining:
            batch = []
            rest = []
            for d in remaining:
                deps = self._global_deps(d.value)
                if all(n in emitted or n in const_names for n in deps):
                    batch.append(d)
                else:
                    rest.append(d)
            if not batch:
                # Cycle or unresolvable dependency: emit in original order
                batch, rest = [remaining[0]], remaining[1:]
            for d in batch:
                self._generate_var(d)
                emitted.add(d.name)
            remaining = rest

    def _emit_struct_body(self, decl):
        if decl.generic_params:
            return
        if decl.name in self._structs_emitted:
            return
        self._structs_emitted.add(decl.name)
        self.emit_h(f'struct {decl.name.replace(".", "_")}')
        self.emit_h('{')
        for field in decl.fields:
            self.emit_h(f'    {self.decl_type_str(field.type_expr, field.name)};')
        self.emit_h('};')
        self.emit_h()

    def _generate_decl(self, decl):
        if isinstance(decl, DeclModule):
            self.module_name = decl.path.replace('::', '_').replace('.', '_')
        elif isinstance(decl, DeclConst):
            pass  # already emitted in pre-pass
        elif isinstance(decl, DeclVar):
            self._generate_var(decl)
        elif isinstance(decl, DeclStruct):
            self._generate_struct(decl)
        elif isinstance(decl, DeclEnum):
            pass  # already emitted in pre-pass
        elif isinstance(decl, DeclTrait):
            self._generate_trait(decl)
        elif isinstance(decl, DeclFunc):
            self._generate_function(decl)
        elif isinstance(decl, DeclExtern):
            self._generate_extern(decl)
        elif isinstance(decl, DeclTypedef):
            pass  # already emitted in pre-pass
        elif isinstance(decl, DeclDistinct):
            pass  # already emitted in pre-pass
        elif isinstance(decl, DeclMethodBlock):
            self._generate_method_block(decl)

    STDINT_CONFLICTS = {
        'INT8_MIN', 'INT8_MAX', 'INT16_MIN', 'INT16_MAX',
        'INT32_MIN', 'INT32_MAX', 'INT64_MIN', 'INT64_MAX',
        'UINT8_MAX', 'UINT16_MAX', 'UINT32_MAX', 'UINT64_MAX',
        'SIZE_MAX', 'WCHAR_MIN', 'WCHAR_MAX',
    }

    def _generate_const(self, decl):
        if decl.name in self.STDINT_CONFLICTS:
            return
        if decl.name in self._globals_declared:
            return
        self._globals_declared.add(decl.name)
        c_type = self.type_to_c(decl.type_anno) if decl.type_anno else self._infer_const_type(decl.value)
        c_name = decl.name
        c_val = self.expr_to_c(decl.value) if decl.value else '0'

        # Simple integer constants -> enum (usable as array dimensions in C)
        if isinstance(decl.value, ExprInt) and isinstance(decl.type_anno, TypeIdent):
            self.emit_h(f'enum {{ {c_name} = {c_val} }};')
            return

        # Array constants: `const char* NAMES[] = {...}` — infer the extent
        # from the initializer when the size is omitted; keep the array type
        # on both the definition and the extern (pointer vs array decls
        # conflict in C).
        if isinstance(decl.type_anno, TypeArray):
            c_base = self.type_to_c(decl.type_anno.base)
            if decl.type_anno.size:
                c_extent = self.expr_to_c(decl.type_anno.size)
            elif isinstance(decl.value, ExprInitializer):
                c_extent = str(len(decl.value.fields))
            else:
                c_extent = None
            if c_extent:
                if decl.exported:
                    self._exported_vars.append(
                        f'extern const {c_base} {c_name}[{c_extent}];')
                if isinstance(decl.value, ExprInitializer):
                    c_val = self._array_init_c(decl.type_anno.base, decl.value)
                self.emit_c(f'const {c_base} {c_name}[{c_extent}] = {c_val};')
                self.emit_c()
                return

        if decl.exported:
            self._exported_vars.append(f'extern const {c_type} {c_name};')
        self.emit_c(f'const {c_type} {c_name} = {c_val};')
        self.emit_c()

    def _is_const_expr(self, expr):
        """True if `expr` can appear in a C global initializer."""
        if expr is None:
            return True
        if isinstance(expr, (ExprInt, ExprFloat, ExprBool, ExprChar,
                             ExprString, ExprNull)):
            return True
        if isinstance(expr, ExprIdent):
            if expr.name in self._const_names:
                return True
            # A function name is an address constant in C
            return expr.name in self._func_param_types
        if isinstance(expr, ExprAddrOf):
            return self._is_const_expr(expr.operand)
        if isinstance(expr, ExprInitializer):
            for f in expr.fields:
                if isinstance(f, tuple) and len(f) == 2:
                    if not self._is_const_expr(f[1]):
                        return False
                elif not self._is_const_expr(f):
                    return False
            return True
        if isinstance(expr, (ExprUnary, ExprDeref)):
            return self._is_const_expr(expr.operand)
        if isinstance(expr, ExprBinary):
            return self._is_const_expr(expr.left) \
                and self._is_const_expr(expr.right)
        if isinstance(expr, ExprTernary):
            return self._is_const_expr(expr.condition) \
                and self._is_const_expr(expr.then_expr) \
                and self._is_const_expr(expr.else_expr)
        if isinstance(expr, ExprParen):
            return self._is_const_expr(expr.expr)
        if isinstance(expr, ExprCast):
            return self._is_const_expr(expr.operand)
        if isinstance(expr, ExprSizeof):
            return True
        if isinstance(expr, ExprIndex):
            return self._is_const_expr(expr.object) \
                and self._is_const_expr(expr.index)
        return False

    def _generate_var(self, decl):
        if decl.name in self._globals_declared:
            return
        self._globals_declared.add(decl.name)
        c_type = self.type_to_c(decl.type_anno) if decl.type_anno else 'int'
        c_name = decl.name
        c_val = self.expr_to_c(decl.value) if decl.value else None
        if c_val and not self._is_const_expr(decl.value):
            # C requires constant initializers for globals; zero-init and
            # leave the value to be assigned at runtime (matches ts codegen)
            c_val = None
        if decl.exported and not isinstance(decl.type_anno, TypeArray):
            self._exported_vars.append(f'extern {c_type} {c_name};')
        if isinstance(decl.type_anno, TypeArray):
            c_base = self.type_to_c(decl.type_anno.base)
            if decl.type_anno.size:
                c_size = self.expr_to_c(decl.type_anno.size)
            elif isinstance(decl.value, ExprInitializer):
                c_size = str(len(decl.value.fields))
            else:
                c_size = None
            if c_size:
                if isinstance(decl.value, ExprInitializer):
                    c_val = self._array_init_c(decl.type_anno.base, decl.value)
                if decl.exported:
                    self._exported_vars.append(
                        f'extern {c_base} {c_name}[{c_size}];')
                val_str = f' = {c_val}' if c_val else ''
                self.emit_c(f'{c_base} {c_name}[{c_size}]{val_str};')
            else:
                val_str = f' = {c_val}' if c_val else ''
                self.emit_c(f'{c_type} {c_name}{val_str};')
        else:
            val_str = f' = {c_val}' if c_val else ''
            self.emit_c(f'{c_type} {c_name}{val_str};')
        self.emit_c()

    def _array_init_c(self, base_type_node, initializer):
        c_base = self.type_to_c(base_type_node)
        base_name = getattr(base_type_node, 'name', '')
        is_str = base_name.replace('.', '_').split('_')[-1] in ('strView', 'String')
        parts = []
        for f in initializer.fields:
            if isinstance(f, tuple) and len(f) == 2:
                parts.append(f'.{f[0]}={self.expr_to_c(f[1])}')
            else:
                val = self.expr_to_c(f)
                if is_str and isinstance(f, ExprString):
                    val = f'{{.ptr={val}, .len=sizeof({val})-1}}'
                parts.append(val)
        return '{' + ', '.join(parts) + '}'

    def _generate_struct(self, decl):
        if decl.generic_params:
            return
        if decl.name in self._structs_methods_emitted:
            return
        self._structs_methods_emitted.add(decl.name)

        # Generate methods (struct body already emitted by _emit_structs_sorted)
        saved = self._current_struct
        self._current_struct = decl.name
        for method in decl.methods:
            self._generate_function(method, struct_name=decl.name)
        self._current_struct = saved

    def _generate_enum(self, decl):
        # Enumerators are C-namespaced: prefix with the (mangled) enum name so
        # enums with overlapping variant names (IrICmpPred/Ult vs IrFCmpPred/Ult)
        # don't collide. References go through the same scheme in expr_to_c.
        self.emit_h(f'typedef enum {{')
        for i, variant in enumerate(decl.variants):
            comma = ',' if i < len(decl.variants) - 1 else ''
            vname = f'{decl.name}_{variant.name}'
            if variant.value:
                self.emit_h(f'    {vname} = {self.expr_to_c(variant.value)}{comma}')
            else:
                self.emit_h(f'    {vname}{comma}')
        self.emit_h(f'}} {decl.name};')
        self.emit_h()

    def _generate_trait(self, decl):
        # Traits generate a struct of function pointers
        self.emit_h(f'typedef struct {decl.name}_vtable {{')
        for method in decl.methods:
            ret = self.type_to_c(method.return_type)
            params = f'{ret}(*)('
            param_strs = ['void* self']
            for p in method.params:
                param_strs.append(self.type_to_c(p.type_expr))
            params += ', '.join(param_strs) + ')'
            self.emit_h(f'    {params} {method.name};')
        self.emit_h(f'}} {decl.name}_vtable;')
        self.emit_h()

    def _generate_function(self, decl, struct_name=None):
        # Save per-function state
        saved_ptr_vars = self._ptr_vars
        saved_var_types = self._var_types
        saved_defer_stack = self._defer_stack
        self._ptr_vars = set()
        self._var_types = {}
        self._defer_stack = []

        ret_type = self.type_to_c(decl.return_type) if decl.return_type else 'void'

        # Build function name
        if decl.struct_name or struct_name:
            sn = decl.struct_name or struct_name
            fn_name = self._method_c_name(sn, decl.name, self._method_def_arity(sn, decl))
        elif decl.trait_name:
            fn_name = f'{decl.struct_name}_{decl.trait_name}_{decl.name}'
        else:
            fn_name = decl.name

        if decl.generic_params:
            self._ptr_vars = saved_ptr_vars
            self._var_types = saved_var_types
            self._defer_stack = saved_defer_stack
            return

        # Build parameter list
        params = []
        has_explicit_self = False
        sn = decl.struct_name or struct_name
        is_constructor = decl.name in ('new', 'fromView', 'fromCstr', 'withCap', 'fromParts', 'some', 'none')
        for i, p in enumerate(decl.params):
            p_name = p.name or ''
            # Methods may declare self as an unnamed first param of the
            # struct's own pointer type (e.g. `void ensureVregs(LinearScanRegAlloc*, u32)`).
            if (p_name == '' and i == 0 and sn
                    and not getattr(decl, 'static', False)
                    and not is_constructor):
                p_name = 'self'
                has_explicit_self = True
            params.append(self.decl_type_str(p.type_expr, p_name))
            if p.name:
                resolved = self.resolved_type_name(p.type_expr)
                self._var_types[p.name] = resolved
                self._var_type_exprs[p.name] = p.type_expr
                if isinstance(p.type_expr, (TypePointer, TypeArray)):
                    self._ptr_vars.add(p.name)
            if p_name == 'self':
                resolved = self.resolved_type_name(p.type_expr)
                self._var_types['self'] = resolved
                self._var_type_exprs['self'] = p.type_expr
                self._ptr_vars.add('self')
            if p.name in ('self', 'this'):
                has_explicit_self = True

        # Add implicit self for non-static methods that reference self in body
        # Constructors (called via Type::method() syntax) don't get implicit self
        if sn and not decl.static and not has_explicit_self and not is_constructor:
            self_type = f'{sn}*'
            params.insert(0, f'{self_type} self')
            self._var_types['self'] = sn
            self._ptr_vars.add('self')
            if 'self' not in self._var_type_exprs:
                self._var_type_exprs['self'] = TypePointer(TypeIdent(sn), const=False)

        param_str = ', '.join(params)
        noreturn_attr = ' __attribute__((noreturn)) ' if decl.noreturn else ''
        inline_prefix = 'static inline ' if decl.inline else ''

        if decl.extern:
            # Declaration only
            vargs = ', ...' if getattr(decl, 'variadic', False) else ''
            if not decl.generic_params and fn_name not in self._funcs_declared:
                self._funcs_declared.add(fn_name)
                self.emit_h(f'extern {ret_type} {fn_name}({param_str}{vargs}){noreturn_attr};')
        else:
            # Declaration in header
            vargs = ', ...' if getattr(decl, 'variadic', False) else ''
            if decl.exported or not decl.generic_params:
                if fn_name not in self._funcs_declared:
                    self._funcs_declared.add(fn_name)
                    if decl.inline:
                        self.emit_h(f'static inline {ret_type} {fn_name}({param_str}{vargs});')
                    else:
                        self.emit_h(f'{ret_type} {fn_name}({param_str}{vargs});')
            elif decl.generic_params:
                pass  # generic templates don't get forward declarations

            if decl.body and fn_name not in self._funcs_defined:
                self._funcs_defined.add(fn_name)
                self.emit_c(f'{inline_prefix}{ret_type} {fn_name}({param_str})')
                self.emit_c('{')
                self.indent_level += 1
                for stmt in decl.body.stmts:
                    self._generate_stmt(stmt)
                if decl.noreturn:
                    self.emit_c('__builtin_unreachable();')
                self.indent_level -= 1
                self.emit_c('}')
                self.emit_c()
        # Restore per-function state
        self._ptr_vars = saved_ptr_vars
        self._var_types = saved_var_types
        self._defer_stack = saved_defer_stack

    def _generate_extern(self, decl):
        if decl.name in INTRINSIC_MAP:
            return
        if decl.name in self._extern_declared:
            return  # already declared in the forward-decl pass
        if decl.is_var:
            ret_type = self.type_to_c(decl.return_type) if decl.return_type else 'void'
            self._extern_declared.add(decl.name)
            self.emit_h(f'extern {ret_type} {decl.name};')
            return
        ret_type = self.type_to_c(decl.return_type) if decl.return_type else 'void'
        vargs = ', ...' if decl.variadic else ''
        noreturn_attr = ' __attribute__((noreturn)) ' if decl.noreturn else ''

        params = []
        for p in decl.params:
            p_name = p.name or ''
            params.append(self.decl_type_str(p.type_expr, p_name))
        param_str = ', '.join(params)

        if isinstance(decl.return_type, TypeFunc):
            inner_ret = self.type_to_c(decl.return_type.return_type) if decl.return_type.return_type else 'void'
            inner_params = ', '.join(self.type_to_c(p) for p in decl.return_type.param_types)
            self.emit_h(f'extern {inner_ret} (*{decl.name}({param_str}{vargs}))({inner_params}){noreturn_attr};')
        else:
            self.emit_h(f'extern {ret_type} {decl.name}({param_str}{vargs}){noreturn_attr};')

    def _generate_typedef(self, decl):
        # Function-pointer typedefs need the name inside the declarator
        # (typedef bool (*name)(...)); decl_type_str handles that shape.
        c_type = self.decl_type_str(decl.type_expr, decl.name)
        self.emit_h(f'typedef {c_type};')
        self.emit_h()

    def _generate_distinct(self, decl):
        c_type = self.type_to_c(decl.type_expr)
        # Use simple typedef for distinct types (avoids struct wrapper issues)
        self.emit_h(f'typedef {c_type} {decl.name};')
        self.emit_h()

    def _generate_method_block(self, decl):
        saved = self._current_struct
        self._current_struct = decl.struct_name
        for method in decl.methods:
            self._generate_function(method, struct_name=decl.struct_name)
        self._current_struct = saved

    # Statement Generation

    def _needs_str_wrap(self, ctype):
        """True when a literal string argument must be wrapped in
        strView_fromCstr to satisfy a strView/String parameter. The C type
        carries the module prefix (`str_strView`), so match both the bare and
        mangled forms."""
        if not isinstance(ctype, str):
            return False
        return ctype in ('strView', 'String', 'str_strView', 'str_String')

    def _str_wrap(self, ctype, a_str):
        """Wrap a literal string expression for a strView/String parameter.
        The wrapper is the mangled type's fromCstr constructor."""
        return f'{ctype}_fromCstr({a_str})'

    def _call_args_list(self, fn_name, args):
        param_types = self._func_param_types.get(fn_name, [])
        arg_strs = []
        for i, a in enumerate(args):
            a_str = self.expr_to_c(a)
            if i < len(param_types) and self._needs_str_wrap(param_types[i]):
                if isinstance(a, ExprString):
                    a_str = self._str_wrap(param_types[i], a_str)
            arg_strs.append(a_str)
        return ', '.join(arg_strs)

    def _translate_call(self, expr):
        if isinstance(expr, ExprCall):
            callee = expr.callee
            # Builtin `cast<T>(val)` (defined in std/misc/cast.crl but
            # never imported) is emitted as a C cast: cast<u8*>(x) -> (uint8_t*)(x).
            if isinstance(callee, ExprGenericInst) and isinstance(callee.base, ExprIdent) and callee.base.name == 'cast':
                ct = self.type_to_c(callee.type_args[0])
                args = ', '.join(self.expr_to_c(a) for a in expr.args)
                return f'({ct})({args})'
            if isinstance(callee, ExprIdent):
                parts = callee.name.split('::')
                if len(parts) == 2:
                    # a::b — treat as module_function
                    if parts[1] in self._extern_names:
                        fn_name = parts[1]
                    else:
                        rt = TYPE_MAP.get(parts[0], parts[0])
                        fn_name = f'{rt}_{parts[1]}'
                    args = ', '.join(self.expr_to_c(a) for a in expr.args)
                    return f'{fn_name}({args})'
                if len(parts) >= 3:
                    # a::b::c — fully qualified, use only function name
                    fn_name = parts[-1]
                    args = ', '.join(self.expr_to_c(a) for a in expr.args)
                    return f'{fn_name}({args})'
                # Check if this is a private method call on self (e.g., _sortByRange)
                if self._current_struct and callee.name in self._struct_methods.get(self._current_struct, set()):
                    if callee.name in self._struct_static_methods.get(self._current_struct, set()):
                        # static methods take no self
                        fn_name = self._method_c_name(self._current_struct, callee.name, len(expr.args))
                        args_list = [self.expr_to_c(a) for a in expr.args]
                    else:
                        fn_name = self._method_c_name(self._current_struct, callee.name, 1 + len(expr.args))
                        self_arg = 'self'
                        args_list = [self_arg] + [self.expr_to_c(a) for a in expr.args]
                    return f'{fn_name}({", ".join(args_list)})'
            if isinstance(callee, ExprDot) or isinstance(callee, ExprArrow):
                obj = callee.object
                method = callee.member
                # Type-qualified method call: vec<T>::new()
                if isinstance(obj, ExprGenericInst):
                    rt = self._var_type(obj) or self.expr_to_c(obj)
                    args = ', '.join(self.expr_to_c(a) for a in expr.args)
                    return f'{self._method_c_name(rt, method, len(expr.args))}({args})'
                # Type-qualified constructor/method call: string_String.new(...)
                # where the object is a (mangled) type name, not a variable.
                raw_obj = obj
                while isinstance(raw_obj, ExprParen):
                    raw_obj = raw_obj.expr
                if isinstance(raw_obj, ExprIdent) and raw_obj.name in self._all_structs:
                    rt = raw_obj.name
                    if method in self._struct_methods.get(rt, set()):
                        args = ', '.join(self.expr_to_c(a) for a in expr.args)
                        return f'{self._method_c_name(rt, method, len(expr.args))}({args})'
                # `ir_builder.IrBuilder::new` parses as a nested module dot.
                if isinstance(raw_obj, ExprDot):
                    mobj = raw_obj.object
                    while isinstance(mobj, ExprParen):
                        mobj = mobj.expr
                    if isinstance(mobj, ExprIdent) and mobj.name in self._module_aliases:
                        tname = f'{mobj.name}_{raw_obj.member}'
                        if tname in self._all_structs and method in self._struct_methods.get(tname, set()):
                            args = ', '.join(self.expr_to_c(a) for a in expr.args)
                            return f'{self._method_c_name(tname, method, len(expr.args))}({args})'
                vt = self._var_type(obj)
                if vt:
                    rt = TYPE_MAP.get(vt, vt)
                    # Only treat as method call if member is a known struct method
                    # (not a function pointer field like Allocator.alloc)
                    if method in self._struct_methods.get(rt, set()):
                        # Unwrap ExprParen to get at the real expression
                        raw_obj = obj
                        while isinstance(raw_obj, ExprParen):
                            raw_obj = raw_obj.expr
                        obj_t = self.expr_to_c(obj)
                        args = [self.expr_to_c(a) for a in expr.args]
                        is_self = isinstance(raw_obj, ExprIdent) and raw_obj.name == 'self'
                        obj_is_ptr = isinstance(raw_obj, ExprIdent) and self._is_ptr_var(raw_obj.name)
                        obj_is_cast = isinstance(raw_obj, ExprCast)
                        obj_is_call = isinstance(raw_obj, ExprCall)
                        # Determine self argument: pointer or address-of
                        if self._expr_stars(raw_obj) >= 1:
                            self_arg = obj_t
                        elif obj_is_call:
                            self_arg = (f'({{ {rt} _t = {obj_t}; '
                                        f'{rt}* _p = __builtin_alloca(sizeof({rt})); '
                                        f'*_p = _t; _p; }})')
                        else:
                            self_arg = f'&{obj_t}'
                        # Detect if explicit self is passed as first arg
                        explicit_self = False
                        if args:
                            first = args[0]
                            if self_arg == first or obj_t == first:
                                if is_self or obj_is_ptr or obj_is_cast:
                                    explicit_self = True
                                if first == f'(&{obj_t})':
                                    explicit_self = True
                        call_arity = len(args) if explicit_self else len(args) + 1
                        fn_name_m = self._method_c_name(rt, method, call_arity)
                        param_types = self._func_param_types.get(fn_name_m, [])
                        if explicit_self:
                            wrapped_args = []
                            for i, a_str in enumerate(args):
                                if i < len(param_types) and self._needs_str_wrap(param_types[i]):
                                    ea = expr.args[i]
                                    if isinstance(ea, ExprString):
                                        a_str = self._str_wrap(param_types[i], a_str)
                                wrapped_args.append(a_str)
                        else:
                            wrapped_args = [self_arg]
                            for i, a_str in enumerate(args):
                                pi = i + 1
                                if pi < len(param_types) and self._needs_str_wrap(param_types[pi]):
                                    ea = expr.args[i]
                                    if isinstance(ea, ExprString):
                                        a_str = self._str_wrap(param_types[pi], a_str)
                                wrapped_args.append(a_str)
                        arg_str = ', '.join(wrapped_args)
                        return f'{fn_name_m}({arg_str})'
                    # Not a method -> function pointer field call, fall through
                    # to raw C generation (e.g., backing->alloc(ctx, size))
        return None

    def _var_type(self, expr):
        if isinstance(expr, ExprIdent):
            vt = self._var_types.get(expr.name)
            if vt:
                return vt
            te = self._var_type_exprs.get(expr.name)
            if te is not None:
                while isinstance(te, (TypePointer, TypeArray)):
                    te = te.base
                if isinstance(te, TypeIdent):
                    return te.name.replace('::', '_').replace('.', '_')
            return None
        if isinstance(expr, ExprCall):
            return self._call_return_type(expr)
        if isinstance(expr, ExprGenericInst):
            if isinstance(expr.base, ExprIdent):
                parts = [expr.base.name.replace('::', '_').replace('.', '_')]
                for a in expr.type_args:
                    parts.append(self._type_suffix(a))
                return '_'.join(parts)
        if isinstance(expr, ExprIndex):
            return self._var_type(expr.object)
        if isinstance(expr, ExprParen):
            return self._var_type(expr.expr)
        if isinstance(expr, ExprCast):
            if isinstance(expr.type_expr, TypePointer):
                base = expr.type_expr.base
                if isinstance(base, TypeIdent):
                    return base.name
            if isinstance(expr.type_expr, TypeIdent):
                return expr.type_expr.name
        if isinstance(expr, (ExprDot, ExprArrow)):
            base_type = self._var_type(expr.object)
            if base_type:
                return self._struct_field_types.get((base_type, expr.member))
        return None

    def _type_suffix(self, typ):
        """Convert a type to a short suffix string for monomorphised names."""
        if isinstance(typ, ExprInt):
            return str(typ.value)
        if isinstance(typ, ExprFloat):
            return str(typ.value).replace('.', '_')
        if isinstance(typ, TypeIdent):
            return typ.name.replace('.', '_')
        if isinstance(typ, TypePointer):
            return self._type_suffix(typ.base) + '_ptr'
        if isinstance(typ, TypeArray):
            return self._type_suffix(typ.base) + '_arr'
        if isinstance(typ, TypeGeneric):
            base = typ.name.replace('::', '_').replace('.', '_')
            args = '_'.join(self._type_suffix(a) for a in typ.args)
            return f'{base}_{args}'
        if isinstance(typ, TypeFunc):
            return 'fn'
        return 'unknown'

    def _call_return_type(self, expr):
        callee = expr.callee
        if isinstance(callee, ExprIdent):
            parts = callee.name.split('::')
            if len(parts) >= 2:
                fn_name = f'{parts[0]}_{parts[1]}'
                return self._func_return_types.get(fn_name)
            fn_name = callee.name
            if self._current_struct and callee.name in self._struct_methods.get(self._current_struct, set()):
                fn_name = self._method_c_name(self._current_struct, callee.name, 1 + len(expr.args))
            return self._func_return_types.get(fn_name)
        if isinstance(callee, ExprDot) or isinstance(callee, ExprArrow):
            mo = callee.object
            while isinstance(mo, ExprParen):
                mo = mo.expr
            tname = None
            if isinstance(mo, ExprDot) and isinstance(mo.object, ExprIdent) and mo.object.name in self._module_aliases:
                cand = f'{mo.object.name}_{mo.member}'
                if cand in self._all_structs:
                    tname = cand
            elif isinstance(mo, ExprIdent) and mo.name in self._all_structs:
                tname = mo.name
            if tname:
                m = callee.member
                if m in self._struct_static_methods.get(tname, set()):
                    fn_name = self._method_c_name(tname, m, len(expr.args))
                else:
                    fn_name = self._method_c_name(tname, m, 1 + len(expr.args))
                rt = self._func_return_types.get(fn_name)
                if rt:
                    return self._resolve_struct_name(rt)
            vt = self._var_type(callee.object)
            if vt:
                method = callee.member
                fn_name = self._method_c_name(vt, method, 1 + len(expr.args))
                rt = self._func_return_types.get(fn_name)
                if rt:
                    return self._resolve_struct_name(rt)
        return None

    def _resolve_struct_name(self, name):
        if name in self._struct_methods:
            return name
        for sn in self._struct_methods:
            if sn.endswith('_' + name):
                return sn
        return name

    def _is_ptr_var(self, name):
        return name in self._ptr_vars

    def _type_expr_stars(self, te):
        """Pointer depth of a type expr. Arrays decay to pointers."""
        depth = 0
        while isinstance(te, (TypePointer, TypeArray)):
            depth += 1
            te = te.base
        return depth

    def _expr_stars(self, e):
        """Number of pointer indirections in `e`'s C type. 1 or more means
        the member access on it must use `->` instead of `.`."""
        if isinstance(e, ExprIdent):
            if e.name == 'self':
                return 1
            te = self._var_type_exprs.get(e.name)
            if te is not None:
                return self._type_expr_stars(te)
            if self._is_ptr_var(e.name):
                return 1
            return 0
        if isinstance(e, ExprParen):
            return self._expr_stars(e.expr)
        if isinstance(e, ExprCast):
            return 1 if isinstance(e.type_expr, TypePointer) else 0
        if isinstance(e, (ExprDot, ExprArrow)):
            base = self._var_type(e.object)
            if base:
                fc = self._struct_field_c.get((base, e.member))
                if fc is not None:
                    return fc.count('*')
            return 0
        if isinstance(e, ExprIndex):
            return max(self._expr_stars(e.object) - 1, 0)
        if isinstance(e, ExprDeref):
            return max(self._expr_stars(e.operand) - 1, 0)
        return 0

    def _generate_stmt(self, stmt):
        if isinstance(stmt, StmtBlock):
            # If this block contains only var declarations (e.g. from multi-var),
            # emit them as a single comma-separated declaration
            all_vars = all(isinstance(s, StmtVar) for s in stmt.stmts)
            if all_vars and len(stmt.stmts) > 1:
                first = stmt.stmts[0]
                c_type = self.type_to_c(first.type_expr) if first.type_expr else 'int'
                names = []
                for s in stmt.stmts:
                    c_name = s.name
                    if s.type_expr:
                        if isinstance(s.type_expr, TypeIdent):
                            self._var_types[s.name] = s.type_expr.name
                        elif isinstance(s.type_expr, TypePointer) and isinstance(s.type_expr.base, TypeIdent):
                            self._var_types[s.name] = s.type_expr.base.name
                        elif isinstance(s.type_expr, TypeGeneric):
                            self._var_types[s.name] = self.resolved_type_name(s.type_expr)
                        self._var_type_exprs[s.name] = s.type_expr
                        if isinstance(s.type_expr, (TypePointer, TypeArray)):
                            self._ptr_vars.add(s.name)
                    if s.value:
                        names.append(f'{c_name} = {self.expr_to_c(s.value)}')
                    else:
                        names.append(c_name)
                self.emit_c(f'{c_type} {", ".join(names)};')
                return
            saved_depth = len(self._defer_stack)
            self.emit_c('{')
            self.indent_level += 1
            for s in stmt.stmts:
                self._generate_stmt(s)
            # Emit defers added within this block (LIFO)
            while len(self._defer_stack) > saved_depth:
                body = self._defer_stack.pop()
                self._generate_stmt(body)
            self.indent_level -= 1
            self.emit_c('}')

        elif isinstance(stmt, StmtVar):
            c_type = self.type_to_c(stmt.type_expr) if stmt.type_expr else 'int'
            c_name = stmt.name
            if stmt.type_expr:
                if isinstance(stmt.type_expr, TypeIdent):
                    self._var_types[stmt.name] = stmt.type_expr.name
                elif isinstance(stmt.type_expr, TypePointer) and isinstance(stmt.type_expr.base, TypeIdent):
                    self._var_types[stmt.name] = stmt.type_expr.base.name
                elif isinstance(stmt.type_expr, TypeGeneric):
                    self._var_types[stmt.name] = self.resolved_type_name(stmt.type_expr)
                self._var_type_exprs[stmt.name] = stmt.type_expr
                if isinstance(stmt.type_expr, (TypePointer, TypeArray)):
                    self._ptr_vars.add(stmt.name)
            if isinstance(stmt.type_expr, TypeArray) and stmt.type_expr.size:
                c_base = self.type_to_c(stmt.type_expr.base)
                c_size = self.expr_to_c(stmt.type_expr.size)
                if stmt.value:
                    self.emit_c(f'{c_base} {c_name}[{c_size}] = {self.expr_to_c(stmt.value)};')
                else:
                    self.emit_c(f'{c_base} {c_name}[{c_size}];')
            else:
                if stmt.value:
                    self.emit_c(f'{c_type} {c_name} = {self.expr_to_c(stmt.value)};')
                else:
                    self.emit_c(f'{c_type} {c_name};')

        elif isinstance(stmt, StmtAssign):
            self.emit_c(f'{self.expr_to_c(stmt.target)} {stmt.op} {self.expr_to_c(stmt.value)};')

        elif isinstance(stmt, StmtReturn):
            # Emit pending defers before returning
            while self._defer_stack:
                body = self._defer_stack.pop()
                self._generate_stmt(body)
            if stmt.is_noreturn:
                self.emit_c('__builtin_unreachable();')
            elif stmt.value:
                self.emit_c(f'return {self.expr_to_c(stmt.value)};')
            else:
                self.emit_c('return;')

        elif isinstance(stmt, StmtIf):
            self.emit_c(f'if ({self.expr_to_c(stmt.condition)})')
            self._generate_stmt(stmt.then_block)
            if stmt.else_block:
                else_s = stmt.else_block.stmts
                if len(else_s) == 1 and isinstance(else_s[0], StmtIf):
                    self.emit_c('else')
                    self._generate_stmt(else_s[0])
                else:
                    self.emit_c('else')
                    self._generate_stmt(stmt.else_block)

        elif isinstance(stmt, StmtFor):
            init = self.expr_to_c(stmt.init) if stmt.init else ''
            cond = self.expr_to_c(stmt.condition) if stmt.condition else ''
            incr = self.expr_to_c(stmt.increment) if stmt.increment else ''
            # Handle var declaration in init
            if isinstance(stmt.init, StmtVar):
                c_type = self.type_to_c(stmt.init.type_expr) if stmt.init.type_expr else 'int'
                init = f'{c_type} {stmt.init.name}'
                if stmt.init.value:
                    init += f' = {self.expr_to_c(stmt.init.value)}'
            elif isinstance(stmt.init, StmtExpr):
                init = self.expr_to_c(stmt.init.expr)
            elif stmt.init is None:
                init = ''
            else:
                init = ''

            self._loop_depth += 1
            self.emit_c(f'for ({init}; {cond}; {incr})')
            self._generate_stmt(stmt.body)
            self._loop_depth -= 1

        elif isinstance(stmt, StmtForIn):
            self._loop_depth += 1
            self.emit_c(f'for (i32 __i = 0; __i < {self.expr_to_c(stmt.iterable)}.len; __i += 1)')
            self._loop_depth += 1
            c_type = 'auto'
            init_decl = f'{c_type} {stmt.name} = {self.expr_to_c(stmt.iterable)}.ptr[__i]'
            self.emit_c('{')
            self.emit_c(f'{init_decl};')
            self._generate_stmt(stmt.body)
            self.emit_c('}')
            self._loop_depth -= 2

        elif isinstance(stmt, StmtWhile):
            self._loop_depth += 1
            self.emit_c(f'while ({self.expr_to_c(stmt.condition)})')
            self._generate_stmt(stmt.body)
            self._loop_depth -= 1

        elif isinstance(stmt, StmtLoop):
            self._loop_depth += 1
            self.emit_c('for (;;)')
            self._generate_stmt(stmt.body)
            self._loop_depth -= 1

        elif isinstance(stmt, StmtExpr):
            self.emit_c(f'{self.expr_to_c(stmt.expr)};')

        elif isinstance(stmt, StmtAssert):
            self.emit_c(f'assert({self.expr_to_c(stmt.condition)});')

        elif isinstance(stmt, StmtAsm):
            body = stmt.body.strip()
            if body.startswith('asm'):
                # raw source text: 'asm volatile { ... }' -> paren form
                inner = body[3:].strip()
                for kw in ('volatile', 'inline', '__volatile__', '__inline__'):
                    if inner.startswith(kw):
                        inner = inner[len(kw):].strip()
                while inner and inner[0] in '({':
                    inner = inner[1:]
                if inner.endswith('}') or inner.endswith(')'):
                    inner = inner[:-1].rstrip()
                inner = _asm_type_fix(inner)
                self.emit_c(f'asm ({inner});')
            else:
                # fallback: token-derived text
                self.emit_c(f'asm {{ {body} }};')

        elif isinstance(stmt, StmtDefer):
            self._defer_stack.append(stmt.body)

        elif isinstance(stmt, StmtSwitch):
            self.emit_c(f'switch ({self.expr_to_c(stmt.cond)})')
            self.emit_c('{')
            self.indent_level += 1
            for case in stmt.cases:
                self.emit_c(f'case {self.expr_to_c(case.value)}:')
                self.indent_level += 1
                for s in case.body:
                    self._generate_stmt(s)
                self.indent_level -= 1
            if stmt.default_body:
                self.emit_c('default:')
                self.indent_level += 1
                for s in stmt.default_body:
                    self._generate_stmt(s)
                self.indent_level -= 1
            self.indent_level -= 1
            self.emit_c('}')

        elif isinstance(stmt, StmtBreak):
            self.emit_c('break;')

        elif isinstance(stmt, StmtContinue):
            self.emit_c('continue;')

    # Write Output Files

    def write_files(self):
        fname = self.module_name.replace('::', '_').replace('.', '_')
        header_path = os.path.join(self.output_dir, f'{fname}.h')
        source_path = os.path.join(self.output_dir, f'{fname}.c')

        h_content, c_content = self.generate(self._program)

        with open(header_path, 'w') as f:
            f.write(h_content)
        with open(source_path, 'w') as f:
            f.write(c_content)

        return header_path, source_path


def generate(program, module_name=None, output_dir='.'):
    if module_name:
        cg = Codegen(module_name, output_dir)
    else:
        mod_name = program.module_name or 'main'
        cg = Codegen(mod_name, output_dir)

    cg._program = program
    return cg.generate(program)
