/* Coral C header (declarations only) for: src/lexer.crl */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef struct LexResult {
    LexTok* toks;
    uint32_t n;
    LexErr* errs;
    uint32_t nerrs;
} LexResult;
typedef struct Lexer {
    uint8_t const* src;
    uint32_t len;
    uint32_t pos;
    uint32_t row;
    uint32_t col;
    LexTok* toks;
    uint32_t ntoks;
    uint32_t cap;
    LexErr* errs;
    uint32_t nerrs;
    uint32_t ecap;
} Lexer;
