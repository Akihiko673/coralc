#!/usr/bin/env python3
"""
Coral → C Compiler
Usage: python main.py [options] input.crl

Options:
  -o DIR        Output directory (default: out/)
  --flags K=V,K2=V2  Compile-time flags (e.g. --flags=ARCH=x86)
  --cc          C compiler command (default: gcc)
  --cflags      Additional C flags
  -S            Only generate C, do not compile
  -I DIR        Add directory to module search path
  -h, --help    Show this help
"""

import sys
import os
import subprocess
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tokenizer import Tokenizer
from parser import Parser, ParseError
from codegen import generate
from monomorphise import monomorphise
from coral_ast import (
    DeclModule, DeclImport, DeclFlag, DeclConditional,
    DeclStruct, DeclMethodBlock, DeclFunc, DeclEnum, DeclTrait, DeclExtern,
    DeclTypedef, DeclDistinct, DeclConst, DeclVar, DeclNamespace,
    StmtFlag, StmtBlock, StmtIf, StmtFor, StmtForIn, StmtWhile, StmtLoop,
    StmtSwitch, StmtDefer, StmtAsm,
)


MODULE_CACHE = {}  # module_path -> Program


def _candidate_dirs(base_dir):
    """Directory list: importing file's dir, then each ancestor, then CWD."""
    dirs = []
    if base_dir:
        d = os.path.abspath(base_dir)
        while True:
            dirs.append(d)
            parent = os.path.dirname(d)
            if parent == d or d == '/':
                break
            d = parent
    dirs.append(os.getcwd())
    return dirs


def resolve_module_path(module_path, search_paths, base_dir=None):
    """Resolve an import to a file path.
    Order: importing file's directory (then ancestors), CWD, then search
    paths. Each candidate is tried as-is and with '.crl' appended, so
    import("file") finds file.crl in the same folder.
    """
    dirs = _candidate_dirs(base_dir) + list(search_paths)
    for d in dirs:
        cand = os.path.join(d, module_path)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
        if os.path.isfile(cand + '.crl'):
            return os.path.abspath(cand + '.crl')
    return None


def resolve_module_dir(module_path, search_paths, base_dir=None):
    """Resolve an import prefix like 'std' (from 'std*') to a directory."""
    dirs = _candidate_dirs(base_dir) + list(search_paths)
    for d in dirs:
        cand = os.path.join(d, module_path)
        if os.path.isdir(cand):
            return os.path.abspath(cand)
        if os.path.isdir(cand.rstrip('/')):
            return os.path.abspath(cand.rstrip('/'))
    return None


def _flag_error(filename, decl, text):
    return (f'{filename}:{getattr(decl, "line", 0)}:'
            f'{getattr(decl, "col", 0)}: error: {text}')


def _select_flag_case(name, cases, default_case, flags):
    value = flags.get(name)
    for cname, body in cases:
        if value is not None and cname == value:
            return body, False
    if default_case is not None:
        return default_case, False
    return None, True


def _filter_decl(decl, flags, errors, context):
    if isinstance(decl, DeclFlag):
        body, missing = _select_flag_case(
            decl.name, decl.cases, decl.default_case, flags)
        if missing:
            errors.append(_flag_error(
                context, decl,
                f'flag "{decl.name}" has no value'
                f' (set it with --flags={decl.name}=...)'))
            return []
        return _filter_decl_list(body, flags, errors, context)
    if isinstance(decl, DeclStruct):
        decl.methods = _filter_decl_list(
            decl.methods, flags, errors, context)
    elif isinstance(decl, DeclMethodBlock):
        decl.methods = _filter_decl_list(
            decl.methods, flags, errors, context)
    elif isinstance(decl, DeclFunc):
        if decl.body is not None:
            decl.body = _filter_stmt(decl.body, flags, errors, context)
    return [decl]


def _filter_decl_list(decls, flags, errors, context):
    out = []
    for d in decls:
        out.extend(_filter_decl(d, flags, errors, context))
    return out


def _filter_stmt(stmt, flags, errors, context):
    if isinstance(stmt, StmtFlag):
        body, missing = _select_flag_case(
            stmt.name, stmt.cases, stmt.default_body, flags)
        if missing:
            errors.append(_flag_error(
                context, stmt,
                f'flag "{stmt.name}" has no value'
                f' (set it with --flags={stmt.name}=...)'))
            return StmtBlock([])
        return StmtBlock([_filter_stmt(s, flags, errors, context)
                          for s in body])
    if isinstance(stmt, StmtBlock):
        stmt.stmts = [_filter_stmt(s, flags, errors, context)
                      for s in stmt.stmts]
    elif isinstance(stmt, StmtIf):
        if stmt.then_block:
            stmt.then_block = _filter_stmt(stmt.then_block, flags, errors, context)
        if stmt.else_block:
            stmt.else_block = _filter_stmt(stmt.else_block, flags, errors, context)
    elif isinstance(stmt, StmtFor):
        stmt.body = _filter_stmt(stmt.body, flags, errors, context)
    elif isinstance(stmt, StmtForIn):
        stmt.body = _filter_stmt(stmt.body, flags, errors, context)
    elif isinstance(stmt, StmtWhile):
        stmt.body = _filter_stmt(stmt.body, flags, errors, context)
    elif isinstance(stmt, StmtLoop):
        stmt.body = _filter_stmt(stmt.body, flags, errors, context)
    elif isinstance(stmt, StmtSwitch):
        for c in stmt.cases:
            c.body = [_filter_stmt(s, flags, errors, context) for s in c.body]
        if stmt.default_body:
            stmt.default_body = [_filter_stmt(s, flags, errors, context)
                                 for s in stmt.default_body]
    elif isinstance(stmt, StmtDefer):
        stmt.body = _filter_stmt(stmt.body, flags, errors, context)
    elif isinstance(stmt, StmtAsm):
        pass
    return stmt


def apply_flags(program, flags, filename):
    """Select flag cases at compile time, flattening them into the tree."""
    if not flags:
        # Nothing selected; resolve flags without values so missing
        # flags error out consistently.
        flags = {}
    errors = []
    program.decls = _filter_decl_list(
        program.decls, flags, errors, filename)
    if errors:
        raise ValueError('\n'.join(errors))
    return program


def _attach_alias(decl, alias):
    """Attach the module alias ('' for root) to a decl and its children."""
    if 'alias' in getattr(type(decl), '__slots__', ()):
        decl.alias = alias
    if isinstance(decl, DeclConditional):
        for d in decl.decls:
            _attach_alias(d, alias)
        if decl.else_decls:
            for d in decl.else_decls:
                _attach_alias(d, alias)
    elif isinstance(decl, DeclFlag):
        for _, dcls in decl.cases:
            for d in dcls:
                _attach_alias(d, alias)
        if decl.default_case:
            for d in decl.default_case:
                _attach_alias(d, alias)
    elif isinstance(decl, DeclStruct):
        for m in decl.methods:
            m.alias = alias
    elif isinstance(decl, DeclMethodBlock):
        for m in decl.methods:
            m.alias = alias


def _parse_import_file(fpath, search_paths, alias, flags, _stack):
    key = os.path.abspath(fpath)
    if key in MODULE_CACHE:
        return MODULE_CACHE[key]
    try:
        with open(fpath) as f:
            imp_source = f.read()
    except OSError as e:
        print(f'  warning: could not import {fpath}: {e}')
        return None
    try:
        imp_prog = parse_with_imports(
            imp_source, fpath, search_paths,
            base_dir=os.path.dirname(fpath),
            alias=alias, flags=flags, _stack=_stack)
    except (ParseError, ValueError, SyntaxError) as e:
        print(f'  warning: could not import {fpath}: {e}')
        return None
    if imp_prog:
        MODULE_CACHE[key] = imp_prog
    return imp_prog


def parse_with_imports(source, filename, search_paths, base_dir=None,
                       alias=None, flags=None, _stack=None):
    """Parse a source file, resolving imports transitively.
    `alias` is the import-site alias ('' for the root file); it becomes
    the mangling prefix for all decls in this file.
    `flags` selects `flag (NAME)` blocks (compile-time configuration).
    """
    tok = Tokenizer(source, filename)
    parser = Parser(tok.tokens, filename, source=source)
    try:
        program = parser.parse()
    except ParseError as e:
        raise

    if not program:
        return None

    alias = alias or ''
    for decl in program.decls:
        _attach_alias(decl, alias)

    apply_flags(program, flags or {}, filename)

    if _stack is None:
        _stack = set()
    if filename in _stack:
        return program
    _stack.add(filename)

    # Process imports: mod <alias> = import("path")
    resolved_imports = []
    for decl in list(program.decls):
        if isinstance(decl, DeclImport):
            imp_alias = decl.names[0] if decl.names else alias
            path = decl.path
            if path.endswith('*'):
                # import("std*"): import all .crl files under that directory
                dirpath = resolve_module_dir(
                    path[:-1], search_paths, base_dir)
                if not dirpath:
                    print(f'  warning: module directory not found: {path}')
                    continue
                for root, _dirs, files in os.walk(dirpath):
                    for fn in sorted(files):
                        if not fn.endswith('.crl'):
                            continue
                        fpath = os.path.join(root, fn)
                        imp_prog = _parse_import_file(
                            fpath, search_paths, imp_alias, flags, _stack)
                        if imp_prog:
                            resolved_imports.append(imp_prog)
                continue
            if path in MODULE_CACHE:
                resolved_imports.append(MODULE_CACHE[path])
                continue
            fpath = resolve_module_path(path, search_paths, base_dir)
            if not fpath:
                print(f'  warning: module not found: {path}')
                continue
            imp_prog = _parse_import_file(
                fpath, search_paths, imp_alias, flags, _stack)
            if imp_prog:
                resolved_imports.append(imp_prog)

    # Merge imported declarations (keep import/module markers so codegen
    # knows every module alias in scope). The same file may be reachable
    # through several import chains; dedupe by object identity so each
    # decl is merged exactly once.
    seen_ids = set()
    for imp_prog in resolved_imports:
        for d in imp_prog.decls:
            if id(d) in seen_ids:
                continue
            seen_ids.add(id(d))
            program.decls.append(d)

    return program


def compile_file(input_path, output_dir, flags=None, compile_c=True,
                 cc='gcc', cflags=None, keep_c=False, search_paths=None):
    filename = os.path.basename(input_path)
    name_no_ext = os.path.splitext(filename)[0]
    base_dir = os.path.dirname(os.path.abspath(input_path))

    with open(input_path, 'r') as f:
        source = f.read()

    print(f'  parsing  {input_path}...')
    try:
        program = parse_with_imports(
            source, input_path,
            search_paths or ['std'],
            base_dir=base_dir,
            flags=flags or {})
    except (ParseError, ValueError, SyntaxError) as e:
        print(f'  error: {e}')
        return False

    if not program:
        print(f'  error: parse returned empty program')
        return False

    print(f'  monomorphising...')
    try:
        monomorphise(program)
    except Exception as e:
        print(f'  error during monomorphisation: {e}')
        if 'generic' in str(e).lower() or 'instantiation' in str(e).lower():
            print('  hint:    check the generic arguments at every call site — '
                  'types like Foo<T> need a matching argument for each '
                  'parameter (<T>), and value parameters expect a number, '
                  'not a type')
        return False

    print(f'  codegen  {input_path}...')
    h_content, c_content = generate(program, name_no_ext, output_dir)

    os.makedirs(output_dir, exist_ok=True)
    h_path = os.path.join(output_dir, f'{name_no_ext}.h')
    c_path = os.path.join(output_dir, f'{name_no_ext}.c')

    with open(h_path, 'w') as f:
        f.write(h_content)
    with open(c_path, 'w') as f:
        f.write(c_content)

    print(f'  wrote    {h_path}')
    print(f'  wrote    {c_path}')

    if compile_c:
        output_bin = os.path.join(output_dir, name_no_ext)
        cf = cflags or []
        cmd = [cc] + cf + ['-o', output_bin, c_path, '-lm']
        print(f'  compile  {" ".join(cmd)}')
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  error    compilation failed:')
            print(result.stderr)
            return False
        print(f'  wrote    {output_bin}')
        if not keep_c:
            os.remove(c_path)
            os.remove(h_path)

    return True


def main():
    parser = argparse.ArgumentParser(description='Coral → C Compiler')
    parser.add_argument('input', nargs='+', help='Input .crl files')
    parser.add_argument('-o', default='out', help='Output directory')
    parser.add_argument('--flags', default='',
                        help='Compile-time flags as comma-separated '
                             'KEY=VALUE pairs, e.g. --flags=ARCH=x86,OS=linux')
    parser.add_argument('--cc', default='gcc', help='C compiler')
    parser.add_argument('--cflags', default='-Wall -Wextra -O2 -g -ffreestanding', help='C flags')
    parser.add_argument('-S', action='store_true', help='Only generate C (no compile)')
    parser.add_argument('--keep-c', action='store_true', help='Keep generated C files')
    parser.add_argument('-I', action='append', default=[], help='Add include search path')

    args = parser.parse_args()

    flags = {}
    if args.flags:
        for pair in args.flags.split(','):
            pair = pair.strip()
            if not pair:
                continue
            if '=' in pair:
                k, v = pair.split('=', 1)
                flags[k.strip()] = v.strip()
            else:
                flags[pair] = '1'

    # Build search paths
    search_paths = list(args.I) + ['std']

    # Add std subdirectories
    std_base = 'std'
    if os.path.isdir(std_base):
        for root, dirs, _ in os.walk(std_base):
            for d in dirs:
                sp = os.path.join(root, d)
                if sp not in search_paths:
                    search_paths.append(sp)

    print(f'Coral → C Compiler')
    print(f'flags: {flags}')
    print(f'search paths: {search_paths}')
    print()

    success = True
    for input_path in args.input:
        if not os.path.exists(input_path):
            print(f'error: file not found: {input_path}')
            success = False
            continue

        ok = compile_file(
            input_path, args.o,
            flags=flags,
            compile_c=not args.S,
            cc=args.cc,
            cflags=args.cflags.split() if args.cflags else None,
            keep_c=args.keep_c,
            search_paths=search_paths,
        )
        if not ok:
            success = False

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
