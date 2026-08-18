import re
import struct

from coral_ast import ParseError, make_snippet

KEYWORDS = {
    'mod', 'import', 'pub', 'extern',
    'struct', 'enum', 'trait',
    'const', 'var', 'typedef', 'distinct',
    'return', 'if', 'else', 'for', 'while', 'loop',
    'switch', 'case', 'default', 'break', 'continue',
    'defer', 'flag', 'comptime', 'asm', 'inline',
    'true', 'false', 'null', 'nil', 'self', 'static',
    'assert', 'sizeof', 'compiler_fn',
    'unsafe',
}

TYPE_KEYWORDS = {
    'i8', 'i16', 'i32', 'i64',
    'u8', 'u16', 'u32', 'u64',
    'f32', 'f64',
    'bool', 'char', 'void',
}

TOKEN_NAMES = {}

class Token:
    __slots__ = ('kind', 'value', 'line', 'col', 'length', 'suffix')

    def __init__(self, kind, value=None, line=0, col=0, length=0, suffix=''):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col
        self.length = length
        self.suffix = suffix

    def __repr__(self):
        return f'Token({self.kind}, {self.value!r}, L{self.line}:{self.col})'

def token_name(kind):
    return TOKEN_NAMES.get(kind, kind)


class Tokenizer:
    def __init__(self, source, filename='<unknown>'):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.generic_depth = 0
        self._tokenize()

    def _error(self, msg):
        raise ParseError(self.filename, self.line, self.col, msg,
                         context='tokenizer',
                         snippet=make_snippet(self.source.split('\n'),
                                              self.line, self.col))

    def _peek(self, offset=0):
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else '\0'

    def _advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self._peek()
            if ch in ' \t\r\n':
                self._advance()
                continue
            if ch == '/':
                if self._peek(1) == '/':
                    while self.pos < len(self.source) and self._peek() != '\n':
                        self._advance()
                    continue
                if self._peek(1) == '*':
                    self._advance(); self._advance()
                    while self.pos < len(self.source):
                        if self._peek() == '*' and self._peek(1) == '/':
                            self._advance(); self._advance()
                            break
                        self._advance()
                    continue
            if ch == 'z' and self._peek(1) == '/':
                self._advance(); self._advance()
                while self.pos < len(self.source) and self._peek() != '\n':
                    self._advance()
                continue
            break

    def _emit(self, kind, value=None, length=0, suffix=''):
        self.tokens.append(Token(kind, value, self.line, self.col - length, length, suffix))

    def _skip_int_suffix(self):
        start = self.pos
        while self._peek() in 'uUlL':
            self._advance()
        return self.source[start:self.pos]

    def _read_string(self):
        line_start = self.line
        col_start = self.col
        self._advance()
        chars = []
        while self.pos < len(self.source):
            ch = self._advance()
            if ch == '"':
                self._emit('STRING', ''.join(chars), self.col - col_start)
                return
            if ch == '\\':
                esc = self._advance()
                if esc == 'n': chars.append('\n')
                elif esc == 't': chars.append('\t')
                elif esc == 'r': chars.append('\r')
                elif esc == '0': chars.append('\0')
                elif esc == 'a': chars.append('\a')
                elif esc == 'b': chars.append('\b')
                elif esc == 'e': chars.append('\x1b')
                elif esc == 'v': chars.append('\v')
                elif esc == 'f': chars.append('\f')
                elif esc == '\\': chars.append('\\')
                elif esc == '"': chars.append('"')
                elif esc == "'": chars.append("'")
                elif esc == 'x':
                    h1 = self._advance()
                    h2 = self._advance()
                    chars.append(chr(int(h1 + h2, 16)))
                else:
                    chars.append(esc)
            else:
                chars.append(ch)
        raise SyntaxError(self._unterminated_msg('string', line_start, col_start))

    def _unterminated_msg(self, what, line_start, col_start):
        line_txt = self.source.splitlines()[line_start - 1] \
            if 1 <= line_start <= len(self.source.splitlines()) else ''
        return (f'{self.filename}:{line_start}:{col_start}: Unterminated {what} literal — '
                f'the opening quote is on line {line_start} but the closing quote was '
                f'never found.\n'
                f'    {line_start} | {line_txt}\n'
                f'    {" " * len(str(line_start))} | {" " * (col_start - 1)}^ ')

    def _read_char(self):
        line_start = self.line
        col_start = self.col
        self._advance()
        ch = self._advance()
        if ch == '\\':
            esc = self._advance()
            if esc == 'n': ch = '\n'
            elif esc == 't': ch = '\t'
            elif esc == 'r': ch = '\r'
            elif esc == '0': ch = '\0'
            elif esc == 'a': ch = '\a'
            elif esc == 'b': ch = '\b'
            elif esc == 'e': ch = '\x1b'
            elif esc == 'v': ch = '\v'
            elif esc == 'f': ch = '\f'
            elif esc == '\\': ch = '\\'
            elif esc == "'": ch = "'"
            elif esc == 'x':
                h1 = self._advance()
                h2 = self._advance()
                ch = chr(int(h1 + h2, 16))
            else:
                ch = esc
        if self._advance() != "'":
            raise SyntaxError(self._unterminated_msg('char', line_start, col_start))
        self._emit('CHAR', ord(ch), self.col - col_start)

    def _read_number(self, start_col):
        ch = self._peek()
        if ch == '0':
            self._advance()
            nxt = self._peek()
            if nxt in 'xX':
                self._advance()
                num = 0
                while self.pos < len(self.source):
                    d = self._peek()
                    if '0' <= d <= '9': num = num * 16 + (ord(d) - 48)
                    elif 'a' <= d <= 'f': num = num * 16 + (ord(d) - 87)
                    elif 'A' <= d <= 'F': num = num * 16 + (ord(d) - 55)
                    else: break
                    self._advance()
                suf = self._skip_int_suffix()
                self._emit('INT', num, self.col - start_col, suf)
                return
            elif nxt in 'bB':
                self._advance()
                num = 0
                while self._peek() in '01':
                    num = num * 2 + (ord(self._advance()) - 48)
                suf = self._skip_int_suffix()
                self._emit('INT', num, self.col - start_col, suf)
                return
            elif nxt in 'oO':
                self._advance()
                num = 0
                while '0' <= self._peek() <= '7':
                    num = num * 8 + (ord(self._advance()) - 48)
                suf = self._skip_int_suffix()
                self._emit('INT', num, self.col - start_col, suf)
                return
            else:
                # Just 0 or float like 0.0
                if self._peek() == '.':
                    is_float = True
                    num_str = ['0']
                    self._advance()
                    num_str.append('.')
                    while self.pos < len(self.source):
                        d = self._peek()
                        if '0' <= d <= '9':
                            num_str.append(self._advance())
                        elif d in 'eE':
                            num_str.append(self._advance())
                            if self._peek() in '+-':
                                num_str.append(self._advance())
                        else:
                            break
                    raw = ''.join(num_str)
                    self._emit('FLOAT', float(raw), self.col - start_col)
                else:
                    suf = self._skip_int_suffix()
                    self._emit('INT', 0, self.col - start_col, suf)
                return

        num_str = []
        is_float = False
        while self.pos < len(self.source):
            d = self._peek()
            if '0' <= d <= '9':
                num_str.append(self._advance())
            elif d == '.' and not is_float:
                nxt = self._peek(1)
                if nxt == '.':
                    break
                is_float = True
                num_str.append(self._advance())
            elif d in 'eE':
                is_float = True
                num_str.append(self._advance())
                if self._peek() in '+-':
                    num_str.append(self._advance())
            else:
                break
        raw = ''.join(num_str)
        if not raw:
            return
        # Consume integer suffixes: u, U, l, L, ll, LL, ul, UL, ull, ULL, lu, LU, llu, LLU
        suf = self._skip_int_suffix()
        if is_float:
            self._emit('FLOAT', float(raw), self.col - start_col)
        else:
            self._emit('INT', int(raw), self.col - start_col, suf)

    def _read_identifier(self, start_col):
        chars = []
        while self.pos < len(self.source):
            ch = self._peek()
            if ch.isalnum() or ch == '_':
                chars.append(self._advance())
            else:
                break
        word = ''.join(chars)
        length = self.col - start_col

        if word in TYPE_KEYWORDS:
            self._emit('TYPE', word, length)
        elif word in KEYWORDS:
            kind = word.upper()
            if word == 'self':
                self._emit('SELF', None, length)
            else:
                self._emit(kind, None, length)
        else:
            self._emit('IDENT', word, length)

    def _tokenize(self):
        while self.pos < len(self.source):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            ch = self._peek()
            start_col = self.col

            if ch == '"':
                self._read_string()
                continue
            if ch == "'":
                self._read_char()
                continue
            if ch.isdigit():
                self._read_number(start_col)
                continue
            if ch.isalpha() or ch == '_':
                self._read_identifier(start_col)
                continue

            self._advance()
            nxt = self._peek() if self.pos < len(self.source) else '\0'

            if ch == '@':
                rest = self.source[self.pos:]
                if nxt == 'u' and self.source[self.pos:self.pos+6] == 'unsafe':
                    for _ in range(6): self._advance()
                    self._emit('AT_UNSAFE', None, 7)
                else:
                    self._emit('AT', None, 1)

            elif ch == '!':
                if nxt == '<':
                    self._advance()
                    self._emit('BANG_LT', None, 2)
                elif nxt == 'r' and self.source[self.pos:self.pos+6] == 'return':
                    for _ in range(6): self._advance()
                    self._emit('NO_RETURN', None, 7)
                elif nxt == '=':
                    self._advance()
                    self._emit('NE', None, 2)
                else:
                    self._emit('BANG', None, 1)

            elif ch == '&':
                if nxt == '&':
                    self._advance()
                    self._emit('AND', None, 2)
                elif nxt == '=':
                    self._advance()
                    self._emit('AMPERSAND_EQ', None, 2)
                else:
                    self._emit('AMPERSAND', None, 1)

            elif ch == '|':
                if nxt == '|':
                    self._advance()
                    self._emit('OR', None, 2)
                elif nxt == '=':
                    self._advance()
                    self._emit('PIPE_EQ', None, 2)
                else:
                    self._emit('PIPE', None, 1)

            elif ch == '^':
                if nxt == '=':
                    self._advance()
                    self._emit('CARET_EQ', None, 2)
                else:
                    self._emit('CARET', None, 1)

            elif ch == '~':
                self._emit('TILDE', None, 1)

            elif ch == '+':
                if nxt == '+':
                    self._advance()
                    self._emit('INC', None, 2)
                elif nxt == '=':
                    self._advance()
                    self._emit('PLUS_EQ', None, 2)
                else:
                    self._emit('PLUS', None, 1)

            elif ch == '-':
                if nxt == '-':
                    self._advance()
                    self._emit('DEC', None, 2)
                elif nxt == '=':
                    self._advance()
                    self._emit('MINUS_EQ', None, 2)
                elif nxt == '>':
                    self._advance()
                    self._emit('ARROW', None, 2)
                else:
                    self._emit('MINUS', None, 1)

            elif ch == '*':
                if nxt == '=':
                    self._advance()
                    self._emit('STAR_EQ', None, 2)
                else:
                    self._emit('STAR', None, 1)

            elif ch == '/':
                if nxt == '=':
                    self._advance()
                    self._emit('SLASH_EQ', None, 2)
                else:
                    self._emit('SLASH', None, 1)

            elif ch == '%':
                if nxt == '=':
                    self._advance()
                    self._emit('PERCENT_EQ', None, 2)
                else:
                    self._emit('PERCENT', None, 1)

            elif ch == '<':
                if nxt == '<':
                    self._advance()
                    if self._peek() == '=':
                        self._advance()
                        self._emit('LTLT_EQ', None, 3)
                    else:
                        self._emit('LTLT', None, 2)
                elif nxt == '=':
                    self._advance()
                    self._emit('LE', None, 2)
                else:
                    self._emit('LT', None, 1)

            elif ch == '>':
                if nxt == '>':
                    self._advance()
                    if self._peek() == '=':
                        self._advance()
                        self._emit('GTGT_EQ', None, 3)
                    else:
                        self._emit('GTGT', None, 2)
                elif nxt == '=':
                    self._advance()
                    self._emit('GE', None, 2)
                else:
                    self._emit('GT', None, 1)

            elif ch == '=':
                if nxt == '=':
                    self._advance()
                    self._emit('EQ', None, 2)
                elif nxt == '>':
                    self._advance()
                    self._emit('FAT_ARROW', None, 2)
                else:
                    self._emit('ASSIGN', None, 1)

            elif ch == '(': self._emit('LPAREN', None, 1)
            elif ch == ')': self._emit('RPAREN', None, 1)
            elif ch == '[': self._emit('LBRACKET', None, 1)
            elif ch == ']': self._emit('RBRACKET', None, 1)
            elif ch == '{': self._emit('LBRACE', None, 1)
            elif ch == '}': self._emit('RBRACE', None, 1)
            elif ch == '?': self._emit('QUESTION', None, 1)
            elif ch == ';': self._emit('SEMICOLON', None, 1)
            elif ch == ':':
                if nxt == ':':
                    self._advance()
                    self._emit('COLON_COLON', None, 2)
                else:
                    self._emit('COLON', None, 1)
            elif ch == '.':
                if nxt == '.' and self._peek(1) == '.':
                    self._advance(); self._advance()
                    self._emit('ELLIPSIS', None, 3)
                else:
                    self._emit('DOT', None, 1)
            elif ch == ',': self._emit('COMMA', None, 1)
            elif ch == '#': self._emit('HASH', None, 1)

            else:
                self._error(f"Unexpected character: {ch!r}")

        self._emit('EOF', None, 0)
