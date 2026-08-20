from coral_ast import *

class MonomorphisationError(Exception):
    pass

def deep_copy_type(typ, subst):
    if isinstance(typ, TypeIdent):
        if typ.name in subst:
            return subst[typ.name]
        return TypeIdent(typ.name, line=typ.line, col=typ.col)
    if isinstance(typ, TypePointer):
        return TypePointer(deep_copy_type(typ.base, subst), const=typ.const,
                           line=typ.line, col=typ.col)
    if isinstance(typ, TypeArray):
        return TypeArray(deep_copy_type(typ.base, subst),
                         deep_copy_expr(typ.size, subst) if typ.size is not None else None,
                         line=typ.line, col=typ.col)
    if isinstance(typ, TypeGeneric):
        return TypeGeneric(typ.name,
                           [deep_copy_type(a, subst) for a in typ.args],
                           line=typ.line, col=typ.col)
    if isinstance(typ, TypeFunc):
        return TypeFunc([deep_copy_type(p, subst) for p in typ.param_types],
                        deep_copy_type(typ.return_type, subst),
                        line=typ.line, col=typ.col)
    return typ

def deep_copy_expr(expr, subst):
    if isinstance(expr, ExprInt):
        return ExprInt(expr.value, line=expr.line, col=expr.col, suffix=expr.suffix)
    if isinstance(expr, ExprFloat):
        return ExprFloat(expr.value, line=expr.line, col=expr.col)
    if isinstance(expr, ExprString):
        return ExprString(expr.value, line=expr.line, col=expr.col)
    if isinstance(expr, ExprChar):
        return ExprChar(expr.value, line=expr.line, col=expr.col)
    if isinstance(expr, ExprBool):
        return ExprBool(expr.value, line=expr.line, col=expr.col)
    if isinstance(expr, ExprNull):
        return ExprNull(line=expr.line, col=expr.col)
    if isinstance(expr, ExprIdent):
        parts = expr.name.split('::')
        new_parts = []
        for p in parts:
            if p in subst:
                v = subst[p]
                if not isinstance(v, (TypeIdent, TypePointer, TypeArray, TypeGeneric, TypeFunc)):
                    return deep_copy_expr(v, subst)
                new_parts.append(v.name)
            else:
                new_parts.append(p)
        return ExprIdent('::'.join(new_parts), line=expr.line, col=expr.col)
    if isinstance(expr, ExprUnary):
        return ExprUnary(expr.op, deep_copy_expr(expr.operand, subst),
                         is_postfix=expr.is_postfix,
                         line=expr.line, col=expr.col)
    if isinstance(expr, ExprBinary):
        return ExprBinary(expr.op,
                          deep_copy_expr(expr.left, subst),
                          deep_copy_expr(expr.right, subst),
                          line=expr.line, col=expr.col)
    if isinstance(expr, ExprTernary):
        return ExprTernary(deep_copy_expr(expr.condition, subst),
                           deep_copy_expr(expr.then_expr, subst),
                           deep_copy_expr(expr.else_expr, subst),
                           line=expr.line, col=expr.col)
    if isinstance(expr, ExprCall):
        return ExprCall(deep_copy_expr(expr.callee, subst),
                        [deep_copy_expr(a, subst) for a in expr.args],
                        line=expr.line, col=expr.col)
    if isinstance(expr, ExprDot):
        return ExprDot(deep_copy_expr(expr.object, subst), expr.member,
                       line=expr.line, col=expr.col)
    if isinstance(expr, ExprArrow):
        return ExprArrow(deep_copy_expr(expr.object, subst), expr.member,
                         line=expr.line, col=expr.col)
    if isinstance(expr, ExprIndex):
        return ExprIndex(deep_copy_expr(expr.object, subst),
                         deep_copy_expr(expr.index, subst),
                         line=expr.line, col=expr.col)
    if isinstance(expr, ExprDeref):
        return ExprDeref(deep_copy_expr(expr.operand, subst),
                         line=expr.line, col=expr.col)
    if isinstance(expr, ExprAddrOf):
        return ExprAddrOf(deep_copy_expr(expr.operand, subst),
                          line=expr.line, col=expr.col)
    if isinstance(expr, ExprCast):
        return ExprCast(deep_copy_type(expr.type_expr, subst),
                        deep_copy_expr(expr.operand, subst),
                        line=expr.line, col=expr.col)
    if isinstance(expr, ExprSizeof):
        return ExprSizeof(deep_copy_type(expr.type_expr, subst),
                          line=expr.line, col=expr.col)
    if isinstance(expr, ExprParen):
        return ExprParen(deep_copy_expr(expr.expr, subst),
                         line=expr.line, col=expr.col)
    if isinstance(expr, ExprTypeLiteral):
        return ExprTypeLiteral(deep_copy_type(expr.type_expr, subst),
                               line=expr.line, col=expr.col)
    if isinstance(expr, ExprModulePath):
        return ExprModulePath(list(expr.parts), line=expr.line, col=expr.col)
    if isinstance(expr, ExprGenericInst):
        return ExprGenericInst(deep_copy_expr(expr.base, subst),
                               [deep_copy_type(a, subst) if isinstance(a, (TypeIdent, TypePointer, TypeArray, TypeGeneric, TypeFunc))
                                else deep_copy_expr(a, subst) for a in expr.type_args],
                               line=expr.line, col=expr.col)
    if isinstance(expr, ExprInitializer):
        new_fields = []
        for f in expr.fields:
            if isinstance(f, tuple) and len(f) == 2:
                new_fields.append((f[0], deep_copy_expr(f[1], subst)))
            else:
                new_fields.append(deep_copy_expr(f, subst))
        return ExprInitializer(new_fields, line=expr.line, col=expr.col)
    return expr

def deep_copy_stmt(stmt, subst):
    if isinstance(stmt, StmtBlock):
        return StmtBlock([deep_copy_stmt(s, subst) for s in stmt.stmts],
                         line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtVar):
        return StmtVar(stmt.name,
                       deep_copy_type(stmt.type_expr, subst) if stmt.type_expr else None,
                       deep_copy_expr(stmt.value, subst) if stmt.value else None,
                       line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtAssign):
        return StmtAssign(deep_copy_expr(stmt.target, subst),
                          deep_copy_expr(stmt.value, subst),
                          op=stmt.op, line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtReturn):
        return StmtReturn(deep_copy_expr(stmt.value, subst) if stmt.value else None,
                          is_noreturn=stmt.is_noreturn,
                          line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtIf):
        return StmtIf(deep_copy_expr(stmt.condition, subst),
                      deep_copy_stmt(stmt.then_block, subst),
                      deep_copy_stmt(stmt.else_block, subst) if stmt.else_block else None,
                      line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtFor):
        return StmtFor(deep_copy_expr(stmt.init, subst) if stmt.init else None,
                       deep_copy_expr(stmt.condition, subst) if stmt.condition else None,
                       deep_copy_expr(stmt.increment, subst) if stmt.increment else None,
                       deep_copy_stmt(stmt.body, subst),
                       line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtForIn):
        return StmtForIn(stmt.name,
                         deep_copy_expr(stmt.iterable, subst),
                         deep_copy_stmt(stmt.body, subst),
                         line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtWhile):
        return StmtWhile(deep_copy_expr(stmt.condition, subst),
                         deep_copy_stmt(stmt.body, subst),
                         line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtLoop):
        return StmtLoop(deep_copy_stmt(stmt.body, subst),
                        line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtExpr):
        return StmtExpr(deep_copy_expr(stmt.expr, subst),
                        line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtAssert):
        return StmtAssert(deep_copy_expr(stmt.condition, subst),
                          line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtAsm):
        return StmtAsm(stmt.body, line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtDefer):
        return StmtDefer(deep_copy_stmt(stmt.body, subst),
                         line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtBreak):
        return StmtBreak(line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtContinue):
        return StmtContinue(line=stmt.line, col=stmt.col)
    if isinstance(stmt, StmtSwitch):
        new_cases = []
        for c in stmt.cases:
            new_cases.append(StmtCase(c.value,
                                      [deep_copy_stmt(s, subst) for s in c.body],
                                      line=c.line, col=c.col))
        return StmtSwitch(deep_copy_expr(stmt.cond, subst), new_cases,
                          [deep_copy_stmt(s, subst) for s in stmt.default_body] if stmt.default_body else None,
                          line=stmt.line, col=stmt.col)
    return stmt


def type_to_suffix(typ):
    """Convert a type to a name suffix for monomorphised functions."""
    if isinstance(typ, TypeIdent):
        name = typ.name.replace('::', '_').replace('.', '_')
        if name == '*':
            return 'ptr'
        if name == 'self':
            return 'self'
        return name
    if isinstance(typ, TypePointer):
        return type_to_suffix(typ.base) + '_ptr'
    if isinstance(typ, TypeGeneric):
        base = typ.name.replace('::', '_').replace('.', '_')
        args = '_'.join(type_to_suffix(a) for a in typ.args)
        return f'{base}_{args}'
    if isinstance(typ, TypeArray):
        return type_to_suffix(typ.base) + '_arr'
    if isinstance(typ, ExprInt):
        return str(typ.value)
    if isinstance(typ, ExprFloat):
        return str(typ.value).replace('.', '_')
    return 'unknown'


def collect_generic_funcs(decls):
    generic_funcs = {}
    for decl in decls:
        if isinstance(decl, DeclFunc) and decl.generic_params:
            key = (decl.name, len(decl.generic_params))
            if key not in generic_funcs:
                generic_funcs[key] = decl
    return generic_funcs


def find_generic_calls(expr, generic_funcs, program):
    """Walk expression tree and find generic instantiations used as calls."""
    instantiations = []
    if isinstance(expr, ExprCall):
        callee = expr.callee
        if isinstance(callee, ExprGenericInst):
            base = callee.base
            if isinstance(base, ExprIdent):
                func_name = base.name
            elif isinstance(base, ExprDot):
                func_name = base.member  # module-qualified: mman.alloc<T>
            else:
                func_name = None
            if func_name:
                # Strip module prefix (e.g., "mman::alloc" -> "alloc")
                parts = func_name.split('::')
                short_name = parts[-1]
                type_args = callee.type_args
                n_params = len(type_args)
                key = (short_name, n_params)
                if key in generic_funcs:
                    instantiations.append((generic_funcs[key], type_args))
        # Also check children of the call
        for arg in expr.args:
            instantiations.extend(find_generic_calls(arg, generic_funcs, program))
        instantiations.extend(find_generic_calls(callee, generic_funcs, program))
    elif isinstance(expr, ExprBinary):
        instantiations.extend(find_generic_calls(expr.left, generic_funcs, program))
        instantiations.extend(find_generic_calls(expr.right, generic_funcs, program))
    elif isinstance(expr, ExprUnary):
        instantiations.extend(find_generic_calls(expr.operand, generic_funcs, program))
    elif isinstance(expr, ExprTernary):
        instantiations.extend(find_generic_calls(expr.condition, generic_funcs, program))
        instantiations.extend(find_generic_calls(expr.then_expr, generic_funcs, program))
        instantiations.extend(find_generic_calls(expr.else_expr, generic_funcs, program))
    elif isinstance(expr, ExprParen):
        instantiations.extend(find_generic_calls(expr.expr, generic_funcs, program))
    elif isinstance(expr, ExprCast):
        instantiations.extend(find_generic_calls(expr.operand, generic_funcs, program))
    elif isinstance(expr, ExprAddrOf):
        instantiations.extend(find_generic_calls(expr.operand, generic_funcs, program))
    elif isinstance(expr, ExprDeref):
        instantiations.extend(find_generic_calls(expr.operand, generic_funcs, program))
    elif isinstance(expr, ExprIndex):
        instantiations.extend(find_generic_calls(expr.object, generic_funcs, program))
        instantiations.extend(find_generic_calls(expr.index, generic_funcs, program))
    elif isinstance(expr, ExprDot):
        instantiations.extend(find_generic_calls(expr.object, generic_funcs, program))
    elif isinstance(expr, ExprArrow):
        instantiations.extend(find_generic_calls(expr.object, generic_funcs, program))
    elif isinstance(expr, ExprInitializer):
        for f in expr.fields:
            if isinstance(f, tuple) and len(f) == 2:
                instantiations.extend(find_generic_calls(f[1], generic_funcs, program))
            else:
                instantiations.extend(find_generic_calls(f, generic_funcs, program))
    return instantiations


def find_generic_calls_in_stmt(stmt, generic_funcs, program):
    instantiations = []
    if isinstance(stmt, StmtVar):
        if stmt.value:
            instantiations.extend(find_generic_calls(stmt.value, generic_funcs, program))
    elif isinstance(stmt, StmtAssign):
        instantiations.extend(find_generic_calls(stmt.target, generic_funcs, program))
        instantiations.extend(find_generic_calls(stmt.value, generic_funcs, program))
    elif isinstance(stmt, StmtReturn):
        if stmt.value:
            instantiations.extend(find_generic_calls(stmt.value, generic_funcs, program))
    elif isinstance(stmt, StmtIf):
        instantiations.extend(find_generic_calls(stmt.condition, generic_funcs, program))
        instantiations.extend(find_generic_calls_in_stmt(stmt.then_block, generic_funcs, program))
        if stmt.else_block:
            instantiations.extend(find_generic_calls_in_stmt(stmt.else_block, generic_funcs, program))
    elif isinstance(stmt, StmtExpr):
        instantiations.extend(find_generic_calls(stmt.expr, generic_funcs, program))
    elif isinstance(stmt, StmtBlock):
        for s in stmt.stmts:
            instantiations.extend(find_generic_calls_in_stmt(s, generic_funcs, program))
    elif isinstance(stmt, StmtFor):
        if stmt.init:
            instantiations.extend(find_generic_calls(stmt.init, generic_funcs, program))
        if stmt.condition:
            instantiations.extend(find_generic_calls(stmt.condition, generic_funcs, program))
        if stmt.increment:
            instantiations.extend(find_generic_calls(stmt.increment, generic_funcs, program))
        instantiations.extend(find_generic_calls_in_stmt(stmt.body, generic_funcs, program))
    elif isinstance(stmt, StmtForIn):
        instantiations.extend(find_generic_calls(stmt.iterable, generic_funcs, program))
        instantiations.extend(find_generic_calls_in_stmt(stmt.body, generic_funcs, program))
    elif isinstance(stmt, StmtWhile):
        instantiations.extend(find_generic_calls(stmt.condition, generic_funcs, program))
        instantiations.extend(find_generic_calls_in_stmt(stmt.body, generic_funcs, program))
    elif isinstance(stmt, StmtLoop):
        instantiations.extend(find_generic_calls_in_stmt(stmt.body, generic_funcs, program))
    elif isinstance(stmt, StmtAssert):
        instantiations.extend(find_generic_calls(stmt.condition, generic_funcs, program))
    elif isinstance(stmt, StmtSwitch):
        instantiations.extend(find_generic_calls(stmt.cond, generic_funcs, program))
        for case in stmt.cases:
            for s in case.body:
                instantiations.extend(find_generic_calls_in_stmt(s, generic_funcs, program))
        if stmt.default_body:
            for s in stmt.default_body:
                instantiations.extend(find_generic_calls_in_stmt(s, generic_funcs, program))
    elif isinstance(stmt, StmtDefer):
        instantiations.extend(find_generic_calls_in_stmt(stmt.body, generic_funcs, program))
    return instantiations


def collect_generic_structs(decls):
    generic_structs = {}
    for decl in decls:
        if isinstance(decl, DeclStruct) and decl.generic_params:
            generic_structs[decl.name] = decl
            if decl.alias:
                generic_structs[f'{decl.alias}_{decl.name}'] = decl
    return generic_structs


def find_generic_types_in_type(typ, generic_structs, program):
    """Find generic struct type references used in a type tree."""
    refs = []
    if isinstance(typ, TypeGeneric):
        base = typ.name.split('::')[-1].split('.')[-1]
        if base in generic_structs:
            refs.append((generic_structs[base], typ.args))
        for a in typ.args:
            refs.extend(find_generic_types_in_type(a, generic_structs, program))
    elif isinstance(typ, TypePointer):
        refs.extend(find_generic_types_in_type(typ.base, generic_structs, program))
    elif isinstance(typ, TypeArray):
        refs.extend(find_generic_types_in_type(typ.base, generic_structs, program))
    elif isinstance(typ, TypeFunc):
        refs.extend(find_generic_types_in_type(typ.return_type, generic_structs, program))
        for p in typ.param_types:
            refs.extend(find_generic_types_in_type(p, generic_structs, program))
    return refs


def find_generic_types_in_expr(expr, generic_structs, program):
    refs = []
    if isinstance(expr, ExprGenericInst):
        for a in expr.type_args:
            if isinstance(a, (TypeIdent, TypePointer, TypeArray, TypeGeneric, TypeFunc)):
                refs.extend(find_generic_types_in_type(a, generic_structs, program))
        if isinstance(expr.base, ExprIdent):
            base_name = expr.base.name
            if base_name in generic_structs:
                refs.append((generic_structs[base_name], expr.type_args))
    elif isinstance(expr, ExprCast):
        refs.extend(find_generic_types_in_type(expr.type_expr, generic_structs, program))
        refs.extend(find_generic_types_in_expr(expr.operand, generic_structs, program))
    elif isinstance(expr, ExprSizeof):
        refs.extend(find_generic_types_in_type(expr.type_expr, generic_structs, program))
    elif isinstance(expr, ExprCall):
        refs.extend(find_generic_types_in_expr(expr.callee, generic_structs, program))
        for a in expr.args:
            refs.extend(find_generic_types_in_expr(a, generic_structs, program))
    elif isinstance(expr, ExprDot):
        refs.extend(find_generic_types_in_expr(expr.object, generic_structs, program))
    elif isinstance(expr, ExprArrow):
        refs.extend(find_generic_types_in_expr(expr.object, generic_structs, program))
    elif isinstance(expr, ExprUnary):
        refs.extend(find_generic_types_in_expr(expr.operand, generic_structs, program))
    elif isinstance(expr, ExprBinary):
        refs.extend(find_generic_types_in_expr(expr.left, generic_structs, program))
        refs.extend(find_generic_types_in_expr(expr.right, generic_structs, program))
    elif isinstance(expr, ExprParen):
        refs.extend(find_generic_types_in_expr(expr.expr, generic_structs, program))
    elif isinstance(expr, ExprAddrOf):
        refs.extend(find_generic_types_in_expr(expr.operand, generic_structs, program))
    elif isinstance(expr, ExprDeref):
        refs.extend(find_generic_types_in_expr(expr.operand, generic_structs, program))
    elif isinstance(expr, ExprIndex):
        refs.extend(find_generic_types_in_expr(expr.object, generic_structs, program))
        refs.extend(find_generic_types_in_expr(expr.index, generic_structs, program))
    elif isinstance(expr, ExprTernary):
        refs.extend(find_generic_types_in_expr(expr.condition, generic_structs, program))
        refs.extend(find_generic_types_in_expr(expr.then_expr, generic_structs, program))
        refs.extend(find_generic_types_in_expr(expr.else_expr, generic_structs, program))
    elif isinstance(expr, ExprInitializer):
        for f in expr.fields:
            if isinstance(f, tuple) and len(f) == 2:
                refs.extend(find_generic_types_in_expr(f[1], generic_structs, program))
            else:
                refs.extend(find_generic_types_in_expr(f, generic_structs, program))
    return refs


def find_generic_types_in_stmt(stmt, generic_structs, program):
    refs = []
    if isinstance(stmt, StmtVar):
        if stmt.type_expr:
            refs.extend(find_generic_types_in_type(stmt.type_expr, generic_structs, program))
        if stmt.value:
            refs.extend(find_generic_types_in_expr(stmt.value, generic_structs, program))
    elif isinstance(stmt, StmtAssign):
        refs.extend(find_generic_types_in_expr(stmt.target, generic_structs, program))
        refs.extend(find_generic_types_in_expr(stmt.value, generic_structs, program))
    elif isinstance(stmt, StmtReturn):
        if stmt.value:
            refs.extend(find_generic_types_in_expr(stmt.value, generic_structs, program))
    elif isinstance(stmt, StmtExpr):
        refs.extend(find_generic_types_in_expr(stmt.expr, generic_structs, program))
    elif isinstance(stmt, StmtIf):
        refs.extend(find_generic_types_in_expr(stmt.condition, generic_structs, program))
        refs.extend(find_generic_types_in_stmt(stmt.then_block, generic_structs, program))
        if stmt.else_block:
            refs.extend(find_generic_types_in_stmt(stmt.else_block, generic_structs, program))
    elif isinstance(stmt, StmtBlock):
        for s in stmt.stmts:
            refs.extend(find_generic_types_in_stmt(s, generic_structs, program))
    elif isinstance(stmt, StmtFor):
        if stmt.init:
            refs.extend(find_generic_types_in_expr(stmt.init, generic_structs, program))
        if stmt.condition:
            refs.extend(find_generic_types_in_expr(stmt.condition, generic_structs, program))
        if stmt.increment:
            refs.extend(find_generic_types_in_expr(stmt.increment, generic_structs, program))
        refs.extend(find_generic_types_in_stmt(stmt.body, generic_structs, program))
    elif isinstance(stmt, StmtWhile):
        refs.extend(find_generic_types_in_expr(stmt.condition, generic_structs, program))
        refs.extend(find_generic_types_in_stmt(stmt.body, generic_structs, program))
    elif isinstance(stmt, StmtLoop):
        refs.extend(find_generic_types_in_stmt(stmt.body, generic_structs, program))
    elif isinstance(stmt, StmtAssert):
        refs.extend(find_generic_types_in_expr(stmt.condition, generic_structs, program))
    elif isinstance(stmt, StmtSwitch):
        refs.extend(find_generic_types_in_expr(stmt.cond, generic_structs, program))
        for case in stmt.cases:
            for s in case.body:
                refs.extend(find_generic_types_in_stmt(s, generic_structs, program))
        if stmt.default_body:
            for s in stmt.default_body:
                refs.extend(find_generic_types_in_stmt(s, generic_structs, program))
    elif isinstance(stmt, StmtForIn):
        refs.extend(find_generic_types_in_expr(stmt.iterable, generic_structs, program))
        refs.extend(find_generic_types_in_stmt(stmt.body, generic_structs, program))
    elif isinstance(stmt, StmtDefer):
        refs.extend(find_generic_types_in_stmt(stmt.body, generic_structs, program))
    return refs


_inst_context = None


def _friendly(inst_label, e):
    """Turn a raw exception from a generic instantiation into a useful
    explanation with the instantiation site named."""
    msg = str(e)
    if isinstance(e, AttributeError):
        if 'name' in msg and ('ExprInt' in msg or 'ExprFloat' in msg):
            detail = ('an expression (a number literal) was used where a type '
                      'was expected — a generic parameter may have been given '
                      'a value instead of a type argument')
        else:
            detail = f'internal processing error: {msg}'
        return MonomorphisationError(f'{inst_label}: {detail}')
    if isinstance(e, TypeError):
        return MonomorphisationError(f'{inst_label}: {msg}')
    return MonomorphisationError(f'{inst_label}: {msg}')


def instantiate_generic_struct(template_struct, type_args):
    subst = {}
    label = (f"instantiation of generic struct '{template_struct.name}' with "
             f'[{", ".join(type_to_suffix(a) for a in type_args)}]')
    global _inst_context
    prev_context = _inst_context
    _inst_context = label
    try:
        return _instantiate_generic_struct_impl(template_struct, type_args)
    except MonomorphisationError:
        raise
    except Exception as e:
        raise _friendly(label, e) from None
    finally:
        _inst_context = prev_context


def _instantiate_generic_struct_impl(template_struct, type_args):
    if len(type_args) != len(template_struct.generic_params):
        raise MonomorphisationError(
            f"generic struct '{template_struct.name}' expects "
            f"{len(template_struct.generic_params)} argument(s) "
            f"({', '.join(template_struct.generic_params)}), but got "
            f"{len(type_args)} — count the types in your '<...>' list")
    subst = {}
    for param_name, arg_type in zip(template_struct.generic_params, type_args):
        subst[param_name] = arg_type

    suffix = '_'.join(type_to_suffix(a) for a in type_args)
    if template_struct.alias:
        struct_name = (f'{template_struct.alias}_{template_struct.name}_{suffix}')
    else:
        struct_name = f'{template_struct.name}_{suffix}'
    
    new_fields = []
    for f in template_struct.fields:
        new_fields.append(
            StructField(f.name, deep_copy_type(f.type_expr, subst),
                        line=f.line, col=f.col))

    new_methods = []
    for m in template_struct.methods:
        new_params = []
        for p in m.params:
            new_params.append(
                Param(p.name, deep_copy_type(p.type_expr, subst),
                      line=p.line, col=p.col))
        new_body = deep_copy_stmt(m.body, subst) if m.body else None
        new_return = deep_copy_type(m.return_type, subst) if m.return_type else None
        new_methods.append(
            DeclFunc(
                m.name, new_return, new_params,
                generic_params=[], body=new_body,
                exported=m.exported, static=m.static,
                is_method=m.is_method, struct_name=struct_name,
                trait_name=m.trait_name, extern=m.extern,
                inline=m.inline,
                calling_conv=m.calling_conv, noreturn=m.noreturn,
                line=m.line, col=m.col, alias=template_struct.alias))

    new_struct = DeclStruct(
        struct_name,
        generic_params=[],
        fields=new_fields,
        methods=new_methods,
        exported=template_struct.exported,
        line=template_struct.line,
        col=template_struct.col,
        alias=template_struct.alias)
    return new_struct


def monomorphise(program):
    """Pre-pass to monomorphise generic functions and structs.
    Iterates to fixpoint so cloned function bodies are also scanned.
    """
    try:
        _monomorphise_impl(program)
    except MonomorphisationError:
        raise
    except Exception as e:
        ctx = f' (while instantiating {_inst_context})' if _inst_context else ''
        raise MonomorphisationError(
            f'{type(e).__name__}: {e}{ctx} — this is a bug in the compiler; '
            f'the failing construct is likely a complex generic '
            f'instantiation.') from None

    # Give every top-level decl its module-alias prefix and update all
    # references, so codegen emits stable {alias}_{name} C names. This
    # must run on every path (the instantiation loop above may return
    # early when only struct generics are in play), so it lives here.
    mangle_aliases(program)


def mangle_type_refs(program):
    """Prefix-mangle ONLY type references (fields, params, returns, generic
    call args, casts...) using each decl's module alias. Runs BEFORE the
    instantiation loop so monomorphised names are derived from the final
    {alias}_{name} forms and stay consistent with the mangled references.
    """
    name_map = {}
    for decl in program.decls:
        if isinstance(decl, (DeclStruct, DeclEnum, DeclTrait, DeclTypedef,
                             DeclDistinct, DeclConst, DeclVar, DeclFunc)):
            if isinstance(decl, DeclFunc) and decl.extern:
                continue
            name_map[decl.name] = (f'{decl.alias}_{decl.name}'
                                   if decl.alias else decl.name)

    def mangle_type(typ):
        if typ is None:
            return
        if isinstance(typ, TypeIdent):
            if typ.name in name_map:
                typ.name = name_map[typ.name]
        elif isinstance(typ, TypeGeneric):
            if typ.name in name_map:
                typ.name = name_map[typ.name]
            for a in typ.args:
                mangle_type(a)
        elif isinstance(typ, TypePointer):
            mangle_type(typ.base)
        elif isinstance(typ, TypeArray):
            mangle_type(typ.base)
        elif isinstance(typ, TypeFunc):
            mangle_type(typ.return_type)
            for p in typ.param_types:
                mangle_type(p)

    def mangle_expr_types(expr):
        if expr is None:
            return
        if isinstance(expr, ExprGenericInst):
            for a in expr.type_args:
                mangle_type(a)
        elif isinstance(expr, ExprCall):
            mangle_expr_types(expr.callee)
            for a in expr.args:
                mangle_expr_types(a)
        elif isinstance(expr, (ExprDot, ExprArrow)):
            mangle_expr_types(expr.object)
        elif isinstance(expr, ExprParen):
            mangle_expr_types(expr.expr)
        elif isinstance(expr, ExprBinary):
            mangle_expr_types(expr.left)
            mangle_expr_types(expr.right)
        elif isinstance(expr, ExprUnary):
            mangle_expr_types(expr.operand)
        elif isinstance(expr, ExprCast):
            mangle_type(expr.type_expr)
            mangle_expr_types(expr.operand)
        elif isinstance(expr, ExprSizeof):
            mangle_type(expr.type_expr)
        elif isinstance(expr, ExprTypeLiteral):
            mangle_type(expr.type_expr)
        elif isinstance(expr, ExprIndex):
            mangle_expr_types(expr.object)
            mangle_expr_types(expr.index)
        elif isinstance(expr, ExprTernary):
            mangle_expr_types(expr.condition)
            mangle_expr_types(expr.then_expr)
            mangle_expr_types(expr.else_expr)
        elif isinstance(expr, ExprInitializer):
            for f in expr.fields:
                if isinstance(f, tuple) and len(f) == 2:
                    mangle_expr_types(f[1])
                else:
                    mangle_expr_types(f)

    def mangle_stmt(stmt):
        if stmt is None:
            return
        if isinstance(stmt, StmtBlock):
            for s in stmt.stmts:
                mangle_stmt(s)
        elif isinstance(stmt, StmtVar):
            mangle_type(stmt.type_expr)
            mangle_expr_types(stmt.value)
        elif isinstance(stmt, StmtAssign):
            mangle_expr_types(stmt.target)
            mangle_expr_types(stmt.value)
        elif isinstance(stmt, StmtReturn):
            mangle_expr_types(stmt.value)
        elif isinstance(stmt, StmtIf):
            mangle_expr_types(stmt.condition)
            mangle_stmt(stmt.then_block)
            mangle_stmt(stmt.else_block)
        elif isinstance(stmt, StmtFor):
            mangle_expr_types(stmt.init)
            mangle_expr_types(stmt.condition)
            mangle_expr_types(stmt.increment)
            mangle_stmt(stmt.body)
        elif isinstance(stmt, StmtForIn):
            mangle_expr_types(stmt.iterable)
            mangle_stmt(stmt.body)
        elif isinstance(stmt, StmtWhile):
            mangle_expr_types(stmt.condition)
            mangle_stmt(stmt.body)
        elif isinstance(stmt, StmtLoop):
            mangle_stmt(stmt.body)
        elif isinstance(stmt, StmtExpr):
            mangle_expr_types(stmt.expr)
        elif isinstance(stmt, StmtAssert):
            mangle_expr_types(stmt.condition)
        elif isinstance(stmt, StmtSwitch):
            mangle_expr_types(stmt.cond)
            for c in stmt.cases:
                for s in c.body:
                    mangle_stmt(s)
            if stmt.default_body:
                for s in stmt.default_body:
                    mangle_stmt(s)

    for decl in program.decls:
        if isinstance(decl, DeclStruct):
            for f in decl.fields:
                mangle_type(f.type_expr)
            for m in decl.methods:
                mangle_type(m.return_type)
                for p in m.params:
                    mangle_type(p.type_expr)
                if m.body:
                    mangle_stmt(m.body)
        elif isinstance(decl, DeclMethodBlock):
            for m in decl.methods:
                mangle_type(m.return_type)
                for p in m.params:
                    mangle_type(p.type_expr)
                if m.body:
                    mangle_stmt(m.body)
        elif isinstance(decl, DeclFunc):
            mangle_type(decl.return_type)
            for p in decl.params:
                mangle_type(p.type_expr)
            if decl.body:
                mangle_stmt(decl.body)
        elif isinstance(decl, DeclTrait):
            for m in decl.methods:
                mangle_type(m.return_type)
                for p in m.params:
                    mangle_type(p.type_expr)
        elif isinstance(decl, DeclConst):
            mangle_type(decl.type_anno)
            mangle_expr_types(decl.value)
        elif isinstance(decl, DeclVar):
            mangle_type(decl.type_anno)
            mangle_expr_types(decl.value)
        elif isinstance(decl, DeclTypedef):
            mangle_type(decl.type_expr)
        elif isinstance(decl, DeclDistinct):
            mangle_type(decl.type_expr)
        elif isinstance(decl, DeclEnum):
            for v in decl.variants:
                mangle_expr_types(v.value)


def _monomorphise_impl(program):
    seen_funcs = set()
    seen_structs = set()
    max_iters = 100

    # Prefix-mangle type references before instantiation so the names of
    # monomorphised structs/functions are consistent with the mangled
    # references in signatures and bodies (nested generics like
    # option<HashMapEntry<K,V>>).
    mangle_type_refs(program)

    for _ in range(max_iters):
        generic_funcs = collect_generic_funcs(program.decls)
        generic_structs = collect_generic_structs(program.decls)

        if not generic_funcs and not generic_structs:
            break

        total_new = 0

        # Collect generic struct references
        struct_refs = []
        for decl in program.decls:
            if isinstance(decl, DeclStruct) and not decl.generic_params:
                for f in decl.fields:
                    struct_refs.extend(find_generic_types_in_type(f.type_expr, generic_structs, program))
                for m in decl.methods:
                    if m.return_type:
                        struct_refs.extend(find_generic_types_in_type(m.return_type, generic_structs, program))
                    for p in m.params:
                        if p.type_expr:
                            struct_refs.extend(find_generic_types_in_type(p.type_expr, generic_structs, program))
                    if m.body:
                        for stmt in m.body.stmts:
                            struct_refs.extend(find_generic_types_in_stmt(stmt, generic_structs, program))
            if isinstance(decl, DeclFunc):
                if decl.return_type:
                    struct_refs.extend(find_generic_types_in_type(decl.return_type, generic_structs, program))
                for p in decl.params:
                    if p.type_expr:
                        struct_refs.extend(find_generic_types_in_type(p.type_expr, generic_structs, program))
                if decl.body:
                    for stmt in decl.body.stmts:
                        struct_refs.extend(find_generic_types_in_stmt(stmt, generic_structs, program))
            elif isinstance(decl, DeclConst):
                if decl.type_anno:
                    struct_refs.extend(find_generic_types_in_type(decl.type_anno, generic_structs, program))
                if decl.value:
                    struct_refs.extend(find_generic_types_in_expr(decl.value, generic_structs, program))
            elif isinstance(decl, DeclVar):
                if decl.type_anno:
                    struct_refs.extend(find_generic_types_in_type(decl.type_anno, generic_structs, program))
                if decl.value:
                    struct_refs.extend(find_generic_types_in_expr(decl.value, generic_structs, program))
            elif isinstance(decl, DeclTypedef):
                if decl.type_expr:
                    struct_refs.extend(find_generic_types_in_type(decl.type_expr, generic_structs, program))

        new_struct_decls = []
        for template_struct, type_args in struct_refs:
            key = (template_struct.name,
                   tuple(type_to_suffix(a) for a in type_args))
            if key in seen_structs:
                continue
            seen_structs.add(key)
            new_struct = instantiate_generic_struct(template_struct, type_args)
            new_struct_decls.append(new_struct)

        total_new += len(new_struct_decls)
        program.decls.extend(new_struct_decls)

        # Collect generic function instantiations
        if not generic_funcs:
            if total_new == 0:
                return
            continue

        instantiations = []
        for decl in program.decls:
            if isinstance(decl, DeclFunc) and not decl.generic_params:
                if decl.body:
                    for stmt in decl.body.stmts:
                        instantiations.extend(
                            find_generic_calls_in_stmt(stmt, generic_funcs, program))
            elif isinstance(decl, DeclStruct) and not decl.generic_params:
                for m in decl.methods:
                    if m.body:
                        for stmt in m.body.stmts:
                            instantiations.extend(
                                find_generic_calls_in_stmt(stmt, generic_funcs, program))
            elif isinstance(decl, DeclConst):
                if decl.value:
                    instantiations.extend(
                        find_generic_calls(decl.value, generic_funcs, program))
            elif isinstance(decl, DeclVar):
                if decl.value:
                    instantiations.extend(
                        find_generic_calls(decl.value, generic_funcs, program))

        new_func_decls = []
        for generic_func, type_args in instantiations:
            key = (generic_func.name,
                   tuple(type_to_suffix(a) for a in type_args))
            if key in seen_funcs:
                continue
            seen_funcs.add(key)

            if len(type_args) != len(generic_func.generic_params):
                raise MonomorphisationError(
                    f"generic function '{generic_func.name}' expects "
                    f"{len(generic_func.generic_params)} argument(s) "
                    f"({', '.join(generic_func.generic_params)}), but got "
                    f"{len(type_args)} — count the types in your call site's "
                    f"'<...>' list")
            subst = {}
            for param_name, arg_type in zip(generic_func.generic_params, type_args):
                subst[param_name] = arg_type

            suffix = '_'.join(type_to_suffix(a) for a in type_args)
            if generic_func.alias:
                mono_name = (f'{generic_func.alias}_{generic_func.name}_{suffix}')
            else:
                mono_name = f'{generic_func.name}_{suffix}'

            mono_func = _clone_func(generic_func, subst, mono_name)
            new_func_decls.append(mono_func)

        total_new += len(new_func_decls)
        program.decls.extend(new_func_decls)

        if total_new == 0:
            break




def _clone_func(generic_func, subst, mono_name):
    new_params = []
    for p in generic_func.params:
        new_params.append(
            Param(p.name, deep_copy_type(p.type_expr, subst),
                  line=p.line, col=p.col))
    new_body = deep_copy_stmt(generic_func.body, subst) if generic_func.body else None
    new_return_type = (deep_copy_type(generic_func.return_type, subst)
                       if generic_func.return_type else None)
    return DeclFunc(
        mono_name, new_return_type, new_params,
        generic_params=[],
        body=new_body,
        exported=generic_func.exported,
        static=generic_func.static,
        is_method=generic_func.is_method,
        struct_name=generic_func.struct_name,
        trait_name=generic_func.trait_name,
        extern=generic_func.extern,
        calling_conv=generic_func.calling_conv,
        noreturn=generic_func.noreturn,
        inline=generic_func.inline,
        line=generic_func.line,
        col=generic_func.col,
        alias=generic_func.alias,
    )


def mangle_aliases(program):
    """Rename every top-level decl and all references to it using the
    module alias prefix, so codegen emits stable `{alias}_{name}` C
    names. Module members are reachable as `alias.name` / `alias::name`
    and as the bare name inside their own module.
    """
    name_map = {}
    module_aliases = set()
    for decl in program.decls:
        if isinstance(decl, DeclImport):
            for a in decl.names:
                module_aliases.add(a)
    # Methods belong to their struct's namespace (Zig model): a method name
    # must never be captured by a module-level decl of the same name. Record
    # every method name first, then only create qualified entries for module
    # functions that do not shadow a method.
    method_names = set()
    for decl in program.decls:
        if isinstance(decl, DeclStruct):
            for meth in decl.methods:
                method_names.add(meth.name)
    for decl in program.decls:
        if isinstance(decl, (DeclStruct, DeclEnum, DeclTrait, DeclTypedef,
                             DeclDistinct, DeclConst, DeclVar, DeclFunc)):
            if isinstance(decl, DeclFunc) and decl.extern:
                continue  # extern decls keep their original C names
            if decl.alias and decl.name.startswith(decl.alias + '_'):
                continue  # already fully mangled (monomorphised name)
            if isinstance(decl, DeclFunc) and decl.name in method_names:
                # Module function shadowing a struct method: keep its qualified
                # name only; the bare name stays bound to the method (Zig).
                m = f'{decl.alias}_{decl.name}' if decl.alias else decl.name
                if decl.alias:
                    name_map[f'{decl.alias}.{decl.name}'] = m
                    name_map[f'{decl.alias}::{decl.name}'] = m
                continue
            m = f'{decl.alias}_{decl.name}' if decl.alias else decl.name
            name_map[decl.name] = m
            if decl.alias:
                name_map[f'{decl.alias}.{decl.name}'] = m
                name_map[f'{decl.alias}::{decl.name}'] = m
            if isinstance(decl, DeclStruct):
                for meth in decl.methods:
                    name_map.setdefault(meth.name, meth.name)

    def _mangle_lookup(alias, name):
        """Map a bare name to its C name. Two modules may both export a
        `name` (e.g. io.repeat and fmt.repeat): the bare entry in name_map
        is last-write-wins, so prefer the current module's qualified entry
        and only fall back to the bare one for root (alias=='') decls."""
        if alias and f'{alias}.{name}' in name_map:
            return name_map[f'{alias}.{name}']
        return name_map.get(name)

    def mangle_type(typ):
        if typ is None:
            return
        if isinstance(typ, TypeIdent):
            if typ.name in name_map:
                typ.name = name_map[typ.name]
        elif isinstance(typ, TypeGeneric):
            if typ.name in name_map:
                typ.name = name_map[typ.name]
            for a in typ.args:
                mangle_type(a)
        elif isinstance(typ, TypePointer):
            mangle_type(typ.base)
        elif isinstance(typ, TypeArray):
            mangle_type(typ.base)
            if typ.size is not None:
                mangle_expr(typ.size, set())
        elif isinstance(typ, TypeFunc):
            mangle_type(typ.return_type)
            for p in typ.param_types:
                mangle_type(p)

    def mangle_expr(expr, locals_, alias=''):
        if expr is None:
            return
        if isinstance(expr, ExprIdent):
            if expr.name in locals_:
                return  # local variable reference, not a decl
            if expr.name in name_map:
                expr.name = _mangle_lookup(alias, expr.name)
            else:
                parts = expr.name.split('::')
                if len(parts) > 1:
                    expr.name = '::'.join(name_map.get(p, p) for p in parts)
        elif isinstance(expr, ExprGenericInst):
            mangle_expr(expr.base, locals_, alias)
            for a in expr.type_args:
                mangle_type(a)
        elif isinstance(expr, ExprUnary):
            mangle_expr(expr.operand, locals_, alias)
        elif isinstance(expr, ExprBinary):
            mangle_expr(expr.left, locals_, alias)
            mangle_expr(expr.right, locals_, alias)
        elif isinstance(expr, ExprTernary):
            mangle_expr(expr.condition, locals_, alias)
            mangle_expr(expr.then_expr, locals_, alias)
            mangle_expr(expr.else_expr, locals_, alias)
        elif isinstance(expr, ExprCall):
            mangle_expr(expr.callee, locals_, alias)
            for a in expr.args:
                mangle_expr(a, locals_, alias)
        elif isinstance(expr, (ExprDot, ExprArrow)):
            obj = expr.object
            if not (isinstance(obj, ExprIdent) and obj.name in module_aliases):
                mangle_expr(obj, locals_, alias)
        elif isinstance(expr, ExprIndex):
            mangle_expr(expr.object, locals_, alias)
            mangle_expr(expr.index, locals_, alias)
        elif isinstance(expr, ExprDeref):
            mangle_expr(expr.operand, locals_, alias)
        elif isinstance(expr, ExprAddrOf):
            mangle_expr(expr.operand, locals_, alias)
        elif isinstance(expr, ExprCast):
            mangle_type(expr.type_expr)
            mangle_expr(expr.operand, locals_, alias)
        elif isinstance(expr, ExprSizeof):
            mangle_type(expr.type_expr)
        elif isinstance(expr, ExprParen):
            mangle_expr(expr.expr, locals_, alias)
        elif isinstance(expr, ExprTypeLiteral):
            mangle_type(expr.type_expr)
        elif isinstance(expr, ExprInitializer):
            for f in expr.fields:
                if isinstance(f, tuple) and len(f) == 2:
                    mangle_expr(f[1], locals_, alias)
                else:
                    mangle_expr(f, locals_, alias)
        elif isinstance(expr, ExprConditional):
            mangle_expr(expr.condition, locals_, alias)
            mangle_expr(expr.then_expr, locals_, alias)
            if expr.else_expr:
                mangle_expr(expr.else_expr, locals_, alias)

    def mangle_stmt(stmt, locals_, alias=''):
        if stmt is None:
            return
        if isinstance(stmt, StmtBlock):
            for s in stmt.stmts:
                mangle_stmt(s, locals_, alias)
        elif isinstance(stmt, StmtVar):
            locals_.add(stmt.name)
            mangle_type(stmt.type_expr)
            mangle_expr(stmt.value, locals_, alias)
        elif isinstance(stmt, StmtAssign):
            mangle_expr(stmt.target, locals_, alias)
            mangle_expr(stmt.value, locals_, alias)
        elif isinstance(stmt, StmtReturn):
            mangle_expr(stmt.value, locals_, alias)
        elif isinstance(stmt, StmtIf):
            mangle_expr(stmt.condition, locals_, alias)
            mangle_stmt(stmt.then_block, locals_, alias)
            mangle_stmt(stmt.else_block, locals_, alias)
        elif isinstance(stmt, StmtFor):
            mangle_expr(stmt.init, locals_, alias)
            mangle_expr(stmt.condition, locals_, alias)
            mangle_expr(stmt.increment, locals_, alias)
            mangle_stmt(stmt.body, locals_, alias)
        elif isinstance(stmt, StmtForIn):
            locals_.add(stmt.name)
            mangle_expr(stmt.iterable, locals_, alias)
            mangle_stmt(stmt.body, locals_, alias)
        elif isinstance(stmt, StmtWhile):
            mangle_expr(stmt.condition, locals_, alias)
            mangle_stmt(stmt.body, locals_, alias)
        elif isinstance(stmt, StmtLoop):
            mangle_stmt(stmt.body, locals_, alias)
        elif isinstance(stmt, StmtExpr):
            mangle_expr(stmt.expr, locals_, alias)
        elif isinstance(stmt, StmtAssert):
            mangle_expr(stmt.condition, locals_, alias)
        elif isinstance(stmt, StmtDefer):
            mangle_stmt(stmt.body, locals_, alias)
        elif isinstance(stmt, StmtSwitch):
            mangle_expr(stmt.cond, locals_, alias)
            for c in stmt.cases:
                mangle_expr(c.value, locals_, alias)
                for s in c.body:
                    mangle_stmt(s, locals_, alias)
            if stmt.default_body:
                for s in stmt.default_body:
                    mangle_stmt(s, locals_, alias)

    def _mangle_func_body(decl):
        locals_ = set(p.name for p in decl.params if p.name)
        for s in decl.body.stmts:
            mangle_stmt(s, locals_, decl.alias)

    def mangle_decl(decl):
        if isinstance(decl, DeclStruct):
            for f in decl.fields:
                mangle_type(f.type_expr)
            for m in decl.methods:
                if m.struct_name:
                    m.struct_name = name_map.get(m.struct_name, m.struct_name)
                mangle_type(m.return_type)
                for p in m.params:
                    mangle_type(p.type_expr)
                if m.body:
                    _mangle_func_body(m)
        elif isinstance(decl, DeclMethodBlock):
            for m in decl.methods:
                if m.struct_name:
                    m.struct_name = name_map.get(m.struct_name, m.struct_name)
                if m.trait_name:
                    m.trait_name = name_map.get(m.trait_name, m.trait_name)
                mangle_type(m.return_type)
                for p in m.params:
                    mangle_type(p.type_expr)
                if m.body:
                    _mangle_func_body(m)
        elif isinstance(decl, DeclFunc):
            mangle_type(decl.return_type)
            for p in decl.params:
                mangle_type(p.type_expr)
            if decl.body:
                _mangle_func_body(decl)
        elif isinstance(decl, DeclConst):
            mangle_type(decl.type_anno)
            mangle_expr(decl.value, set(), decl.alias)
        elif isinstance(decl, DeclVar):
            mangle_type(decl.type_anno)
            mangle_expr(decl.value, set(), decl.alias)
        elif isinstance(decl, DeclTypedef):
            mangle_type(decl.type_expr)
        elif isinstance(decl, DeclDistinct):
            mangle_type(decl.type_expr)
        elif isinstance(decl, DeclEnum):
            for v in decl.variants:
                mangle_expr(v.value, set(), decl.alias)
        elif isinstance(decl, DeclTrait):
            for m in decl.methods:
                mangle_type(m.return_type)
                for p in m.params:
                    mangle_type(p.type_expr)
                if m.body:
                    _mangle_func_body(m)

    for decl in program.decls:
        if isinstance(decl, (DeclStruct, DeclEnum, DeclTrait, DeclTypedef,
                             DeclDistinct, DeclConst, DeclVar, DeclFunc)):
            if isinstance(decl, DeclFunc) and decl.extern:
                continue  # extern decls keep their original C names
            if decl.alias and decl.name.startswith(decl.alias + '_'):
                continue  # already fully mangled (monomorphised name)
            if decl.alias:
                # Prefer the module-qualified entry: the bare-name entry is
                # last-write-wins across modules and may belong to another one.
                decl.name = name_map.get(f'{decl.alias}.{decl.name}', decl.name)
            else:
                decl.name = name_map[decl.name]

    for decl in program.decls:
        mangle_decl(decl)
