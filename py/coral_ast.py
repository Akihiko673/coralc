# Coral AST Node Definitions

NODE_TYPES = set()

def node_type(cls):
    NODE_TYPES.add(cls.__name__)
    return cls


TOKEN_DISPLAY = {
    'RPAREN': ')', 'LPAREN': '(', 'RBRACE': '}', 'LBRACE': '{',
    'RBRACKET': ']', 'LBRACKET': '[', 'SEMICOLON': ';', 'COMMA': ',',
    'COLON': ':', 'DOT': '.', 'ARROW': '->', 'COLON_COLON': '::',
    'ASSIGN': '=', 'EQ': '==', 'NE': '!=', 'LT': '<', 'GT': '>',
    'LTEQ': '<=', 'GTEQ': '>=', 'PLUS': '+', 'MINUS': '-', 'STAR': '*',
    'SLASH': '/', 'PERCENT': '%', 'AND': '&&', 'OR': '||', 'BANG': '!',
    'BITAND': '&', 'BITOR': '|', 'CARET': '^', 'TILDE': '~',
    'INC': '++', 'DEC': '--', 'PLUS_EQ': '+=', 'MINUS_EQ': '-=',
    'STAR_EQ': '*=', 'SLASH_EQ': '/=', 'PERCENT_EQ': '%=',
    'AMPERSAND_EQ': '&=', 'PIPE_EQ': '|=', 'CARET_EQ': '^=',
    'LTLT_EQ': '<<=', 'GTGT_EQ': '>>=', 'LTLT': '<<', 'GTGT': '>>',
    'BANG_LT': '!<', 'ELLIPSIS': '...', 'QUEST': '?', 'SHIFT': '<<',
}


def token_display(kind):
    return TOKEN_DISPLAY.get(kind, kind)


def make_snippet(lines, line, col):
    """Build a '  N | source line' snippet with a caret under `col`."""
    if not lines or line < 1 or line > len(lines):
        return None
    text = lines[line - 1].rstrip('\n')
    caret = ' ' * max(col - 1, 0) + '^'
    width = len(str(line))
    return (f'    {line} | {text}\n'
            f'    {" " * width} | {caret}')


class ParseError(Exception):
    """A parse error with file/line/col, a message, the enclosing
    context (e.g. 'function push'), and a source snippet with a caret."""

    def __init__(self, filename, line, col, message,
                 context=None, snippet=None):
        super().__init__()
        self.filename = filename
        self.line = line
        self.col = col
        self.message = message
        self.context = context
        self.snippet = snippet

    def __str__(self):
        loc = f'{self.filename}:{self.line}:{self.col}'
        ctx = f' [in {self.context}]' if self.context else ''
        s = f'{loc}:{ctx} error: {self.message}'
        if self.snippet:
            s += f'\n{self.snippet}'
        return s

@node_type
class Program:
    __slots__ = ('decls', 'module_name', 'filename')
    def __init__(self, decls=None, module_name=None, filename=None):
        self.decls = decls or []
        self.module_name = module_name
        self.filename = filename

    def __repr__(self):
        return f'Program(module={self.module_name}, decls={len(self.decls)})'


@node_type
class Decorator:
    __slots__ = ('name', 'condition')
    def __init__(self, name, condition=None):
        self.name = name
        self.condition = condition

    def __repr__(self):
        if self.condition:
            return f'@if({self.condition})'
        return f'@{self.name}'


# Types

@node_type
class TypeIdent:
    __slots__ = ('name', 'line', 'col')
    def __init__(self, name, line=0, col=0):
        self.name = name
        self.line = line
        self.col = col
    def __repr__(self): return f'Type({self.name})'

@node_type
class TypePointer:
    __slots__ = ('base', 'const', 'line', 'col')
    def __init__(self, base, const=False, line=0, col=0):
        self.base = base
        self.const = const
        self.line = line
        self.col = col
    def __repr__(self): return f'Ptr({"const " if self.const else ""}{self.base})'

@node_type
class TypeArray:
    __slots__ = ('base', 'size', 'line', 'col')
    def __init__(self, base, size=None, line=0, col=0):
        self.base = base
        self.size = size
        self.line = line
        self.col = col
    def __repr__(self): return f'Array({self.base}, {self.size})'

@node_type
class TypeGeneric:
    __slots__ = ('name', 'args', 'line', 'col')
    def __init__(self, name, args=None, line=0, col=0):
        self.name = name
        self.args = args or []
        self.line = line
        self.col = col
    def __repr__(self): return f'Generic({self.name}<{self.args}>)'

@node_type
class TypeFunc:
    __slots__ = ('param_types', 'return_type', 'line', 'col')
    def __init__(self, param_types=None, return_type=None, line=0, col=0):
        self.param_types = param_types or []
        self.return_type = return_type
        self.line = line
        self.col = col
    def __repr__(self): return f'FuncType({self.param_types} -> {self.return_type})'


# Declarations

@node_type
class DeclModule:
    __slots__ = ('path', 'line', 'col', 'alias')
    def __init__(self, path, line=0, col=0):
        self.path = path
        self.line = line
        self.col = col
        self.alias = ''
    def __repr__(self): return f'Module({self.path})'

@node_type
class DeclImport:
    __slots__ = ('path', 'names', 'line', 'col', 'alias')
    def __init__(self, path, names=None, line=0, col=0):
        self.path = path
        self.names = names or []
        self.line = line
        self.col = col
        self.alias = ''
    def __repr__(self): return f'Import({self.path}{"::{" + ", ".join(self.names) + "}" if self.names else ""})'

@node_type
class DeclConst:
    __slots__ = ('name', 'type_anno', 'value', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, type_anno=None, value=None, exported=False, line=0, col=0):
        self.name = name
        self.type_anno = type_anno
        self.value = value
        self.exported = exported
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Const({self.name})'

@node_type
class DeclVar:
    __slots__ = ('name', 'type_anno', 'value', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, type_anno=None, value=None, exported=False, line=0, col=0):
        self.name = name
        self.type_anno = type_anno
        self.value = value
        self.exported = exported
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Var({self.name})'

@node_type
class DeclStruct:
    __slots__ = ('name', 'generic_params', 'fields', 'methods', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, generic_params=None, fields=None, methods=None, exported=False, line=0, col=0, alias=''):
        self.name = name
        self.generic_params = generic_params or []
        self.fields = fields or []
        self.methods = methods or []
        self.exported = exported
        self.alias = alias
        self.line = line
        self.col = col
    def __repr__(self): return f'Struct({self.name})'

@node_type
class StructField:
    __slots__ = ('name', 'type_expr', 'line', 'col')
    def __init__(self, name, type_expr, line=0, col=0):
        self.name = name
        self.type_expr = type_expr
        self.line = line
        self.col = col
    def __repr__(self): return f'Field({self.name}: {self.type_expr})'

@node_type
class DeclEnum:
    __slots__ = ('name', 'variants', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, variants=None, exported=False, line=0, col=0):
        self.name = name
        self.variants = variants or []
        self.exported = exported
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Enum({self.name})'

@node_type
class EnumVariant:
    __slots__ = ('name', 'value', 'line', 'col')
    def __init__(self, name, value=None, line=0, col=0):
        self.name = name
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self): return f'Variant({self.name})'

@node_type
class DeclTrait:
    __slots__ = ('name', 'methods', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, methods=None, exported=False, line=0, col=0):
        self.name = name
        self.methods = methods or []
        self.exported = exported
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Trait({self.name})'

@node_type
class DeclExtern:
    __slots__ = ('name', 'return_type', 'params', 'variadic', 'calling_conv',
                 'noreturn', 'exported', 'line', 'col', 'alias', 'is_var')
    def __init__(self, name, return_type, params=None, variadic=False,
                 calling_conv=None, noreturn=False, exported=False, line=0, col=0,
                 is_var=False):
        self.name = name
        self.return_type = return_type
        self.params = params or []
        self.variadic = variadic
        self.calling_conv = calling_conv
        self.noreturn = noreturn
        self.exported = exported
        self.is_var = is_var
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Extern({self.name})'

@node_type
class DeclTypedef:
    __slots__ = ('name', 'type_expr', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, type_expr, exported=False, line=0, col=0):
        self.name = name
        self.type_expr = type_expr
        self.exported = exported
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Typedef({self.name} = {self.type_expr})'

@node_type
class DeclDistinct:
    __slots__ = ('name', 'type_expr', 'exported', 'line', 'col', 'alias')
    def __init__(self, name, type_expr, exported=False, line=0, col=0):
        self.name = name
        self.type_expr = type_expr
        self.exported = exported
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self): return f'Distinct({self.name})'

@node_type
class DeclFunc:
    __slots__ = ('name', 'return_type', 'params', 'generic_params', 'body',
                 'exported', 'static', 'is_method', 'struct_name', 'trait_name',
                 'extern', 'calling_conv', 'noreturn', 'line', 'col', 'alias',
                 'inline')
    def __init__(self, name, return_type=None, params=None, generic_params=None,
                 body=None, exported=False, static=False, is_method=False,
                 struct_name=None, trait_name=None, extern=False,
                 calling_conv=None, noreturn=False, line=0, col=0, alias='',
                 inline=False):
        self.name = name
        self.return_type = return_type
        self.params = params or []
        self.generic_params = generic_params or []
        self.body = body or []
        self.exported = exported
        self.static = static
        self.is_method = is_method
        self.struct_name = struct_name
        self.trait_name = trait_name
        self.extern = extern
        self.calling_conv = calling_conv
        self.noreturn = noreturn
        self.line = line
        self.col = col
        self.alias = alias
        self.inline = inline
    def __repr__(self): return f'Func({self.name})'

@node_type
class Param:
    __slots__ = ('name', 'type_expr', 'line', 'col')
    def __init__(self, name, type_expr, line=0, col=0):
        self.name = name
        self.type_expr = type_expr
        self.line = line
        self.col = col
    def __repr__(self): return f'Param({self.name}: {self.type_expr})'

@node_type
class DeclMethodBlock:
    __slots__ = ('struct_name', 'trait_name', 'methods', 'line', 'col', 'alias')
    def __init__(self, struct_name, trait_name=None, methods=None, line=0, col=0):
        self.struct_name = struct_name
        self.trait_name = trait_name
        self.methods = methods or []
        self.alias = ''
        self.line = line
        self.col = col
    def __repr__(self):
        if self.trait_name:
            return f'Impl({self.struct_name}::{self.trait_name})'
        return f'MethodBlock({self.struct_name})'

@node_type
class DeclNamespace:
    __slots__ = ('name', 'decls', 'line', 'col')
    def __init__(self, name, decls=None, line=0, col=0):
        self.name = name
        self.decls = decls or []
        self.line = line
        self.col = col
    def __repr__(self):
        return f'Namespace({self.name})'

@node_type
class DeclConditional:
    __slots__ = ('condition', 'decls', 'else_decls', 'line', 'col')
    def __init__(self, condition, decls=None, else_decls=None, line=0, col=0):
        self.condition = condition
        self.decls = decls or []
        self.else_decls = else_decls
        self.line = line
        self.col = col
    def __repr__(self): return f'Conditional(@if {self.condition})'

@node_type
class DeclFlag:
    __slots__ = ('name', 'cases', 'default_case', 'line', 'col')
    def __init__(self, name, cases=None, default_case=None, line=0, col=0):
        self.name = name
        self.cases = cases or []       # list of (case_name, decls)
        self.default_case = default_case  # list of decls
        self.line = line
        self.col = col
    def __repr__(self): return f'Flag({self.name})'


# Statements

@node_type
class StmtBlock:
    __slots__ = ('stmts', 'line', 'col')
    def __init__(self, stmts=None, line=0, col=0):
        self.stmts = stmts or []
        self.line = line
        self.col = col
    def __repr__(self): return f'Block({len(self.stmts)} stmts)'

@node_type
class StmtVar:
    __slots__ = ('name', 'type_expr', 'value', 'line', 'col')
    def __init__(self, name, type_expr=None, value=None, line=0, col=0):
        self.name = name
        self.type_expr = type_expr
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self): return f'StmtVar({self.name})'

@node_type
class StmtAssign:
    __slots__ = ('target', 'value', 'op', 'line', 'col')
    def __init__(self, target, value, op='=', line=0, col=0):
        self.target = target
        self.value = value
        self.op = op
        self.line = line
        self.col = col
    def __repr__(self): return f'Assign({self.target} {self.op} {self.value})'

@node_type
class StmtReturn:
    __slots__ = ('value', 'is_noreturn', 'line', 'col')
    def __init__(self, value=None, is_noreturn=False, line=0, col=0):
        self.value = value
        self.is_noreturn = is_noreturn
        self.line = line
        self.col = col
    def __repr__(self): return f'Return({self.value})'

@node_type
class StmtIf:
    __slots__ = ('condition', 'then_block', 'else_block', 'line', 'col')
    def __init__(self, condition, then_block, else_block=None, line=0, col=0):
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block
        self.line = line
        self.col = col
    def __repr__(self): return f'If({self.condition})'

@node_type
class StmtFor:
    __slots__ = ('init', 'condition', 'increment', 'body', 'line', 'col')
    def __init__(self, init=None, condition=None, increment=None, body=None, line=0, col=0):
        self.init = init
        self.condition = condition
        self.increment = increment
        self.body = body
        self.line = line
        self.col = col
    def __repr__(self): return f'For({self.init}; {self.condition}; {self.increment})'


@node_type
class StmtForIn:
    __slots__ = ('name', 'iterable', 'body', 'line', 'col')
    def __init__(self, name, iterable, body=None, line=0, col=0):
        self.name = name
        self.iterable = iterable
        self.body = body
        self.line = line
        self.col = col
    def __repr__(self): return f'ForIn({self.name} in {self.iterable})'

@node_type
class StmtWhile:
    __slots__ = ('condition', 'body', 'line', 'col')
    def __init__(self, condition, body, line=0, col=0):
        self.condition = condition
        self.body = body
        self.line = line
        self.col = col
    def __repr__(self): return f'While({self.condition})'

@node_type
class StmtLoop:
    __slots__ = ('body', 'line', 'col')
    def __init__(self, body, line=0, col=0):
        self.body = body
        self.line = line
        self.col = col
    def __repr__(self): return f'Loop()'

@node_type
class StmtExpr:
    __slots__ = ('expr', 'line', 'col')
    def __init__(self, expr, line=0, col=0):
        self.expr = expr
        self.line = line
        self.col = col
    def __repr__(self): return f'StmtExpr({self.expr})'

@node_type
class StmtAssert:
    __slots__ = ('condition', 'line', 'col')
    def __init__(self, condition, line=0, col=0):
        self.condition = condition
        self.line = line
        self.col = col
    def __repr__(self): return f'Assert({self.condition})'


@node_type
class StmtSwitch:
    __slots__ = ('cond', 'cases', 'default_body', 'line', 'col')
    def __init__(self, cond, cases=None, default_body=None, line=0, col=0):
        self.cond = cond
        self.cases = cases or []
        self.default_body = default_body
        self.line = line
        self.col = col
    def __repr__(self): return f'Switch({self.cond}, {len(self.cases)} cases)'

@node_type
class StmtCase:
    __slots__ = ('value', 'body', 'line', 'col')
    def __init__(self, value, body=None, line=0, col=0):
        self.value = value
        self.body = body or []
        self.line = line
        self.col = col
    def __repr__(self): return f'Case({self.value})'

@node_type
class StmtBreak:
    __slots__ = ('line', 'col')
    def __init__(self, line=0, col=0):
        self.line = line
        self.col = col
    def __repr__(self): return 'Break'

@node_type
class StmtContinue:
    __slots__ = ('line', 'col')
    def __init__(self, line=0, col=0):
        self.line = line
        self.col = col
    def __repr__(self): return 'Continue'

@node_type
class StmtAsm:
    __slots__ = ('body', 'line', 'col')
    def __init__(self, body, line=0, col=0):
        self.body = body
        self.line = line
        self.col = col
    def __repr__(self): return f'Asm({self.body})'

@node_type
class StmtDefer:
    __slots__ = ('body', 'line', 'col')
    def __init__(self, body, line=0, col=0):
        self.body = body
        self.line = line
        self.col = col
    def __repr__(self): return f'Defer({self.body})'

@node_type
class StmtFlag:
    __slots__ = ('name', 'cases', 'default_body', 'line', 'col')
    def __init__(self, name, cases=None, default_body=None, line=0, col=0):
        self.name = name
        self.cases = cases or []     # list of (case_name, stmts)
        self.default_body = default_body  # list of stmts
        self.line = line
        self.col = col
    def __repr__(self): return f'FlagStmt({self.name})'


# Expressions

@node_type
class ExprInt:
    __slots__ = ('value', 'line', 'col', 'suffix')
    def __init__(self, value, line=0, col=0, suffix=''):
        self.value = value
        self.line = line
        self.col = col
        self.suffix = suffix
    def __repr__(self): return f'{self.value}{self.suffix}'

@node_type
class ExprFloat:
    __slots__ = ('value', 'line', 'col')
    def __init__(self, value, line=0, col=0):
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.value}'

@node_type
class ExprString:
    __slots__ = ('value', 'line', 'col')
    def __init__(self, value, line=0, col=0):
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.value!r}'

@node_type
class ExprChar:
    __slots__ = ('value', 'line', 'col')
    def __init__(self, value, line=0, col=0):
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self): return f"'{chr(self.value) if 32 <= self.value < 127 else hex(self.value)}'"

@node_type
class ExprBool:
    __slots__ = ('value', 'line', 'col')
    def __init__(self, value, line=0, col=0):
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self): return f'{"true" if self.value else "false"}'

@node_type
class ExprIdent:
    __slots__ = ('name', 'line', 'col')
    def __init__(self, name, line=0, col=0):
        self.name = name
        self.line = line
        self.col = col
    def __repr__(self): return self.name

@node_type
class ExprUnary:
    __slots__ = ('op', 'operand', 'is_postfix', 'line', 'col')
    def __init__(self, op, operand, is_postfix=False, line=0, col=0):
        self.op = op
        self.operand = operand
        self.is_postfix = is_postfix
        self.line = line
        self.col = col
    def __repr__(self): return f'({self.op}{self.operand})'

@node_type
class ExprBinary:
    __slots__ = ('op', 'left', 'right', 'line', 'col')
    def __init__(self, op, left, right, line=0, col=0):
        self.op = op
        self.left = left
        self.right = right
        self.line = line
        self.col = col
    def __repr__(self): return f'({self.left} {self.op} {self.right})'

@node_type
class ExprTernary:
    __slots__ = ('condition', 'then_expr', 'else_expr', 'line', 'col')
    def __init__(self, condition, then_expr, else_expr, line=0, col=0):
        self.condition = condition
        self.then_expr = then_expr
        self.else_expr = else_expr
        self.line = line
        self.col = col
    def __repr__(self): return f'({self.condition} ? {self.then_expr} : {self.else_expr})'

@node_type
class ExprCall:
    __slots__ = ('callee', 'args', 'line', 'col')
    def __init__(self, callee, args=None, line=0, col=0):
        self.callee = callee
        self.args = args or []
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.callee}({self.args})'

@node_type
class ExprDot:
    __slots__ = ('object', 'member', 'line', 'col')
    def __init__(self, object, member, line=0, col=0):
        self.object = object
        self.member = member
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.object}.{self.member}'

@node_type
class ExprArrow:
    __slots__ = ('object', 'member', 'line', 'col')
    def __init__(self, object, member, line=0, col=0):
        self.object = object
        self.member = member
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.object}->{self.member}'

@node_type
class ExprIndex:
    __slots__ = ('object', 'index', 'line', 'col')
    def __init__(self, object, index, line=0, col=0):
        self.object = object
        self.index = index
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.object}[{self.index}]'

@node_type
class ExprDeref:
    __slots__ = ('operand', 'line', 'col')
    def __init__(self, operand, line=0, col=0):
        self.operand = operand
        self.line = line
        self.col = col
    def __repr__(self): return f'*{self.operand}'

@node_type
class ExprAddrOf:
    __slots__ = ('operand', 'line', 'col')
    def __init__(self, operand, line=0, col=0):
        self.operand = operand
        self.line = line
        self.col = col
    def __repr__(self): return f'&{self.operand}'

@node_type
class ExprCast:
    __slots__ = ('type_expr', 'operand', 'line', 'col')
    def __init__(self, type_expr, operand, line=0, col=0):
        self.type_expr = type_expr
        self.operand = operand
        self.line = line
        self.col = col
    def __repr__(self): return f'({self.type_expr}){self.operand}'

@node_type
class ExprSizeof:
    __slots__ = ('type_expr', 'line', 'col')
    def __init__(self, type_expr, line=0, col=0):
        self.type_expr = type_expr
        self.line = line
        self.col = col
    def __repr__(self): return f'sizeof({self.type_expr})'

@node_type
class ExprNull:
    __slots__ = ('line', 'col')
    def __init__(self, line=0, col=0):
        self.line = line
        self.col = col
    def __repr__(self): return 'null'

@node_type
class ExprModulePath:
    __slots__ = ('parts', 'line', 'col')
    def __init__(self, parts, line=0, col=0):
        self.parts = parts
        self.line = line
        self.col = col
    def __repr__(self): return '::'.join(self.parts)

@node_type
class ExprGenericInst:
    __slots__ = ('base', 'type_args', 'line', 'col')
    def __init__(self, base, type_args=None, line=0, col=0):
        self.base = base
        self.type_args = type_args or []
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.base}!<{self.type_args}>'

@node_type
class ExprInitializer:
    __slots__ = ('type_expr', 'fields', 'line', 'col')
    def __init__(self, type_expr, fields=None, line=0, col=0):
        self.type_expr = type_expr
        self.fields = fields or []
        self.line = line
        self.col = col
    def __repr__(self): return f'{self.type_expr} {{ ... }}'

@node_type
class ExprParen:
    __slots__ = ('expr', 'line', 'col')
    def __init__(self, expr, line=0, col=0):
        self.expr = expr
        self.line = line
        self.col = col
    def __repr__(self): return f'({self.expr})'


@node_type
class ExprTypeLiteral:
    __slots__ = ('type_expr', 'line', 'col')
    def __init__(self, type_expr, line=0, col=0):
        self.type_expr = type_expr
        self.line = line
        self.col = col
    def __repr__(self): return f'({self.type_expr})'


@node_type
class ExprConditional:
    __slots__ = ('condition', 'then_expr', 'else_expr', 'line', 'col')
    def __init__(self, condition, then_expr, else_expr=None, line=0, col=0):
        self.condition = condition
        self.then_expr = then_expr
        self.else_expr = else_expr
        self.line = line
        self.col = col
    def __repr__(self): return f'if {self.condition} then {self.then_expr} else {self.else_expr}'
