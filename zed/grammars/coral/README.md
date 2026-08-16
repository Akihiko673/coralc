# tree-sitter-coral

Tree-sitter grammar for the Coral programming language.

This repository is a vendored copy of the grammar sources generated from
`grammar.js` (generated with `tree-sitter generate`). Zed clones this
repository and compiles `src/parser.c` to WebAssembly at extension install
time, so the generated sources are checked in.

## Layout

- `grammar.js` – the grammar definition
- `src/parser.c` – generated parser (do not edit by hand)
- `src/tree_sitter/` – tree-sitter runtime headers
- `node-types.json` – generated node type list

## Regenerating

```sh
tree-sitter generate
```

## Testing

```sh
tree-sitter test
```
