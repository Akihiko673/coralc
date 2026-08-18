from tokenizer import Token, Tokenizer, KEYWORDS, TYPE_KEYWORDS
from coral_ast import *

# Operator precedence (higher = binds tighter)
ASSIGN_OPS_LIST = [
    ('=', 'ASSIGN'), ('+=', 'PLUS_EQ'), ('-=', 'MINUS_EQ'),
    ('*=', 'STAR_EQ'), ('/=', 'SLASH_EQ'), ('%=', 'PERCENT_EQ'),
    ('&=', 'AMPERSAND_EQ'), ('|=', 'PIPE_EQ'), ('^=', 'CARET_EQ'),
    ('<<=', 'LTLT_EQ'), ('>>=', 'GTGT_EQ'),
]

PREC = {
    'ASSIGN': 0,
    'TERNARY': 1,
    'OR': 2,
    'AND': 3,
    'BITOR': 4,
    'BITXOR': 5,
    'BITAND': 6,
    'EQ': 7,
    'CMP': 8,
    'SHIFT': 9,
    'ADD': 10,
    'MUL': 11,
    'UNARY': 12,
    'POSTFIX': 13,
    'PRIMARY': 14,
}

BINARY_OPS = {
    'OR': ('||', PREC['OR']),
    'AND': ('&&', PREC['AND']),
    'PIPE': ('|', PREC['BITOR']),
    'CARET': ('^', PREC['BITXOR']),
    'AMPERSAND': ('&', PREC['BITAND']),
    'EQ': ('==', PREC['EQ']),
    'NE': ('!=', PREC['EQ']),
    'LT': ('<', PREC['CMP']),
    'LE': ('<=', PREC['CMP']),
    'GT': ('>', PREC['CMP']),
    'GE': ('>=', PREC['CMP']),
    'LTLT': ('<<', PREC['SHIFT']),
    'GTGT': ('>>', PREC['SHIFT']),
    'PLUS': ('+', PREC['ADD']),
    'MINUS': ('-', PREC['ADD']),
    'STAR': ('*', PREC['MUL']),
    'SLASH': ('/', PREC['MUL']),
    'PERCENT': ('%', PREC['MUL']),
}
ASSIGN_OPS_BIN = {
    'ASSIGN': ('=', PREC['ASSIGN']),
    'PLUS_EQ': ('+=', PREC['ASSIGN']),
    'MINUS_EQ': ('-=', PREC['ASSIGN']),
    'STAR_EQ': ('*=', PREC['ASSIGN']),
    'SLASH_EQ': ('/=', PREC['ASSIGN']),
    'PERCENT_EQ': ('%=', PREC['ASSIGN']),
    'AMPERSAND_EQ': ('&=', PREC['ASSIGN']),
    'PIPE_EQ': ('|=', PREC['ASSIGN']),
    'CARET_EQ': ('^=', PREC['ASSIGN']),
    'LTLT_EQ': ('<<=', PREC['ASSIGN']),
    'GTGT_EQ': ('>>=', PREC['ASSIGN']),
}

PREFIX_OPS = {
    'PLUS': '+',
    'MINUS': '-',
    'BANG': '!',
    'TILDE': '~',
    'STAR': '*',
    'AMPERSAND': '&',
    'INC': '++',
    'DEC': '--',
}

ASSIGN_OPS = {
    'ASSIGN': '=',
    'PLUS_EQ': '+=',
    'MINUS_EQ': '-=',
    'STAR_EQ': '*=',
    'SLASH_EQ': '/=',
    'PERCENT_EQ': '%=',
    'AMPERSAND_EQ': '&=',
    'PIPE_EQ': '|=',
    'CARET_EQ': '^=',
    'LTLT_EQ': '<<=',
    'GTGT_EQ': '>>=',
}

class Parser:
    def __init__(self, tokens, filename='<unknown>', defines=None, source=None):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        self._lines = source.split('\n') if source is not None else None
        self._context_stack = []
        self._gtgt_consumed = False

    def _ctx(self, label):
        """Context manager: label the enclosing language construct being
        parsed so errors say 'in function push', 'in struct Vec', etc."""
        stack = self._context_stack

        class _CtxMgr:
            __slots__ = ()

            def __enter__(self):
                stack.append(label)
                return self

            def __exit__(self, *exc):
                stack.pop()
                return False

        return _CtxMgr()

    def _context_str(self):
        if not self._context_stack:
            return None
        return ' → '.join(self._context_stack[-3:])

    def _snippet(self, tok):
        return make_snippet(self._lines, tok.line, tok.col) \
            if self._lines is not None else None

    def _error(self, msg, tok=None):
        if tok is None:
            tok = self._peek()
        raise ParseError(self.filename, tok.line, tok.col, msg,
                         context=self._context_str(),
                         snippet=self._snippet(tok))

    def _peek(self, offset=0):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else Token('EOF', line=0, col=0)

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind, msg=None):
        tok = self._peek()
        if kind == 'IDENT' and tok.kind == 'TYPE':
            return self._advance()
        if tok.kind != kind:
            if msg:
                self._error(msg)
            if kind == 'IDENT':
                want = 'an identifier'
            elif kind == 'TYPE':
                want = 'a type'
            else:
                want = f"'{token_display(kind)}'"
            got = f"'{token_display(tok.kind)}'"
            if tok.kind in ('IDENT', 'TYPE', 'INT', 'FLOAT', 'STRING', 'CHAR'):
                got += f" '{tok.value}'"
            hint = self._expect_hint(kind, tok)
            self._error(f'expected {want}, found {got}{hint}')
        return self._advance()

    def _expect_hint(self, kind, tok):
        """Explanatory hint appended to `expected X, found Y` errors."""
        if kind == 'IDENT' and tok.kind in (
                'MOD', 'IMPORT', 'PUB', 'EXTERN', 'STRUCT', 'ENUM', 'TRAIT',
                'CONST', 'VAR', 'TYPEDEF', 'DISTINCT', 'RETURN', 'IF', 'ELSE',
                'FOR', 'WHILE', 'LOOP', 'SWITCH', 'CASE', 'DEFAULT', 'BREAK',
                'CONTINUE', 'DEFER', 'FLAG', 'COMPTIME', 'ASM', 'INLINE',
                'TRUE', 'FALSE', 'NULL', 'NIL', 'SELF', 'STATIC', 'ASSERT',
                'SIZEOF', 'COMPILER_FN', 'UNSAFE'):
            return (f" — '{tok.value or token_display(tok.kind).lower()}' is a keyword "
                    f"and cannot be used as a name; rename it (e.g. append an "
                    f"underscore: '{tok.value or token_display(tok.kind).lower()}_')")
        hints = {
            'SEMICOLON': " — a statement or declaration is missing its trailing ';' "
                         "(did you forget to end the previous line with ';'?)",
            'RPAREN': " — a call or function header is missing its closing ')' "
                      "(an argument or parameter list was left open)",
            'RBRACE': " — a block, struct, enum, trait, or flag case is missing "
                      "its closing '}' (check that every '{' is balanced)",
            'GT': " — a generic argument list is missing its closing '>'; nested "
                  "generics like Foo<Bar<Baz>> need one '>' per level",
            'LPAREN': " — expected '(' here (e.g. a function or macro name is "
                      "followed by its argument list)",
            'LBRACE': " — expected '{' here (a body or block must start with '{')",
            'LBRACKET': " — an array type or index expression is missing its "
                        "closing ']'",
            'RBRACKET': " — a '[' was opened here and never closed",
            'COLON': " — a flag case selector or type annotation needs ':' after "
                     "the name",
            'COMMA': " — expected ',' to separate items in a list (did you forget "
                     "a comma?)",
            'ASSIGN': " — a var/const declaration needs '=' followed by a value",
        }
        return hints.get(kind, '')

    def _check(self, kind):
        return self._peek().kind == kind

    def _check_any(self, *kinds):
        return any(self._peek().kind == k for k in kinds)

    def _expect_ident_or_type(self):
        tok = self._peek()
        if tok.kind in ('IDENT', 'TYPE'):
            return self._advance()
        got = f"'{token_display(tok.kind)}'"
        if tok.kind in ('IDENT', 'TYPE', 'INT', 'FLOAT', 'STRING', 'CHAR'):
            got += f" ({tok.value})"
        self._error(
            f'expected a name (identifier or type), found {got}'
            + self._expect_hint('IDENT', tok))

    def _skip_semicolons(self):
        while self._check('SEMICOLON'):
            self._advance()

    def parse(self):
        decls = self._parse_decls()
        self._expect('EOF')
        return Program(decls, filename=self.filename)

    # Declarations

    def _parse_decls(self):
        decls = []
        while not self._check('EOF') and not self._check('RBRACE'):
            decl = self._parse_decl()
            if decl is not None:
                if isinstance(decl, tuple):
                    decls.extend(decl)
                else:
                    decls.append(decl)
            self._skip_semicolons()
        return decls

    def _parse_decl(self):
        self._skip_semicolons()

        if self._check('EOF'):
            return None

        if self._check('AT_UNSAFE'):
            self._advance()
            return None  # handled as module-level attribute

        if self._check('AT'):
            self._advance()
            if self._check('LBRACKET'):
                # @[ident, ...] attribute — skip
                self._advance()
                while not self._check('RBRACKET') and not self._check('EOF'):
                    self._advance()
                self._expect('RBRACKET')
                self._skip_semicolons()
                return None
            name = self._expect('IDENT').value
            return None  # generic attribute, skip for now

        if self._check('PUB'):
            self._advance()
            return self._parse_decl_exported(True)

        return self._parse_decl_exported(False)

    def _parse_decl_exported(self, exported):
        if self._check('MOD'):
            return self._parse_module_decl()
        if self._check('EXTERN'):
            return self._parse_extern_decl(exported)
        if self._check('STATIC'):
            self._advance()
            # static function at module level — parse as type-first decl
            return self._parse_type_first_decl(exported, static=True)
        if self._check('INLINE'):
            self._advance()
            return self._parse_type_first_decl(exported, inline=True)
        if self._check('CONST'):
            return self._parse_const_decl(exported)
        if self._check('VAR'):
            return self._parse_var_decl(exported)
        if self._check('STRUCT'):
            return self._parse_struct_decl(exported)
        if self._check('ENUM'):
            return self._parse_enum_decl(exported)
        if self._check('TRAIT'):
            return self._parse_trait_decl(exported)
        if self._check('TYPEDEF'):
            return self._parse_typedef_decl(exported)
        if self._check('DISTINCT'):
            return self._parse_distinct_decl(exported)
        if self._check('COMPILER_FN'):
            return self._parse_compiler_fn_decl(exported)
        if self._check('FLAG'):
            return self._parse_flag_decl(exported)

        # Type-first function/const declaration
        if self._check('TYPE') or self._check('IDENT'):
            # Could be: return_type name(...) { ... }
            # Or: Name { ... }  (method block)
            # Or: Name :: Name { ... } (trait impl)
            # Or: Name :: name(...) { ... } (module-scoped function)
            return self._parse_type_first_decl(exported)

        if self._check('RBRACE'):
            return None

        self._error(f'Unexpected token: {self._peek().kind} ({self._peek().value})')

    def _parse_module_decl(self):
        tok = self._advance()
        alias = self._expect('IDENT').value
        self._expect('ASSIGN')
        if self._check('IMPORT'):
            self._advance()
        self._expect('LPAREN')
        path = self._expect('STRING').value
        self._expect('RPAREN')
        self._expect('SEMICOLON')
        return DeclModule(alias, line=tok.line, col=tok.col), DeclImport(path, [alias], line=tok.line, col=tok.col)

    def _parse_extern_decl(self, exported):
        self._advance()
        calling_conv = None
        if self._check('LPAREN'):
            self._advance()
            calling_conv = self._expect('STRING').value
            self._expect('RPAREN')
        return_type = self._parse_type()
        name = self._expect('IDENT').value
        if self._check('LPAREN'):
            self._advance()
            params, variadic = self._parse_param_list()
            self._expect('RPAREN')
            noreturn = False
            if self._check('NO_RETURN'):
                self._advance()
                noreturn = True
            self._expect('SEMICOLON')
            tok = self.tokens[self.pos - 1]
            return DeclExtern(name, return_type, params, variadic, calling_conv,
                              noreturn, exported, line=tok.line, col=tok.col)
        else:
            self._expect('SEMICOLON')
            tok = self.tokens[self.pos - 1]
            return DeclExtern(name, return_type, [], False, calling_conv,
                              False, exported, line=tok.line, col=tok.col,
                              is_var=True)

    def _parse_const_decl(self, exported):
        self._advance()
        saved_pos = self.pos
        next_is_ident = self._check('IDENT')
        next1 = self._peek(1)
        if next_is_ident and next1 is not None and next1.kind in ('ASSIGN', 'LBRACKET', 'SEMICOLON'):
            name = self._advance().value
            type_anno = None
            if self._check('LBRACKET'):
                self._advance()
                array_size = None
                if not self._check('RBRACKET'):
                    array_size = self._parse_expr()
                self._expect('RBRACKET')
                type_anno = TypeArray(TypeIdent('void'), array_size, line=self.tokens[self.pos-2].line, col=self.tokens[self.pos-2].col)
        else:
            type_anno = self._parse_type()
            if type_anno is None:
                self._error('Expected type in const declaration')
            name_tok = self._expect_ident_or_type()
            name = name_tok.value
            if self._check('LPAREN'):
                self.pos = saved_pos
                return self._parse_type_first_decl(exported)
            if self._check('LBRACKET'):
                self._advance()
                array_size = None
                if not self._check('RBRACKET'):
                    array_size = self._parse_expr()
                self._expect('RBRACKET')
                type_anno = TypeArray(type_anno, array_size, line=type_anno.line, col=type_anno.col)
        self._expect('ASSIGN')
        value = self._parse_expr()
        self._expect('SEMICOLON')
        tok = self.tokens[self.pos - 1]
        return DeclConst(name, type_anno, value, exported,
                         line=tok.line, col=tok.col)

    def _parse_var_decl(self, exported):
        self._advance()
        name = self._expect('IDENT').value
        type_anno = None
        if self._check('COLON'):
            self._advance()
            type_anno = self._parse_type()
        value = None
        if self._check('ASSIGN'):
            self._advance()
            value = self._parse_expr()
        self._expect('SEMICOLON')
        tok = self.tokens[self.pos - 1]
        return DeclVar(name, type_anno, value, exported,
                       line=tok.line, col=tok.col)

    def _parse_struct_decl(self, exported):
        self._advance()
        name = self._expect_ident_or_type().value
        with self._ctx(f'struct {name}'):
            return self._parse_struct_decl_rest(exported, name)

    def _parse_struct_decl_rest(self, exported, name):
        generic_params = []
        if self._check('LT'):
            self._advance()
            generic_params = self._parse_generic_param_list()
            self._expect('GT')
        self._expect('LBRACE')
        fields = []
        methods = []
        while not self._check('RBRACE') and not self._check('EOF'):
            if self._check('SEMICOLON'):
                self._advance()
                continue
            if self._check('STATIC'):
                self._advance()
                method = self._parse_func_decl(exported, is_method=False,
                                               struct_name=name)
                if method:
                    method.static = True
                    methods.append(method)
                self._skip_semicolons()
                continue
            if self._check('TYPE') or self._check('IDENT') or self._check('CONST'):
                saved = self.pos
                try:
                    field_type = self._parse_type()
                    field_name = self._expect_ident_or_type().value
                    if self._check('LPAREN') or self._check('LT') or self._check('BANG_LT'):
                        self.pos = saved
                        method = self._parse_func_decl(exported, is_method=True,
                                                       struct_name=name)
                        if method:
                            methods.append(method)
                        self._skip_semicolons()
                        continue
                    array_size = None
                    while self._check('LBRACKET'):
                        self._advance()
                        dim = self._parse_expr()
                        self._expect('RBRACKET')
                        if array_size is None:
                            array_size = dim
                        else:
                            array_size = [array_size, dim]
                    if array_size is not None and not isinstance(array_size, list):
                        field_type = TypeArray(field_type, array_size)
                    elif isinstance(array_size, list):
                        inner = field_type
                        for d in reversed(array_size):
                            inner = TypeArray(inner, d)
                        field_type = inner
                    field = StructField(field_name, field_type,
                                       line=field_type.line, col=field_type.col)
                    fields.append(field)
                    self._expect('SEMICOLON')
                except ParseError:
                    self.pos = saved
                    method = self._parse_func_decl(exported, is_method=True,
                                                   struct_name=name)
                    if method:
                        methods.append(method)
                    self._skip_semicolons()
            else:
                method = self._parse_func_decl(exported, is_method=True,
                                               struct_name=name)
                if method:
                    methods.append(method)
                self._skip_semicolons()
        self._expect('RBRACE')
        tok = self.tokens[self.pos - 1]
        return DeclStruct(name, generic_params, fields, methods, exported,
                          line=tok.line, col=tok.col)

    def _parse_enum_decl(self, exported):
        self._advance()
        name = self._expect('IDENT').value
        with self._ctx(f'enum {name}'):
            return self._parse_enum_decl_rest(exported, name)

    def _parse_enum_decl_rest(self, exported, name):
        self._expect('LBRACE')
        variants = []
        while not self._check('RBRACE') and not self._check('EOF'):
            var_name = self._expect('IDENT').value
            if self._check('LPAREN'):
                # variant payload types: Name(T1, T2) — consumed, not used
                self._advance()
                while not self._check('RPAREN') and not self._check('EOF'):
                    self._parse_type()
                    if self._check('COMMA'):
                        self._advance()
                self._expect('RPAREN')
            value = None
            if self._check('ASSIGN'):
                self._advance()
                value = self._parse_expr()
            variants.append(EnumVariant(var_name, value))
            if self._check('COMMA'):
                self._advance()
        self._expect('RBRACE')
        tok = self.tokens[self.pos - 1]
        return DeclEnum(name, variants, exported, line=tok.line, col=tok.col)

    def _parse_trait_decl(self, exported):
        self._advance()
        name = self._expect('IDENT').value
        with self._ctx(f'trait {name}'):
            return self._parse_trait_decl_rest(exported, name)

    def _parse_trait_decl_rest(self, exported, name):
        self._expect('LBRACE')
        methods = []
        while not self._check('RBRACE') and not self._check('EOF'):
            if self._check('SEMICOLON'):
                self._advance()
                continue
            return_type = self._parse_type()
            method_name = self._expect('IDENT').value
            generic_params = []
            if self._check('BANG_LT'):
                self._advance()
                generic_params = self._parse_generic_param_list()
                self._expect('GT')
            self._expect('LPAREN')
            params, variadic = self._parse_param_list()
            self._expect('RPAREN')
            self._expect('SEMICOLON')
            methods.append(DeclFunc(method_name, return_type, params,
                                    generic_params, extern=True,
                                    line=return_type.line, col=return_type.col))
        self._expect('RBRACE')
        tok = self.tokens[self.pos - 1]
        return DeclTrait(name, methods, exported, line=tok.line, col=tok.col)

    def _parse_typedef_decl(self, exported):
        self._advance()
        name = self._expect('IDENT').value
        self._expect('ASSIGN')
        type_expr = self._parse_type()
        self._expect('SEMICOLON')
        tok = self.tokens[self.pos - 1]
        return DeclTypedef(name, type_expr, exported, line=tok.line, col=tok.col)

    def _parse_distinct_decl(self, exported):
        self._advance()
        name = self._expect('IDENT').value
        self._expect('ASSIGN')
        type_expr = self._parse_type()
        self._expect('SEMICOLON')
        tok = self.tokens[self.pos - 1]
        return DeclDistinct(name, type_expr, exported, line=tok.line, col=tok.col)

    def _parse_compiler_fn_decl(self, exported):
        self._advance()
        tok = self._peek()
        return_type = self._parse_type()
        name = self._expect('IDENT').value
        self._expect('LPAREN')
        params, variadic = self._parse_param_list()
        self._expect('RPAREN')
        self._expect('SEMICOLON')
        return DeclFunc(name, return_type, params, [],
                        extern=True, exported=exported,
                        line=tok.line, col=tok.col)

    def _parse_flag_decl(self, exported):
        """flag (NAME) { case: decls... default: decls... }"""
        tok = self._advance()
        self._expect('LPAREN')
        name = self._expect('IDENT').value
        self._expect('RPAREN')
        with self._ctx(f'flag {name}'):
            return self._parse_flag_decl_rest(exported, name, tok)

    def _parse_flag_decl_rest(self, exported, name, tok):
        self._expect('LBRACE')
        cases = []
        default_case = None
        while not self._check('RBRACE') and not self._check('EOF'):
            if self._check('DEFAULT'):
                self._advance()
                self._expect('COLON')
                default_case = self._parse_flag_case_body()
            elif self._check('IDENT'):
                cname = self._advance().value
                self._expect('COLON')
                cases.append((cname, self._parse_flag_case_body()))
            else:
                self._advance()
        self._expect('RBRACE')
        return DeclFlag(name, cases, default_case, line=tok.line, col=tok.col)

    def _parse_flag_case_body(self):
        decls = []
        while self.pos < len(self.tokens) and not self._check('RBRACE') \
              and not self._check('DEFAULT') \
              and not (self._check('IDENT') and self._peek(1).kind == 'COLON'):
            saved = self.pos
            decl = self._parse_decl()
            if decl is None:
                break
            if isinstance(decl, tuple):
                decls.extend(decl)
            else:
                decls.append(decl)
            if self.pos == saved:
                self._advance()
        return decls

    def _parse_func_decl(self, exported, is_method=False, struct_name=None,
                         trait_name=None):
        tok = self._peek()
        return_type = self._parse_type()
        name = self._expect('IDENT').value
        with self._ctx(f'function {name}'):
            return self._parse_func_decl_rest(
                tok, return_type, name, exported,
                is_method, struct_name, trait_name)

    def _parse_func_decl_rest(self, tok, return_type, name, exported,
                              is_method, struct_name, trait_name):
        generic_params = []
        if self._check('BANG_LT') or self._check('LT'):
            if self._check('BANG_LT'):
                self._advance()
            else:
                self._advance()
            generic_params = self._parse_generic_param_list()
            self._expect('GT')
        self._expect('LPAREN')
        params, variadic = self._parse_param_list()
        self._expect('RPAREN')
        noreturn = False
        if self._check('NO_RETURN'):
            self._advance()
            noreturn = True
        body = None
        if self._check('LBRACE'):
            body = self._parse_block()
        else:
            self._expect('SEMICOLON')
        return DeclFunc(name, return_type, params, generic_params, body,
                        exported=exported, is_method=is_method,
                        struct_name=struct_name, trait_name=trait_name,
                        noreturn=noreturn, line=tok.line, col=tok.col)

    def _parse_type_first_decl(self, exported, static=False, inline=False):
        tok = self._peek()
        saved_pos = self.pos

        # Check for namespace block: namespace NAME {
        if self._check('IDENT') and self._peek().value == 'namespace':
            self._advance()
            name = self._expect('IDENT').value
            self._expect('LBRACE')
            decls = []
            while not self._check('RBRACE') and not self._check('EOF'):
                self._skip_semicolons()
                decl = self._parse_decl()
                if decl:
                    decls.append(decl)
            self._expect('RBRACE')
            return DeclNamespace(name, decls, line=tok.line, col=tok.col)

        # Check for method block: Name { or option<T> {
        if self._check('IDENT'):
            n1 = self._advance().value
            gen_params = None
            if self._check('LT'):
                self._advance()
                gen_params = self._parse_generic_param_list()
                self._expect('GT')
            if self._check('LBRACE'):
                self._advance()
                # Method block: Name { ... } or option<T> { ... }
                methods = []
                with self._ctx(f'methods of {n1}'):
                    while not self._check('RBRACE') and not self._check('EOF'):
                        self._skip_semicolons()
                        method = self._parse_func_decl(False, is_method=True,
                                                       struct_name=n1)
                        if method:
                            methods.append(method)
                self._expect('RBRACE')
                return DeclMethodBlock(n1, None, methods, line=tok.line, col=tok.col)
            if gen_params is not None:
                # Generic type as return type, not a method block
                # Fall through to type-first parsing
                pass
            elif self._check('COLON_COLON'):
                self._advance()
                n2 = self._peek()
                if self._check('IDENT') and self._peek(1).kind == 'LBRACE':
                    n2 = self._advance().value
                    # Trait impl block: Name :: TraitName { ... }
                    methods = []
                    with self._ctx(f'trait impl {n1} :: {n2}'):
                        while not self._check('RBRACE') and not self._check('EOF'):
                            self._skip_semicolons()
                            method = self._parse_func_decl(False, is_method=True,
                                                           struct_name=n1,
                                                           trait_name=n2)
                            if method:
                                methods.append(method)
                    self._expect('RBRACE')
                    return DeclMethodBlock(n1, n2, methods,
                                           line=tok.line, col=tok.col)
            # Could be return-type name(...) or type ident = ...
            self.pos = saved_pos

        # Try to parse as type-first declaration
        return_type = self._parse_type()
        if return_type is None:
            return None

        name = self._peek()
        if name.kind != 'IDENT':
            self.pos = saved_pos
            return None

        name_val = self._advance().value
        with self._ctx(f'declaration of {name_val}'):
            return self._parse_type_first_decl_rest(
                tok, saved_pos, return_type, name_val, exported, static,
                inline)

    def _parse_type_first_decl_rest(self, tok, saved_pos, return_type,
                                    name_val, exported, static, inline=False):
        # Could be function declaration
        if self._check('BANG_LT') or self._check('LT'):
            in_bang = self._check('BANG_LT')
            if in_bang:
                self._advance()
            else:
                self._advance()
            saved2 = self.pos
            # Try generic params
            gentok = []
            while not self._check('GT') and not self._check('EOF'):
                gentok.append(self._advance())
            gt = self._peek()
            if gt.kind == 'GT' and self._peek(1).kind == 'LPAREN':
                self.pos = saved2
                generic_params = self._parse_generic_param_list()
                self._expect('GT')
            else:
                self.pos = saved2
                generic_params = []

        if self._check('LPAREN'):
            self._advance()
            params, variadic = self._parse_param_list()
            self._expect('RPAREN')
            noreturn = self._check('NO_RETURN')
            if noreturn:
                self._advance()
            body = None
            if self._check('LBRACE'):
                body = self._parse_block()
            else:
                self._expect('SEMICOLON')
            return DeclFunc(name_val, return_type, params, generic_params
                           if 'generic_params' in dir() else [],
                           body, exported, static, line=tok.line, col=tok.col,
                           inline=inline)
        if self._check('LBRACKET'):
            self._advance()
            array_size = None
            if not self._check('RBRACKET'):
                array_size = self._parse_expr()
            self._expect('RBRACKET')
            return_type = TypeArray(return_type, array_size,
                                    line=return_type.line, col=return_type.col)
        if self._check('SEMICOLON'):
            self._advance()
            return DeclVar(name_val, return_type, None, exported,
                           line=tok.line, col=tok.col)
        elif self._check('ASSIGN'):
            self._advance()
            value = self._parse_expr()
            self._expect('SEMICOLON')
            return DeclVar(name_val, return_type, value, exported,
                           line=tok.line, col=tok.col)
        else:
            self.pos = saved_pos
            return None

    # Parameter parsing

    def _parse_param_list(self):
        params = []
        variadic = False
        if not self._check('RPAREN') and not self._check('SEMICOLON'):
            if self._check('ELLIPSIS') or self._check('...'):
                self._advance()
                variadic = True
            else:
                if self._check('SELF'):
                    saved = self.pos
                    self._advance()
                    if self._check('COLON'):
                        self._advance()
                        param_type = self._parse_type()
                        if self._check('IDENT') or self._check('TYPE'):
                            pn = self._advance().value
                        else:
                            pn = 'self'
                        params.append(Param(pn, param_type))
                    else:
                        self.pos = saved
                        param_type = self._parse_type()
                        if self._check('IDENT') or self._check('TYPE') or self._check('SELF'):
                            ptok = self._advance()
                            pn = 'self' if ptok.kind == 'SELF' else ptok.value
                        else:
                            pn = 'self'
                        params.append(Param(pn, param_type))
                elif self._check('CONST') or self._check('TYPE') or self._check('IDENT'):
                    param_type = self._parse_type()
                    if self._check('ELLIPSIS') or self._check('...'):
                        self._advance()
                        variadic = True
                        if self._check('IDENT') or self._check('TYPE') or self._check('SELF'):
                            ptok = self._advance()
                            pn = 'self' if ptok.kind == 'SELF' else ptok.value
                        else:
                            pn = None
                        params.append(Param(pn, param_type))
                    else:
                        if self._check('IDENT') or self._check('TYPE') or self._check('SELF'):
                            ptok = self._advance()
                            pn = 'self' if ptok.kind == 'SELF' else ptok.value
                            params.append(Param(pn, param_type))
                        else:
                            params.append(Param(None, param_type))
                while self._check('COMMA') and not self._check('RPAREN'):
                    self._advance()
                    if self._check('ELLIPSIS') or self._check('...'):
                        self._advance()
                        variadic = True
                        break
                    param_type = self._parse_type()
                    if self._check('IDENT') or self._check('TYPE') or self._check('SELF'):
                        ptok = self._advance()
                        pn = 'self' if ptok.kind == 'SELF' else ptok.value
                    else:
                        pn = None
                    params.append(Param(pn, param_type))
        return params, variadic

    def _parse_generic_param_list(self):
        params = []
        while not self._check('GT') and not self._check('EOF'):
            if self._check('IDENT'):
                params.append(self._advance().value)
                if self._check('COMMA'):
                    self._advance()
                continue
            self._advance()
        return params

    # Type parsing

    def _parse_type(self):
        tok = self._peek()
        # The '>>' flag is scoped to a single generic construct: every type
        # parse starts with a clean slate so a flag left over from a
        # backtracked attempt can never leak into the next parse.
        self._gtgt_consumed = False

        # Check for const prefix
        is_const = False
        if self._check('CONST'):
            self._advance()
            is_const = True

        # Consume C qualifiers used in inline/MMIO code
        while self._check('IDENT') and self._peek().value in ('volatile', 'restrict'):
            self._advance()

        # Parse base type
        base = None
        if self._check('TYPE'):
            name = self._advance().value
            # Check for generic args
            if self._check('BANG_LT') or self._check('LT'):
                self._advance()
                args = []
                while not self._check('GT') and not self._check('GTGT') \
                      and not self._check('RANGLE') and not self._check('EOF') \
                      and not self._gtgt_consumed:
                    if self._check('COMMA'):
                        self._advance()
                        continue
                    args.append(self._parse_generic_arg())
                    if self._check('COMMA'):
                        self._advance()
                self._finish_generic_args()
                base = TypeGeneric(name, args, line=tok.line, col=tok.col)
            else:
                base = TypeIdent(name, line=tok.line, col=tok.col)

        elif self._check('SELF'):
            self._advance()
            base = TypeIdent('self', line=tok.line, col=tok.col)

        elif self._check('IDENT'):
            name = self._advance().value
            if self._check('COLON_COLON') or self._check('DOT'):
                parts = [name]
                while self._check('COLON_COLON') or self._check('DOT'):
                    self._advance()
                    if self._check('IDENT') or self._check('TYPE'):
                        parts.append(self._advance().value)
                    else:
                        break
                full_path = '.'.join(parts)
                if self._check('BANG_LT') or self._check('LT'):
                    self._advance()
                    args = []
                    while not self._check('GT') and not self._check('GTGT') \
                          and not self._check('RANGLE') and not self._check('EOF') \
                          and not self._gtgt_consumed:
                        if self._check('COMMA'):
                            self._advance()
                            continue
                        args.append(self._parse_generic_arg())
                        if self._check('COMMA'):
                            self._advance()
                    self._finish_generic_args()
                    base = TypeGeneric(full_path, args, line=tok.line, col=tok.col)
                else:
                    base = TypeIdent(full_path, line=tok.line, col=tok.col)
            elif self._check('BANG_LT') or self._check('LT'):
                in_bang = self._check('BANG_LT')
                self._advance()
                args = []
                while not self._check('GT') and not self._check('GTGT') \
                      and not self._check('RANGLE') and not self._check('EOF') \
                      and not self._gtgt_consumed:
                    if self._check('COMMA'):
                        self._advance()
                        continue
                    args.append(self._parse_generic_arg())
                    if self._check('COMMA'):
                        self._advance()
                self._finish_generic_args()
                base = TypeGeneric(name, args, line=tok.line, col=tok.col)
            else:
                base = TypeIdent(name, line=tok.line, col=tok.col)

        elif self._check('SELF'):
            self._advance()
            base = TypeIdent('self', line=tok.line, col=tok.col)
        elif self._check('VOID'):
            self._advance()
            base = TypeIdent('void', line=tok.line, col=tok.col)
        elif self._check('LPAREN'):
            # Function pointer type: (void)(i32)
            self._advance()
            if self._check('TYPE') or self._check('IDENT'):
                return_type = self._parse_type()
                params = []
                if self._check('RPAREN'):
                    self._advance()
                    if self._check('LPAREN'):
                        self._advance()
                        while not self._check('RPAREN') and not self._check('EOF'):
                            pt = self._parse_type()
                            if pt is None:
                                break
                            params.append(pt)
                            if self._check('COMMA'):
                                self._advance()
                        if self._check('RPAREN'):
                            self._advance()
                base = TypeFunc(params, return_type, line=tok.line, col=tok.col)
            else:
                self._error('Expected type after (')
        else:
            return None  # Not a type

        # Handle postfix '*' pointers
        ptr_const = False
        if is_const and self._check('STAR'):
            self._advance()
            base = TypePointer(base, const=True, line=tok.line, col=tok.col)
            is_const = False

        while self._check('STAR'):
            self._advance()
            base = TypePointer(base, const=ptr_const, line=tok.line, col=tok.col)
            ptr_const = False

        # Handle postfix function type: return_type(params...)
        # A '(' directly after a generic instantiation is always a call
        # (e.g. `alloc<HashMapEntry<K, V>>(16)`), never a function type;
        # only non-generic bases like `u64(K) hashFn` take the function-type
        # interpretation here.
        if self._check('LPAREN') and base is not None \
           and not (isinstance(base, TypeGeneric) and self._gtgt_consumed):
            self._advance()
            param_types = []
            while not self._check('RPAREN') and not self._check('EOF'):
                pt = self._parse_type()
                if pt is None:
                    break
                param_types.append(pt)
                if self._check('COMMA'):
                    self._advance()
            if self._check('RPAREN'):
                self._advance()
                base = TypeFunc(param_types, base, line=base.line, col=base.col)

        return base

    def _parse_type_or_expr_as_type(self):
        tok = self._peek()
        if self._check('TYPE') or self._check('IDENT') or self._check('CONST') \
           or self._check('SELF') or self._check('VOID') \
           or self._check('STRUCT') or self._check('LPAREN'):
            return self._parse_type()
        return self._parse_expr()

    def _parse_generic_arg(self):
        tok = self._peek()
        if self._check('TYPE') or self._check('IDENT') or self._check('CONST') \
           or self._check('SELF') or self._check('VOID') \
           or self._check('STRUCT') or self._check('LPAREN'):
            return self._parse_type()
        saved = self.pos
        expr = self._parse_expr()
        if self._check('GT') or self._check('COMMA') or self._check('RANGLE') \
           or self._check('GTGT'):
            return expr
        self.pos = saved
        return self._parse_primary()

    def _close_generic(self):
        tok = self._peek()
        if tok.kind == 'GT':
            self._advance()
            return True
        elif tok.kind == 'GTGT':
            # '>>' closes BOTH the current generic list and the enclosing
            # one. Consume it whole (never mutate the token stream, which
            # would corrupt backtracking) and notify the enclosing args
            # loop via the flag.
            self._advance()
            self._gtgt_consumed = True
            return True
        elif tok.kind == 'RANGLE':
            self._advance()
            return True
        self._error(
            f"expected '>' to close the generic argument list, found "
            f"'{token_display(tok.kind)}'"
            + (f" '{tok.value}'" if tok.kind in ('IDENT', 'TYPE', 'INT', 'FLOAT', 'STRING', 'CHAR') else '')
            + " — nested generics like Foo<Bar<Baz>> need one '>' per level; "
              "count how many '<' you opened and add the matching '>'s")

    def _finish_generic_args(self):
        """Close the current generic arg list. If an inner arg's '>>' already
        consumed the closing '>' of this list too, just swallow the flag."""
        if self._gtgt_consumed:
            self._gtgt_consumed = False
            return
        self._close_generic()

    # Block parsing

    def _parse_block(self):
        self._expect('LBRACE')
        stmts = self._parse_stmts()
        self._expect('RBRACE')
        return StmtBlock(stmts)

    def _parse_stmts(self):
        stmts = []
        while not self._check('RBRACE') and not self._check('EOF'):
            self._skip_semicolons()
            if self._check('RBRACE') or self._check('EOF'):
                break
            stmt = self._parse_stmt()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def _parse_stmt(self):
        tok = self._peek()

        if self._check('SEMICOLON'):
            self._advance()
            return None

        if self._check('LBRACE'):
            return self._parse_block()

        if self._check('IF'):
            return self._parse_if_stmt()

        if self._check('FOR'):
            return self._parse_for_stmt()

        if self._check('WHILE'):
            return self._parse_while_stmt()

        if self._check('LOOP'):
            return self._parse_loop_stmt()

        if self._check('SWITCH'):
            return self._parse_switch_stmt()

        if self._check('BREAK'):
            self._advance()
            self._expect('SEMICOLON')
            return StmtBreak(line=tok.line, col=tok.col)

        if self._check('CONTINUE'):
            self._advance()
            self._expect('SEMICOLON')
            return StmtContinue(line=tok.line, col=tok.col)

        if self._check('RETURN'):
            return self._parse_return_stmt()

        if self._check('NO_RETURN'):
            self._advance()
            self._expect('SEMICOLON')
            return StmtReturn(is_noreturn=True, line=tok.line, col=tok.col)

        if self._check('DEFER'):
            self._advance()
            body = self._parse_stmt()
            self._expect('SEMICOLON')
            return StmtDefer(body, line=tok.line, col=tok.col)

        if self._check('ASSERT'):
            return self._parse_assert_stmt()

        if self._check('ASM'):
            return self._parse_asm_stmt()

        if self._check('COMPTIME'):
            self._advance()
            return self._parse_block()

        if self._check('FLAG'):
            return self._parse_flag_stmt()

        if self._check('VAR'):
            self._advance()
            name = self._expect('IDENT').value
            type_expr = None
            if self._check('COLON'):
                self._advance()
                type_expr = self._parse_type()
            value = None
            if self._check('ASSIGN'):
                self._advance()
                value = self._parse_expr()
            self._expect('SEMICOLON')
            return StmtVar(name, type_expr, value, line=tok.line, col=tok.col)

        if self._check('CONST') or self._check('TYPE') or self._check('IDENT'):
            saved = self.pos
            # Could be: type name = expr; or type name; (variable statement)
            # Or: expr; (expression statement)
            try:
                type_or_expr = self._parse_type_or_expr_as_type()
                if type_or_expr is None:
                    self.pos = saved
                    return self._parse_expr_stmt()
                if not isinstance(type_or_expr, (TypeIdent, TypePointer,
                                                  TypeArray, TypeGeneric,
                                                  TypeFunc)):
                    self.pos = saved
                    return self._parse_expr_stmt()
            except ParseError:
                # Not a type after all — e.g. a compound expression such as
                # `a < b` or a generic call. Parse it as an expression.
                self.pos = saved
                return self._parse_expr_stmt()

            # From here the statement is a real type; commit to the
            # declaration. Errors past this point are real and propagate.
            if self._check('IDENT') or self._check('SELF'):
                # type name ... — variable declaration
                ptok = self._advance()
                name = 'self' if ptok.kind == 'SELF' else ptok.value
                # Check for array size
                if self._check('LBRACKET'):
                    self._advance()
                    array_size = self._parse_expr()
                    self._expect('RBRACKET')
                    type_or_expr = TypeArray(type_or_expr, array_size)
                value = None
                if self._check('ASSIGN'):
                    self._advance()
                    value = self._parse_expr()
                # Multi-var: type name1, name2, ...
                if self._check('COMMA'):
                    vars = [(name, type_or_expr, value)]
                    while self._check('COMMA'):
                        self._advance()
                        ptok = self._advance() if (self._check('IDENT') or self._check('SELF')) else self._error('Expected identifier')
                        vname = 'self' if ptok.kind == 'SELF' else ptok.value
                        vval = None
                        if self._check('ASSIGN'):
                            self._advance()
                            vval = self._parse_expr()
                        vars.append((vname, type_or_expr, vval))
                    self._expect('SEMICOLON')
                    first = StmtVar(vars[0][0], vars[0][1], vars[0][2],
                                    line=tok.line, col=tok.col)
                    rest = [StmtVar(v[0], v[1], v[2]) for v in vars[1:]]
                    return StmtBlock([first] + rest,
                                      line=tok.line, col=tok.col)
                self._expect('SEMICOLON')
                return StmtVar(name, type_or_expr, value,
                               line=tok.line, col=tok.col)
            elif self._check('LBRACE'):
                # struct initializer as statement
                self._advance()
                fields = []
                while not self._check('RBRACE') and not self._check('EOF'):
                    if self._check('SEMICOLON'):
                        self._advance()
                        continue
                    field_name = self._expect('IDENT').value
                    self._expect('ASSIGN')
                    field_val = self._parse_expr()
                    fields.append((field_name, field_val))
                    if self._check('COMMA'):
                        self._advance()
                self._expect('RBRACE')
                return StmtExpr(ExprInitializer(type_or_expr, fields,
                                                line=tok.line, col=tok.col))

            # Must be an expression
            self.pos = saved
            return self._parse_expr_stmt()

        return self._parse_expr_stmt()

    def _parse_flag_stmt(self):
        """flag (NAME) { case: stmts... default: stmts... }"""
        tok = self._advance()
        self._expect('LPAREN')
        name = self._expect('IDENT').value
        self._expect('RPAREN')
        self._expect('LBRACE')
        cases = []
        default_body = None
        while not self._check('RBRACE') and self.pos < len(self.tokens):
            if self._check('DEFAULT'):
                self._advance()
                self._expect('COLON')
                default_body = []
                while self.pos < len(self.tokens) and not self._check('RBRACE') \
                      and not self._check('IDENT') and not self._check('DEFAULT') \
                      and not self._check('CASE'):
                    s = self._parse_stmt()
                    if s is not None:
                        default_body.append(s)
            elif self._check('IDENT'):
                cname = self._advance().value
                self._expect('COLON')
                body = []
                while self.pos < len(self.tokens) and not self._check('RBRACE') \
                      and not self._check('IDENT') and not self._check('DEFAULT') \
                      and not self._check('CASE'):
                    s = self._parse_stmt()
                    if s is not None:
                        body.append(s)
                cases.append((cname, body))
            else:
                self._advance()
        self._expect('RBRACE')
        return StmtFlag(name, cases, default_body, line=tok.line, col=tok.col)

    def _raw_slice(self, line1, col1, line2, col2):
        """Return the original source text from (line1, col1) to
        (line2, col2), both 1-based and inclusive of end col."""
        if self._lines is None:
            return None
        if line1 == line2:
            return self._lines[line1 - 1][col1 - 1:col2]
        parts = [self._lines[line1 - 1][col1 - 1:]]
        for ln in range(line1, line2 - 1):
            parts.append(self._lines[ln])
        parts.append(self._lines[line2 - 1][:col2])
        return '\n'.join(parts)

    def _parse_asm_stmt(self):
        tok = self._advance()  # consume 'asm'
        # Skip optional volatile/inline qualifiers
        while self._check('IDENT') and self._peek().value in ('volatile', 'inline'):
            self._advance()
        self._expect('LBRACE')
        # Collect raw assembly tokens until matching }
        depth = 1
        body_tokens = []
        close_tok = None
        while depth > 0 and self.pos < len(self.tokens):
            t = self._advance()
            if t.kind == 'LBRACE':
                depth += 1
            elif t.kind == 'RBRACE':
                depth -= 1
                if depth == 0:
                    close_tok = t
                    break
            body_tokens.append(t)
        if self._check('SEMICOLON'):
            self._advance()
        if close_tok is not None:
            # Prefer the exact source text so punctuation survives
            # verbatim (asm operands use ':', '%', '"' etc.)
            raw = self._raw_slice(tok.line, tok.col,
                                  close_tok.line,
                                  close_tok.col + (close_tok.length or 1))
            if raw is not None:
                return StmtAsm(raw, line=tok.line, col=tok.col)
            body = ' '.join(str(t.value or t.kind) for t in body_tokens)
        else:
            body = ' '.join(str(t.value or t.kind) for t in body_tokens)
        return StmtAsm(body, line=tok.line, col=tok.col)

    def _parse_if_stmt(self):
        self._advance()
        self._expect('LPAREN')
        condition = self._parse_expr()
        self._expect('RPAREN')
        then_block = self._parse_block_or_stmt()
        else_block = None
        if self._check('ELSE'):
            self._advance()
            if self._check('IF'):
                else_block = StmtBlock([self._parse_if_stmt()])
            else:
                else_block = self._parse_block_or_stmt()
        return StmtIf(condition, then_block, else_block)

    def _parse_block_or_stmt(self):
        if self._check('LBRACE'):
            return self._parse_block()
        stmt = self._parse_stmt()
        return StmtBlock([stmt]) if stmt else StmtBlock()

    def _parse_for_stmt(self):
        tok = self._peek()
        self._advance()
        self._expect('LPAREN')
        # Check for range-based for: for (var name : expr)
        if self._check('VAR'):
            self._advance()
            name = self._expect_ident_or_type().value
            self._expect('COLON')
            iterable = self._parse_expr()
            self._expect('RPAREN')
            body = self._parse_block_or_stmt()
            return StmtForIn(name, iterable, body, line=tok.line, col=tok.col)
        init = None
        if not self._check('SEMICOLON'):
            if self._check('TYPE') or self._check('CONST') or self._check('IDENT'):
                saved = self.pos
                try:
                    typ = self._parse_type()
                    if isinstance(typ, (TypeIdent, TypePointer, TypeGeneric)):
                        if self._check('IDENT'):
                            name = self._advance().value
                            init = StmtVar(name, typ)
                            if self._check('ASSIGN'):
                                self._advance()
                                init.value = self._parse_expr()
                        else:
                            self.pos = saved
                            init = StmtExpr(self._parse_expr())
                    else:
                        self.pos = saved
                        init = StmtExpr(self._parse_expr())
                except:
                    self.pos = saved
                    init = StmtExpr(self._parse_expr())
            else:
                init = StmtExpr(self._parse_expr())
        self._expect('SEMICOLON')
        condition = None
        if not self._check('SEMICOLON'):
            condition = self._parse_expr()
        self._expect('SEMICOLON')
        increment = None
        if not self._check('RPAREN'):
            increment = self._parse_expr()
        self._expect('RPAREN')
        body = self._parse_block_or_stmt()
        return StmtFor(init, condition, increment, body)

    def _parse_while_stmt(self):
        self._advance()
        self._expect('LPAREN')
        condition = self._parse_expr()
        self._expect('RPAREN')
        body = self._parse_block_or_stmt()
        return StmtWhile(condition, body)

    def _parse_loop_stmt(self):
        self._advance()
        body = self._parse_block_or_stmt()
        return StmtLoop(body)

    def _parse_switch_stmt(self):
        tok = self._advance()
        self._expect('LPAREN')
        cond = self._parse_expr()
        self._expect('RPAREN')
        self._expect('LBRACE')
        cases = []
        default_body = None
        while not self._check('RBRACE') and self.pos < len(self.tokens):
            if self._check('CASE'):
                self._advance()
                value = self._parse_expr()
                self._expect('COLON')
                body = []
                while self.pos < len(self.tokens) and not self._check('RBRACE') \
                      and not self._check('CASE') and not self._check('DEFAULT'):
                    stmt = self._parse_stmt()
                    if stmt is not None:
                        body.append(stmt)
                cases.append(StmtCase(value, body, line=tok.line, col=tok.col))
            elif self._check('DEFAULT'):
                self._advance()
                self._expect('COLON')
                body = []
                while self.pos < len(self.tokens) and not self._check('RBRACE') \
                      and not self._check('CASE') and not self._check('DEFAULT'):
                    stmt = self._parse_stmt()
                    if stmt is not None:
                        body.append(stmt)
                default_body = body
            else:
                break
        self._expect('RBRACE')
        return StmtSwitch(cond, cases, default_body, line=tok.line, col=tok.col)

    def _parse_return_stmt(self):
        self._advance()
        value = None
        if not self._check('SEMICOLON'):
            value = self._parse_expr()
        self._expect('SEMICOLON')
        return StmtReturn(value)

    def _parse_assert_stmt(self):
        self._advance()
        self._expect('LPAREN')
        condition = self._parse_expr()
        self._expect('RPAREN')
        self._expect('SEMICOLON')
        return StmtAssert(condition)

    def _parse_expr_stmt(self):
        expr = self._parse_expr()
        if self._check('ASSIGN') or self._check('PLUS_EQ') or self._check('MINUS_EQ') \
           or self._check('STAR_EQ') or self._check('SLASH_EQ') \
           or self._check('PERCENT_EQ') or self._check('AMPERSAND_EQ') \
           or self._check('PIPE_EQ') or self._check('CARET_EQ') \
           or self._check('LTLT_EQ') or self._check('GTGT_EQ'):
            op = ASSIGN_OPS[self._peek().kind]
            self._advance()
            value = self._parse_expr()
            self._expect('SEMICOLON')
            return StmtAssign(expr, value, op)
        self._expect('SEMICOLON')
        return StmtExpr(expr)

    # Expression parsing

    def _parse_expr(self, min_prec=0):
        return self._parse_binary(min_prec)

    def _parse_binary(self, min_prec):
        left = self._parse_unary()

        while True:
            tok = self._peek()
            if tok.kind in BINARY_OPS:
                op_str, prec = BINARY_OPS[tok.kind]
                if prec < min_prec:
                    break
                self._advance()
                right = self._parse_binary(prec + 1)
                left = ExprBinary(op_str, left, right, line=tok.line, col=tok.col)
            elif tok.kind in ASSIGN_OPS_BIN:
                op_str, prec = ASSIGN_OPS_BIN[tok.kind]
                if prec < min_prec:
                    break
                self._advance()
                right = self._parse_binary(prec)  # right-associative
                left = ExprBinary(op_str, left, right, line=tok.line, col=tok.col)
            elif tok.kind == 'QUESTION':
                if PREC['TERNARY'] < min_prec:
                    break
                self._advance()
                then_expr = self._parse_expr()
                self._expect('COLON')
                else_expr = self._parse_expr(PREC['TERNARY'])
                left = ExprTernary(left, then_expr, else_expr, line=tok.line, col=tok.col)
            else:
                break

        return left

    def _parse_unary(self):
        tok = self._peek()
        if tok.kind in PREFIX_OPS:
            self._advance()
            op = PREFIX_OPS[tok.kind]
            operand = self._parse_unary()
            if op == '*':
                return ExprDeref(operand, line=tok.line, col=tok.col)
            if op == '&':
                return ExprAddrOf(operand, line=tok.line, col=tok.col)
            return ExprUnary(op, operand, line=tok.line, col=tok.col)

        if self._check('LPAREN') and (self._peek(1).kind == 'TYPE' or
                                       self._peek(1).kind == 'IDENT' or
                                       self._peek(1).kind == 'CONST'):
            # Check if it's a cast: (type) expr
            saved = self.pos
            self._advance()
            try:
                typ = self._parse_type()
            except ParseError:
                self.pos = saved
                typ = None
            if typ is not None and self._check('RPAREN'):
                self._advance()
                try:
                    operand = self._parse_unary()
                except ParseError:
                    self.pos = saved
                    operand = None
                if operand is not None:
                    return ExprCast(typ, operand, line=tok.line, col=tok.col)
                self.pos = saved
            else:
                self.pos = saved
        return self._parse_primary()

    def _parse_primary(self):
        left = self._parse_atom()
        return self._parse_postfix(left)

    def _parse_atom(self):
        tok = self._peek()

        if tok.kind == 'INT':
            self._advance()
            return ExprInt(tok.value, line=tok.line, col=tok.col, suffix=getattr(tok, 'suffix', ''))

        if tok.kind == 'FLOAT':
            self._advance()
            return ExprFloat(tok.value, line=tok.line, col=tok.col)

        if tok.kind == 'STRING':
            self._advance()
            return ExprString(tok.value, line=tok.line, col=tok.col)

        if tok.kind == 'CHAR':
            self._advance()
            return ExprChar(tok.value, line=tok.line, col=tok.col)

        if tok.kind == 'TRUE':
            self._advance()
            return ExprBool(True, line=tok.line, col=tok.col)

        if tok.kind == 'FALSE':
            self._advance()
            return ExprBool(False, line=tok.line, col=tok.col)

        if tok.kind == 'NULL' or tok.kind == 'NIL':
            self._advance()
            return ExprNull(line=tok.line, col=tok.col)

        if tok.kind == 'SIZEOF':
            self._advance()
            self._expect('LPAREN')
            typ = self._parse_type()
            self._expect('RPAREN')
            return ExprSizeof(typ, line=tok.line, col=tok.col)

        if tok.kind == 'LPAREN':
            self._advance()
            saved = self.pos
            # Check for C-style cast: (type)expr
            if self._check('TYPE') or self._check('CONST') or self._check('IDENT') or self._check('MUL'):
                try:
                    typ = self._parse_type()
                    if typ is not None and self._check('RPAREN'):
                        self._advance()
                        operand = self._parse_unary()
                        if operand:
                            return ExprCast(typ, operand, line=tok.line, col=tok.col)
                except ParseError:
                    pass
                self.pos = saved
                # Check for (type) as a type literal in expression context
                if self._check('TYPE') or self._check('CONST') or self._check('IDENT') or self._check('MUL'):
                    try:
                        typ = self._parse_type()
                        if typ is not None and self._check('RPAREN'):
                            self._advance()
                            return ExprTypeLiteral(typ, line=tok.line, col=tok.col)
                    except ParseError:
                        pass
            self.pos = saved
            expr = self._parse_expr()
            self._expect('RPAREN')
            return ExprParen(expr, line=tok.line, col=tok.col)

        if tok.kind == 'IDENT':
            name = self._advance().value
            # Check for module path: a::b::c
            if self._check('COLON_COLON'):
                parts = [name]
                while self._check('COLON_COLON'):
                    self._advance()
                    if self._check('IDENT') or self._check('TYPE'):
                        parts.append(self._advance().value)
                    else:
                        break
                path = '::'.join(parts)
                if self._check('BANG_LT') or self._check('LT'):
                    self._advance()
                    args = []
                    while not self._check('GT') and not self._check('GTGT') \
                          and not self._check('RANGLE') and not self._check('EOF') \
                          and not self._gtgt_consumed:
                        if self._check('COMMA'):
                            self._advance()
                            continue
                        args.append(self._parse_generic_arg())
                        if self._check('COMMA'):
                            self._advance()
                    self._finish_generic_args()
                    left = ExprGenericInst(ExprIdent(path), args,
                                           line=tok.line, col=tok.col)
                    if self._check('COLON_COLON'):
                        self._advance()
                        if self._check('IDENT') or self._check('TYPE'):
                            member = self._advance().value
                            left = ExprDot(left, member, line=tok.line, col=tok.col)
                    return left
                return ExprIdent(path, line=tok.line, col=tok.col)

            # Generic instantiation: ident!<...>
            if self._check('BANG_LT'):
                self._advance()
                args = []
                while not self._check('GT') and not self._check('GTGT') \
                      and not self._check('RANGLE') and not self._check('EOF') \
                      and not self._gtgt_consumed:
                    if self._check('COMMA'):
                        self._advance()
                        continue
                    args.append(self._parse_generic_arg())
                    if self._check('COMMA'):
                        self._advance()
                self._finish_generic_args()
                return ExprGenericInst(ExprIdent(name), args,
                                       line=tok.line, col=tok.col)

            # Generic instantiation with LT in type context: ident<...>
            if self._check('LT'):
                saved = self.pos
                self._advance()
                saved2 = self.pos
                # Try to parse as type args
                args = []
                while not self._check('GT') and not self._check('GTGT') \
                      and not self._check('RANGLE') and not self._check('EOF') \
                      and not self._gtgt_consumed:
                    if self._check('SEMICOLON') or self._check('COMMA') or self._check('RPAREN') or self._check('RBRACE'):
                        break
                    typ = self._parse_type()
                    if typ is None:
                        break
                    args.append(typ)
                    if self._check('COMMA'):
                        self._advance()
                if self._gtgt_consumed:
                    if args:
                        base = ExprGenericInst(ExprIdent(name), args,
                                               line=tok.line, col=tok.col)
                        if self._check('COLON_COLON'):
                            self._advance()
                            if self._check('IDENT') or self._check('TYPE'):
                                member = self._advance().value
                                return ExprDot(base, member, line=tok.line, col=tok.col)
                        return base
                    self.pos = saved
                else:
                    gt = self._peek()
                    if (gt.kind == 'GT' or gt.kind == 'GTGT' or gt.kind == 'RANGLE') and args:
                        if gt.kind == 'GTGT':
                            self._advance()
                            self._gtgt_consumed = True
                        else:
                            self._advance()
                        base = ExprGenericInst(ExprIdent(name), args,
                                               line=tok.line, col=tok.col)
                        # Check for :: continuation: vec<T>::new()
                        if self._check('COLON_COLON'):
                            self._advance()
                            if self._check('IDENT') or self._check('TYPE'):
                                member = self._advance().value
                                return ExprDot(base, member, line=tok.line, col=tok.col)
                        return base
                    self.pos = saved

            # Macro invocation: ident!(...)
            if self._check('BANG') and self._peek(1).kind == 'LPAREN':
                self._advance()
                self._advance()
                args = self._parse_call_args()
                self._expect('RPAREN')
                return ExprCall(ExprIdent(name), line=tok.line, col=tok.col)

            return ExprIdent(name, line=tok.line, col=tok.col)

        if tok.kind == 'TYPE':
            name = self._advance().value
            # Check for module path: string::new
            if self._check('COLON_COLON'):
                parts = [name]
                while self._check('COLON_COLON'):
                    self._advance()
                    if self._check('IDENT') or self._check('TYPE'):
                        parts.append(self._advance().value)
                    else:
                        break
                return ExprIdent('::'.join(parts), line=tok.line, col=tok.col)
            if self._check('BANG_LT'):
                self._advance()
                args = []
                while not self._check('GT') and not self._check('GTGT') \
                      and not self._check('RANGLE') and not self._check('EOF') \
                      and not self._gtgt_consumed:
                    if self._check('COMMA'):
                        self._advance()
                        continue
                    args.append(self._parse_generic_arg())
                    if self._check('COMMA'):
                        self._advance()
                self._finish_generic_args()
                return ExprGenericInst(ExprIdent(name), args,
                                       line=tok.line, col=tok.col)
            return ExprIdent(name, line=tok.line, col=tok.col)

        if self._check('LBRACE'):
            return self._parse_initializer()

        if self._check('SELF'):
            self._advance()
            return ExprIdent('self', line=tok.line, col=tok.col)

        self._error(f'Unexpected token in expression: {tok.kind} ({tok.value})')

    def _lt_is_generic(self):
        """True if the current LT token opens a generic arg list, i.e. the
        matching GT is followed by '(', '.', '::' etc. (a call or member
        access), not a comparison like `a < b`."""
        i = self.pos + 1
        depth = 1
        while i < len(self.tokens):
            t = self.tokens[i]
            if t.kind == 'LT':
                depth += 1
            elif t.kind in ('GT', 'RANGLE'):
                depth -= 1
                if depth == 0:
                    nxt = self.tokens[i + 1] if i + 1 < len(self.tokens) else None
                    if nxt is not None and nxt.kind in (
                            'LPAREN', 'DOT', 'COLON_COLON', 'SEMICOLON',
                            'COMMA', 'RPAREN', 'RBRACKET', 'ASSIGN',
                            'LBRACE', 'LBRACKET'):
                        return True
                    return False
                if depth < 0:
                    return False
            elif t.kind == 'GTGT':
                # '>>' closes two levels at once
                depth -= 2
                if depth == 0:
                    nxt = self.tokens[i + 1] if i + 1 < len(self.tokens) else None
                    if nxt is not None and nxt.kind in (
                            'LPAREN', 'DOT', 'COLON_COLON', 'SEMICOLON',
                            'COMMA', 'RPAREN', 'RBRACKET', 'ASSIGN',
                            'LBRACE', 'LBRACKET'):
                        return True
                    return False
                if depth < 0:
                    return False
            elif t.kind in ('SEMICOLON', 'LPAREN', 'RBRACE', 'EOF'):
                return False
            i += 1
        return False

    def _parse_generic_after_member(self, tok, left, kind):
        self._advance()  # consume BANG_LT or LT
        type_args = []
        while not self._check('GT') and not self._check('GTGT') \
              and not self._check('RANGLE') and not self._check('EOF') \
              and not self._gtgt_consumed:
            if self._check('COMMA'):
                self._advance()
                continue
            type_args.append(self._parse_type())
            if self._check('COMMA'):
                self._advance()
        self._finish_generic_args()
        left = ExprGenericInst(left, type_args, line=tok.line, col=tok.col)
        if self._check('LPAREN'):
            self._advance()
            args = self._parse_call_args()
            self._expect('RPAREN')
            left = ExprCall(left, args, line=tok.line, col=tok.col)
        return left

    def _parse_postfix(self, left):
        while True:
            tok = self._peek()

            if tok.kind == 'LPAREN':
                self._advance()
                args = self._parse_call_args()
                self._expect('RPAREN')
                left = ExprCall(left, args, line=tok.line, col=tok.col)

            elif tok.kind == 'DOT':
                self._advance()
                member = self._expect('IDENT').value
                left = ExprDot(left, member, line=tok.line, col=tok.col)
                if self._check('BANG_LT') or (self._check('LT') and self._lt_is_generic()):
                    left = self._parse_generic_after_member(tok, left, 'DOT')

            elif tok.kind == 'ARROW':
                self._advance()
                member = self._expect('IDENT').value
                left = ExprArrow(left, member, line=tok.line, col=tok.col)
                if self._check('BANG_LT') or (self._check('LT') and self._lt_is_generic()):
                    left = self._parse_generic_after_member(tok, left, 'ARROW')

            elif tok.kind == 'LBRACKET':
                self._advance()
                index = self._parse_expr()
                self._expect('RBRACKET')
                left = ExprIndex(left, index, line=tok.line, col=tok.col)

            elif tok.kind == 'COLON_COLON':
                self._advance()
                if self._check('IDENT') or self._check('TYPE'):
                    member = self._advance().value
                    left = ExprDot(left, member, line=tok.line, col=tok.col)
                else:
                    break

            elif tok.kind == 'INC':
                self._advance()
                left = ExprUnary('++', left, is_postfix=True,
                                 line=tok.line, col=tok.col)

            elif tok.kind == 'DEC':
                self._advance()
                left = ExprUnary('--', left, is_postfix=True,
                                 line=tok.line, col=tok.col)

            elif tok.kind == 'BANG_LT':
                self._advance()
                type_args = []
                while not self._check('GT') and not self._check('GTGT') \
                      and not self._check('RANGLE') and not self._check('EOF') \
                      and not self._gtgt_consumed:
                    if self._check('COMMA'):
                        self._advance()
                        continue
                    type_args.append(self._parse_generic_arg())
                    if self._check('COMMA'):
                        self._advance()
                self._finish_generic_args()
                if self._check('LPAREN'):
                    self._advance()
                    args = self._parse_call_args()
                    self._expect('RPAREN')
                    left = ExprCall(ExprGenericInst(left, type_args), args,
                                    line=tok.line, col=tok.col)
                else:
                    left = ExprGenericInst(left, type_args)

            else:
                break

        return left

    def _parse_call_args(self):
        args = []
        if not self._check('RPAREN'):
            args.append(self._parse_expr())
            while self._check('COMMA'):
                self._advance()
                if self._check('RPAREN'):
                    break
                args.append(self._parse_expr())
        return args

    def _parse_initializer(self):
        # { .field = expr, ... } or { expr, ... }
        tok = self._advance()
        fields = []
        if self._check('DOT'):
            while not self._check('RBRACE') and not self._check('EOF'):
                self._expect('DOT')
                field_name = self._expect('IDENT').value
                self._expect('ASSIGN')
                field_val = self._parse_expr()
                fields.append((field_name, field_val))
                if self._check('COMMA'):
                    self._advance()
        else:
            # Array/compound literal initializer
            while not self._check('RBRACE') and not self._check('EOF'):
                fields.append(self._parse_expr())
                if self._check('COMMA'):
                    self._advance()
        self._expect('RBRACE')
        return ExprInitializer(None, fields, line=tok.line, col=tok.col)

    # Path parsing

    def _parse_path(self):
        parts = []
        while self._check('IDENT') or self._check('TYPE') or self._check('EXTERN'):
            tok = self._advance()
            if tok.kind == 'EXTERN':
                parts.append('extern')
            else:
                parts.append(tok.value)
            if not self._check('COLON_COLON'):
                break
            self._advance()
        return '::'.join(parts)


# Wrapper
def parse(source, filename='<unknown>'):
    tokenizer = Tokenizer(source, filename)
    parser = Parser(tokenizer.tokens, filename)
    return parser.parse()
