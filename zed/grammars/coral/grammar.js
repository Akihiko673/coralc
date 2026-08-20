module.exports = grammar({
  name: 'coral',

  extras: $ => [
    $.comment,
    /[\s\p{Zs}\uFEFF\u00A0]/
  ],

  conflicts: $ => [
    [$.named_type, $.primary],
    [$.flag_case],
    [$.struct_member, $.function_declaration],
    [$.relational_lt, $.relational_gt],
    [$._generic_type_args, $.generic_instantiation],
    [$.block, $.primary],
    [$.primary],
    [$.struct_declaration],
    [$.enum_declaration],
    [$.named_type],
  ],

  word: $ => $.identifier,

  rules: {
    source_file: $ => repeat($.declaration),

    comment: $ => token(choice(
      seq('//', /.*/),
      seq('/*', /[^*]*\*+([^/*][^*]*\*+)*/, '/')
    )),

    _literal: $ => choice(
      $.integer_literal,
      $.float_literal,
      $.string_literal,
      $.char_literal,
      $.bool_literal,
      $.null_literal,
    ),

    integer_literal: $ => token(choice(
      /[0-9][0-9_]*[uUlLbBoOxX]*/,
      /0[xX][0-9a-fA-F][0-9a-fA-F_]*[uUlL]*/,
      /0[oO][0-7][0-7_]*[uUlL]*/,
      /0[bB][01][01_]*[uUlL]*/,
    )),

    float_literal: $ => token(choice(
      /[0-9][0-9_]*\.[0-9][0-9_]*([eE][+-]?[0-9]+)?/,
      /[0-9][0-9_]*[eE][+-]?[0-9]+/,
    )),

    string_literal: $ => choice(
      $.single_line_string,
      $.multi_line_string,
    ),

    single_line_string: $ => token(seq(
      '"',
      repeat(choice(/[^"\\\n]/, /\\(.|\n)/)),
      '"'
    )),

    multi_line_string: $ => token(seq(
      '"""',
      repeat(choice(/[^\\]/, /\\(.|\n)/)),
      '"""'
    )),

    char_literal: $ => token(seq(
      '\'',
      choice(/[^'\\\n]/, /\\(.|\n)/),
      '\''
    )),

    bool_literal: $ => choice('true', 'false'),
    null_literal: $ => 'null',

    identifier: $ => /[a-zA-Z_][a-zA-Z0-9_]*/,

    _type: $ => choice(
      $.primitive_type,
      $.named_type,
      $.pointer_type,
      $.generic_instantiation,
      $.function_pointer_type,
    ),

    function_pointer_type: $ => seq(
      $._type,
      '(',
      optional(seq($.function_pointer_param, repeat(seq(',', $.function_pointer_param)), optional(','))),
      ')',
    ),

    function_pointer_param: $ => seq(
      optional('const'),
      $._type,
      optional(field('name', $.identifier)),
    ),

    primitive_type: $ => choice(
      'i8', 'i16', 'i32', 'i64',
      'u8', 'u16', 'u32', 'u64',
      'f32', 'f64',
      'bool', 'char', 'void',
      'isize', 'usize',
    ),

    named_type: $ => seq(
      $.identifier,
      repeat(seq('.', $.identifier)),
      optional(seq('::', $.identifier)),
    ),

    pointer_type: $ => prec(1, seq(
      $._type,
      repeat1('*'),
    )),

    generic_instantiation: $ => prec(1, seq(
      $.named_type,
      '<',
      $._generic_type_args,
      '>',
    )),

    type_parameter: $ => seq(choice(seq($._type, field('name', $.identifier)), $.identifier), optional('...')),
    type_parameters: $ => seq(
      '<',
      seq(
        $.type_parameter,
        repeat(seq(',', $.type_parameter)),
        optional(',')
      ),
      '>',
    ),

    declaration: $ => choice(
      $.mod_declaration,
      $.struct_declaration,
      $.enum_declaration,
      $.function_declaration,
      $.const_declaration,
      $.var_declaration,
      $.typedef_declaration,
      $.distinct_declaration,
      $.extern_declaration,
      $.attribute_declaration,
      $.flag_block,
      $.asm_block,
      $.impl_block,
      $._init_declaration,
      $.simple_var_declaration,
      $.trait_declaration,
    ),

    mod_declaration: $ => seq(
      'mod', $.identifier, '=', 'import', '(', $.string_literal, ')', ';',
    ),

    attribute_declaration: $ => seq(
      '@', '[',
      optional(seq($.identifier, repeat(seq(',', $.identifier)))),
      ']',
    ),

    impl_block: $ => seq($._type, '{', repeat($.function_declaration), '}'),

    trait_declaration: $ => seq(
      optional($._visibility), 'trait',
      field('name', $.identifier),
      optional($.type_parameters),
      '{', repeat($.function_declaration), '}', optional(';'),
    ),

    _visibility: $ => choice('pub', 'export'),

    _init_declaration: $ => seq(
      optional($._visibility), optional('static'), $._type, field('name', $.identifier),
      repeat(seq('[', optional($.expression), ']')),
      '=', $.expression, ';',
    ),

    _struct_body_item: $ => choice(
      $.struct_member,
      $.function_declaration,
    ),

    struct_declaration: $ => seq(
      optional($._visibility), 'struct',
      field('name', $.identifier),
      optional($.type_parameters),
      '{', repeat($._struct_body_item), '}', optional(';'),
    ),

    struct_member: $ => choice(
      seq($._type, field('name', $.identifier), repeat(seq('[', $.expression, ']')), ';'),
      seq('const', $._type, field('name', $.identifier), ';'),
    ),

    enum_declaration: $ => seq(
      optional($._visibility), 'enum',
      field('name', $.identifier),
      '{',
      seq($.enum_variant, repeat(seq(',', $.enum_variant)), optional(',')),
      '}', optional(';'),
    ),

    enum_variant: $ => seq(
      field('name', $.identifier),
      optional(seq('(', $._type, repeat(seq(',', $._type)), optional(','), ')')),
      optional(seq('=', $.expression)),
    ),

    function_declaration: $ => seq(
      optional($._visibility), optional('static'), optional('inline'),
      seq(optional('const'), field('return_type', $._type), field('name', $.identifier)),
      optional($.type_parameters),
      '(',
      optional(seq($.parameter, repeat(seq(',', $.parameter)), optional(','), optional(seq(',', '...')))),
      ')',
      choice($.block, ';'),
    ),

    parameter: $ => seq(
      optional('const'),
      choice(seq($._type, '...'), $._type),
      optional(field('name', $.identifier))
    ),

    const_declaration: $ => seq(
      optional($._visibility), 'const',
      optional($._type), field('name', $.identifier),
      optional(seq('[', optional($.expression), ']')),
      optional(seq('=', $.expression)), ';',
    ),

    var_declaration: $ => seq(
      optional($._visibility), 'var',
      field('name', $.identifier),
      '=', $.expression, ';',
    ),

    typedef_declaration: $ => seq(
      optional($._visibility), 'typedef',
      field('name', $.identifier), '=', $._type, ';',
    ),

    distinct_declaration: $ => seq(
      optional($._visibility), 'distinct',
      field('name', $.identifier), '=', $._type, ';',
    ),

    extern_declaration: $ => seq(
      optional($._visibility), 'extern',
      optional(seq('(', $.string_literal, ')')),
      choice($._type), field('name', $.identifier),
      choice(
        seq('(', optional(seq($.parameter, repeat(seq(',', $.parameter)), optional(','), optional(seq(',', '...')))), ')', optional(seq('!', 'return')), ';'),
        ';',
      ),
    ),

    _if: $ => prec.right(seq(
      'if', '(', $.expression, ')', $.statement,
      optional(seq('else', $.statement)),
    )),

    statement: $ => choice(
      $.block,
      $._if,
      $.while_statement,
      $.for_statement,
      $.loop_statement,
      $.switch_statement,
      $.break_statement,
      $.continue_statement,
      $.return_statement,
      $.defer_statement,
      $.comptime_block,
      $.flag_block,
      $.asm_block,
      $._declaration_statement,
      $.expression_statement,
      ';',
    ),

    _declaration_statement: $ => choice(
      $.const_declaration,
      $.var_declaration,
      $.struct_declaration,
      $.simple_var_declaration,
      $._init_declaration,
    ),

    simple_var_declaration: $ => seq(
      optional($._visibility), optional('static'), $._type, field('name', $.identifier),
      repeat(seq(',', field('name', $.identifier))),
      repeat(seq('[', optional($.expression), ']')), ';',
    ),

    block: $ => seq('{', repeat($.statement), '}'),

    while_statement: $ => seq('while', '(', $.expression, ')', $.statement),

    for_statement: $ => choice(
      seq(
        'for', '(',
        optional(choice(
          seq('var', field('name', $.identifier), optional(seq('=', $.expression))),
          seq($._type, field('name', $.identifier), optional(seq('=', $.expression))),
          $.expression,
        )),
        ';', optional($.expression), ';', optional($.expression),
        ')', $.statement,
      ),
      seq('for', '(', 'var', $.identifier, ':', $.expression, ')', $.statement),
    ),

    loop_statement: $ => seq('loop', $.statement),

    switch_statement: $ => choice(
      seq('switch', $.expression, '{',
        repeat($.switch_case), optional($.switch_default_old), '}'),
      seq('switch', $.expression, '{',
        repeat($.switch_arm), '}'),
    ),

    switch_case: $ => seq('case', $.expression, ':', repeat($.statement)),
    switch_default_old: $ => seq('default', ':', repeat($.statement)),
    switch_arm: $ => seq($.expression, '=>', $.expression, optional(',')),

    break_statement: $ => seq('break', ';'),
    continue_statement: $ => seq('continue', ';'),

    return_statement: $ => seq('return', optional($.expression), ';'),
    defer_statement: $ => seq('defer', $.statement),

    expression_statement: $ => seq($.expression, ';'),

    comptime_block: $ => seq('comptime', $.block),

    flag_block: $ => seq(
      'flag', '(', $.identifier, ')', '{',
      repeat($.flag_case), optional($.flag_default), '}',
    ),

    flag_case: $ => seq($.identifier, ':', repeat(choice($.statement, $.function_declaration, $.extern_declaration))),
    flag_default: $ => seq('default', ':', repeat(choice($.statement, $.function_declaration, $.extern_declaration))),

    asm_block: $ => seq('asm', optional('volatile'), token(seq('{', /[^}]*/, '}'))),

    expression: $ => seq(
      $.ternary,
      optional(seq(choice('=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>='), $.expression)),
    ),

    ternary: $ => choice(
      prec.right(seq($.ternary, '?', $.expression, ':', $.ternary)),
      $.logical_or,
    ),

    logical_or: $ => choice(
      prec.left(1, seq($.logical_or, '||', $.logical_and)),
      prec.left(1, $.logical_and),
    ),

    logical_and: $ => choice(
      prec.left(2, seq($.logical_and, '&&', $.bitwise_or)),
      prec.left(2, $.bitwise_or),
    ),

    bitwise_or: $ => choice(
      prec.left(3, seq($.bitwise_or, '|', $.bitwise_xor)),
      prec.left(3, $.bitwise_xor),
    ),

    bitwise_xor: $ => choice(
      prec.left(4, seq($.bitwise_xor, '^', $.bitwise_and)),
      prec.left(4, $.bitwise_and),
    ),

    bitwise_and: $ => choice(
      prec.left(5, seq($.bitwise_and, '&', $.equality)),
      prec.left(5, $.equality),
    ),

    equality: $ => choice(
      prec.left(6, seq($.equality, choice('==', '!='), $.relational)),
      prec.left(6, $.relational),
    ),

    relational: $ => choice(
      $.relational_lt,
      $.relational_gt,
    ),

    relational_lt: $ => choice(
      prec.left(7, seq($.relational_lt, choice('<', '<='), $.shift)),
      prec.left(7, $.shift),
    ),

    relational_gt: $ => choice(
      prec.left(7, seq($.relational_gt, choice('>', '>='), $.shift)),
      prec.left(7, $.shift),
    ),

    shift: $ => choice(
      prec.left(8, seq($.shift, choice('<<', '>>'), $.addition)),
      prec.left(8, $.addition),
    ),

    addition: $ => choice(
      prec.left(9, seq($.addition, choice('+', '-'), $.multiplication)),
      prec.left(9, $.multiplication),
    ),

    multiplication: $ => choice(
      prec.left(10, seq($.multiplication, choice('*', '/', '%'), $.unary)),
      prec.left(10, $.unary),
    ),

    unary: $ => prec(2, choice(
      seq(choice('+', '-', '!', '~', '*', '&'), $.unary),
      seq('++', $.unary),
      seq('--', $.unary),
      $.postfix,
    )),

    _generic_type_args: $ => seq(
      choice(seq('const', $._type), $._type, $.integer_literal),
      repeat(seq(',', choice(seq('const', $._type), $._type, $.integer_literal))),
      optional(','),
    ),

    postfix: $ => choice(
      seq($.postfix, '++'),
      seq($.postfix, '--'),
      seq($.postfix, '.', $.identifier),
      seq($.postfix, '->', $.identifier),
      seq($.postfix, '[', $.expression, ']'),
      seq($.postfix, '(', optional(seq($.expression, repeat(seq(',', $.expression)), optional(','))), ')'),
      seq($.postfix, '::', $.identifier),
      $.primary,
    ),

    primary: $ => choice(
      $._literal,
      $.identifier,
      seq($.named_type, '::', $.identifier),
      seq('(', $.expression, ')'),
      seq('sizeof', '(', $._type, ')'),
      seq('(', $._type, ')', optional($.unary)),
      seq('(', 'const', $._type, ')', optional($.unary)),
      seq('(', 'volatile', $._type, ')', optional($.unary)),
      seq('(', $._type, ')',
        '{', optional(seq(choice($.expression, $.struct_field), repeat(seq(',', choice($.expression, $.struct_field))), optional(','))), '}'),
      seq('{', optional(seq(choice($.expression, $.struct_field), repeat(seq(',', choice($.expression, $.struct_field))), optional(','))), '}'),
      seq($.identifier, '!', '(', optional(seq($.expression, repeat(seq(',', $.expression)), optional(','))), ')'),
      prec(2, seq($.named_type, '<', $._generic_type_args, '>', '::', $.identifier)),
      prec(2, seq($.named_type, '::', $.identifier, '<', $._generic_type_args, '>',
        optional(seq('(', optional(seq($.expression, repeat(seq(',', $.expression)), optional(','))), ')')),
        optional(seq('{', optional(seq($.struct_field, repeat(seq(',', $.struct_field)), optional(','))), '}')))),
      prec(2, seq($.named_type, '<', $._generic_type_args, '>',
        '(', optional(seq($.expression, repeat(seq(',', $.expression)), optional(','))), ')')),
      prec(2, seq($.named_type, '<', $._generic_type_args, '>',
        '{', optional(seq($.struct_field, repeat(seq(',', $.struct_field)), optional(','))), '}')),
    ),

    struct_field: $ => seq('.', $.identifier, optional(seq('=', $.expression))),
  }
});