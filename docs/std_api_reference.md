# Coral Standard Library — Complete API Reference

> This document catalogs every `pub` export in `lib/std/`, organized by module.
> Struct fields are listed; methods are listed with their parameters and return types.
> Free functions include parameter types and return types.

---

## 1. `std/core/char` — Character Classification

```coral
pub bool isDigit(char c)          // '0'-'9'
pub bool isAlpha(char c)          // 'a'-'z', 'A'-'Z'
pub bool isAlnum(char c)          // isDigit || isAlpha
pub bool isLower(char c)          // 'a'-'z'
pub bool isUpper(char c)          // 'A'-'Z'
pub char toLower(char c)          // uppercase → lowercase
pub char toUpper(char c)          // lowercase → uppercase
pub bool isSpace(char c)          // ' ', '\t', '\n', '\r', '\f', '\v'
pub bool isPrint(char c)          // 0x20-0x7E
pub bool isControl(char c)        // <0x20 or 0x7F
pub bool isHexDigit(char c)       // '0'-'9','a'-'f','A'-'F'
pub u8 digitValue(char c)         // char → numeric value (0-15)
```

---

## 2. `std/core/duration` — Time Durations

### `struct Duration`
**Fields:** `i64 sec`, `i64 nsec`

**Static methods:**
- `static Duration fromSecs(i64 s)` — Create from whole seconds
- `static Duration fromMillis(i64 ms)` — Create from milliseconds
- `static Duration fromMicros(i64 us)` — Create from microseconds
- `static Duration fromNanos(i64 ns)` — Create from nanoseconds
- `static Duration fromF64(f64 seconds)` — Create from fractional seconds

**Instance methods:**
- `i64 asSecs()` → whole seconds
- `i64 asMillis()` → total milliseconds
- `i64 asMicros()` → total microseconds
- `i64 asNanos()` → total nanoseconds
- `f64 asF64()` → fractional seconds
- `bool isZero()` → true if 0 duration
- `Duration add(Duration other)` → sum
- `Duration sub(Duration other)` → difference
- `Duration mul(i64 factor)` → multiply
- `Duration div(i64 factor)` → divide (assert != 0)
- `i32 compare(Duration other)` → -1/0/1
- `bool eq(Duration other)` / `lt` / `gt` / `le` / `ge`
- `time.Timespec toTimespec()` → convert for syscall
- `void sleep()` → block for this duration

**Free functions:**
- `pub Duration seconds(i64 s)` — sugar for `fromSecs`
- `pub Duration millis(i64 ms)` — sugar for `fromMillis`
- `pub Duration micros(i64 us)` — sugar for `fromMicros`
- `pub Duration nanos(i64 ns)` — sugar for `fromNanos`

---

## 3. `std/core/limits` — Numeric Limits

```coral
pub const INT64_MIN = -9223372036854775808
pub const INT64_MAX = 9223372036854775807
pub const INT32_MIN = -2147483648
pub const INT32_MAX = 2147483647
pub const INT16_MIN = -32768
pub const INT16_MAX = 32767
pub const INT8_MIN  = -128
pub const INT8_MAX  = 127
pub const U64_MAX = 18446744073709551615u
pub const U32_MAX = 4294967295u
pub const U16_MAX = 65535u
pub const U8_MAX = 255u
pub const F64_MAX = 1.7976931348623157e+308
pub const F64_MIN = 2.2250738585072014e-308
pub const F32_MAX = 3.40282347e+38
pub const F32_MIN = 1.17549435e-38
```

---

## 4. `std/core/time` — System Time

### `struct Timespec` — `i64 sec`, `i64 nsec`
### `struct Timeval` — `i64 sec`, `i64 usec`

**Free functions:**
- `pub Timespec nowMonotonic()` — CLOCK_MONOTONIC
- `pub Timespec nowRealtime()` — CLOCK_REALTIME
- `pub Timeval nowTimeval()` — gettimeofday
- `pub u64 unixSeconds()` — time(null)
- `pub Timespec addTimespec(Timespec a, Timespec b)`
- `pub Timespec subTimespec(Timespec a, Timespec b)`
- `pub f64 timespecToF64(Timespec ts)`
- `pub f64 timevalToF64(Timeval tv)`
- `pub void sleepMs(u64 ms)` — millisecond sleep

---

## 5. `std/data/option` — Optional Values

### `struct option<T>` — `bool some`, `T value`
- `option<T> some(T value)` — wrap a value
- `option<T> none()` — empty option
- `bool isSome()` — true if has value
- `bool isNone()` — true if empty
- `T unwrap()` — assert + return value
- `T unwrapOr(T defaultVal)` — value or default
- `T* ptr()` — pointer to value or null
- `const T* constPtr()` — const pointer or null
- `void map(T(T) fn)` — apply fn if some
- `void andThen(option<T>(T) fn)` — chain
- `void orElse(option<T>() fn)` — fallback
- `T take()` — extract value, set to none

---

## 6. `std/data/result` — Result Type

### `struct Result<T, E>` — `bool ok`, `T value`, `E error`
- `Result<T,E> ok(T value)` — success
- `Result<T,E> err(E error)` — failure
- `bool isOk()` — true if success
- `bool isErr()` — true if error
- `T unwrap()` — assert ok + return value
- `T unwrapOr(T defaultVal)` — value or default
- `E unwrapErr()` — assert err + return error
- `T* okPtr()` — pointer to value or null
- `E* errPtr()` — pointer to error or null
- `void mapOk(T(T) fn)` — transform value if ok
- `void mapErr(E(E) fn)` — transform error if err
- `void andThen(Result<T,E>(T) fn)` — chain on ok
- `void orElse(Result<T,E>(E) fn)` — chain on err

---

## 7. `std/collections/vec` — Dynamic Array

### `struct vec<T>` — `T* data`, `u64 len`, `u64 cap`
- `static vec<T> new()` — empty vec (null data, cap=0)
- `static vec<T> withCap(u64 capacity)` — pre-allocate
- `void reserve(u64 newCap)` — ensure capacity
- `void push(T val)` — append element
- `T pop()` — remove and return last element
- `u64 count()` — number of elements
- `T* atPtr(u64 i)` — mutable pointer to element
- `const T* atConst(u64 i)` — const pointer
- `T at(u64 i)` — copy of element
- `T* ptr()` — raw mutable pointer to data
- `const T* constPtr()` — raw const pointer
- `bool isEmpty()` — true if len == 0
- `void set(u64 i, T val)` — overwrite element
- `T front()` — first element (assert non-empty)
- `T back()` — last element (assert non-empty)
- `void insert(u64 i, T val)` — insert at index
- `void removeAt(u64 i)` — remove at index, shift
- `void removeRange(u64 start, u64 end)` — remove range
- `bool contains(T val)` — linear search
- `void fill(T val)` — fill all elements
- `void reserveExact(u64 newCap)` — allocate exact
- `void shrinkToFit()` — realloc to exact size
- `void clear()` — len = 0
- `void reverse()` — reverse in place
- `bool isSortedBy(bool(T, T) less)` — check sorted
- `void sortBy(bool(T, T) less)` — quicksort
- `i64 binarySearchBy(T key, i32(T, T) cmp)` — binary search
- `void dispose()` — free memory

---

## 8. `std/collections/arr` — Fixed-Size Array

### `struct arr<T, N>` — `T data[N]`
- `T* ptr()` — mutable pointer
- `const T* constPtr()` — const pointer
- `u64 count()` → N
- `bool isEmpty()` → N == 0
- `T at(u64 i)` — element copy
- `void set(u64 i, T val)` — set element
- `T* atPtr(u64 i)` — mutable pointer
- `T front()` — first element
- `T back()` — last element
- `void fill(T val)` — fill all
- `void copyTo(T* dst)` — copy out
- `void copyFrom(const T* src)` — copy in

---

## 9. `std/collections/hashmap` — Open-Addressing Hash Map

### `struct HashMapEntry<K, V>` — `K key`, `V value`, `bool occupied`
### `struct hashmap<K, V>` — `entries`, `cap`, `len`, `hashFn`, `eqFn`
- `static hashmap<K, V> new(u64(K) hf, bool(K, K) ef)` — create with hash+eq
- `void dispose()` — free entries
- `u64 count()` — number of entries
- `void insert(K key, V value)` — insert/replace
- `option<V> get(K key)` — lookup, return option
- `bool contains(K key)` — key exists
- `V* getPtr(K key)` — mutable pointer or null
- `void remove(K key)` — delete entry
- `option<HashMapEntry<K, V>> removeEntry(K key)` — delete and return removed entry
- `void clear()` — mark all empty
- `void each(void(K, V) fn)` — iterate entries
- `void eachEntry(void(HashMapEntry<K, V>*) fn)` — iterate raw entries

---

## 10. `std/collections/map` — AVL Tree (Ordered Map)

### `struct MapEntry<K, V>` — key, value, height, left, right
### `struct map<K, V>` — `root`, `len`, `cmpFn`
- `static map<K, V> new(i32(K, K) cmp)` — create with comparator
- `void dispose()` — free tree
- `u64 count()` — number of entries
- `bool isEmpty()`
- `void insert(K key, V value)` — insert/replace
- `option<V> get(K key)` — lookup
- `V* getPtr(K key)` — pointer or null
- `bool contains(K key)`
- `void remove(K key)`
- `void clear()`
- `void each(void(K, V) fn)` — in-order traversal

---

## 11. `std/collections/set` — Hash Set

### `struct set<T>` — wraps `hashmap<T, bool>`
- `static set<T> new(u64(T) hf, bool(T, T) ef)`
- `void dispose()`
- `u64 count()`
- `bool isEmpty()`
- `void insert(T val)`
- `bool contains(T val)`
- `void remove(T val)`
- `void clear()`
- `vec<T> toVec()` — collect keys
- `void each(void(T) fn)` — iterate
- `set<T> union(const set<T>* other)` — set union
- `set<T> intersection(const set<T>* other)` — intersection
- `set<T> difference(const set<T>* other)` — difference
- `bool isSubset(const set<T>* other)`
- `bool isSuperset(const set<T>* other)`

---

## 12. `std/collections/linkedlist` — Doubly-Linked List

### `struct ListNode<T>` — `T value`, `prev*`, `next*`
### `struct linkedlist<T>` — `head`, `tail`, `len`
- `static linkedlist<T> new()`
- `void dispose()` — free all nodes
- `u64 count()`
- `bool isEmpty()`
- `void pushFront(T val)`
- `void pushBack(T val)`
- `T popFront()`
- `T popBack()`
- `T front()`
- `T back()`
- `void insertAfter(ListNode<T>* node, T val)`
- `void remove(ListNode<T>* node)`
- `void each(void(T) fn)`

---

## 13. `std/collections/deque` — Ring-Buffer Deque

### `struct deque<T>` — `data`, `head`, `tail`, `cap`, `mask`
- `static deque<T> new()` — initial cap=8
- `void dispose()`
- `u64 count()`
- `bool isEmpty()`
- `u64 capacity()`
- `void pushFront(T val)`
- `void pushBack(T val)`
- `T popFront()`
- `T popBack()`
- `T front()`
- `T back()`
- `T at(u64 i)`
- `void set(u64 i, T val)`
- `void clear()`

---

## 14. `std/collections/queue` — FIFO Queue (wraps deque)

### `struct queue<T>` — wraps `deque<T>`
- `static queue<T> new()`
- `void dispose()`
- `u64 count()`
- `bool isEmpty()`
- `void enqueue(T val)`
- `T dequeue()`
- `T peek()`
- `void clear()`

---

## 15. `std/collections/priorityqueue` — Binary Heap

### `struct priorityqueue<T>` — `data`, `len`, `cap`, `less`
- `static priorityqueue<T> new(bool(T, T) cmp)` — comparator
- `void dispose()`
- `u64 count()`
- `bool isEmpty()`
- `void push(T val)`
- `T pop()` — extract min (by less)
- `T peek()` — min element
- `void clear()`

---

## 16. `std/collections/ringbuf` — Fixed-Capacity Ring Buffer

### `struct ringbuf<T>` — `data`, `cap`, `head`, `tail`, `full`
- `static ringbuf<T> new(u64 capacity)`
- `void dispose()`
- `u64 count()`
- `bool isEmpty()`
- `bool isFull()`
- `u64 capacity()`
- `void push(T val)` — overwrites oldest if full
- `T pop()`
- `T front()`
- `T back()`
- `T at(u64 i)`
- `void clear()`

---

## 17. `std/collections/bitset` — Resizable Bit Set

### `struct bitset` — `u64* words`, `numBits`, `numWords`
- `static bitset new(u64 numBits)`
- `void dispose()`
- `u64 count()` — numBits
- `u64 wordCount()` — numWords
- `void set(u64 bit)`
- `void clear(u64 bit)`
- `void toggle(u64 bit)`
- `bool test(u64 bit)`
- `void setAll()`
- `void clearAll()`
- `u64 countOnes()` — popcount
- `u64 countZeros()`
- `bool any()`
- `bool none()`
- `bool all()`
- `void and(bitset* other)` — bitwise AND
- `void or(bitset* other)` — bitwise OR
- `void xor(bitset* other)` — bitwise XOR
- `void not()` — bitwise NOT

---

## 18. `std/collections/trie` — Byte Trie (string key map)

### `struct TrieNode` — `children[256]`, `isEnd`
### `struct trie` — `root`, `count`
- `static trie new()`
- `void dispose()`
- `u64 size()`
- `bool isEmpty()`
- `void insert(strView key)`
- `bool contains(strView key)`
- `bool startsWith(strView prefix)`
- `bool remove(strView key)`
- `void each(void(strView) fn)` — iterate keys

---

## 19. `std/collections/tree` — N-ary Tree

### `struct TreeNode<T>` — `T value`, `vec<TreeNode<T>*> children`
### `struct tree<T>` — `TreeNode<T>* root`
- `static tree<T> new()`
- `void dispose()`
- `bool isEmpty()`
- `TreeNode<T>* setRoot(T val)`
- `TreeNode<T>* addChild(TreeNode<T>* parent, T val)`
- `u64 childCount(TreeNode<T>* node)`
- `TreeNode<T>* childAt(TreeNode<T>* node, u64 idx)`
- `void removeChild(TreeNode<T>* parent, u64 idx)`
- `void preOrder(void(T) fn)`
- `void postOrder(void(T) fn)`
- `u64 depth(TreeNode<T>* node)`
- `u64 size()` — total node count
- `vec<T> toVec()` — pre-order flatten

---

## 20. `std/collections/cache` — LRU Cache

### `struct CacheEntry<K, V>` — key, value, prev*, next*
### `struct cache<K, V>` — wraps hashmap + doubly-linked list
- `static cache<K, V> new(u64 max, u64(K) hf, bool(K, K) ef)`
- `void dispose()`
- `u64 count()`
- `u64 maxSizeValue()`
- `void insert(K key, V value)` — upsert, evicts LRU if over max
- `option<V> get(K key)` — access, moves to front
- `V* getPtr(K key)` — mutable pointer, moves to front
- `bool contains(K key)`
- `void remove(K key)`
- `void clear()`
- `void each(void(K, V) fn)` — from MRU to LRU
- `void resize(u64 newMax)` — shrink if needed

---

## 21. `std/collections/sort` — Sorting Algorithms

```coral
pub void sortI32(vec.vec<i32>* v)
pub void sortU64(vec.vec<u64>* v)
pub void sortF64(vec.vec<f64>* v)
pub void sortBy<T>(vec.vec<T>* v, bool(T, T) less)   // generic quicksort
pub bool isSortedI32(const vec.vec<i32>* v)
pub bool isSortedU64(const vec.vec<u64>* v)
pub bool isSortedBy<T>(const vec.vec<T>* v, bool(T, T) less)
pub i64 binarySearchI32(const vec.vec<i32>* v, i32 key)
pub i64 binarySearchU64(const vec.vec<u64>* v, u64 key)
pub i64 binarySearchBy<T>(const vec.vec<T>* v, T key, i32(T, T) cmp)
pub void reverse<T>(vec.vec<T>* v)
```

---

## 22. `std/collections/iter` — Iterator Combinators

```coral
pub struct Pair<T, U> { T first; U second; }

pub vec.vec<U> map<T, U>(const vec.vec<T>* v, U(T) fn)
pub vec.vec<T> filter<T>(const vec.vec<T>* v, bool(T) pred)
pub T reduce<T>(const vec.vec<T>* v, T init, T(T, T) fn)
pub void forEach<T>(const vec.vec<T>* v, void(T) fn)
pub T find<T>(const vec.vec<T>* v, bool(T) pred)
pub i64 findIndex<T>(const vec.vec<T>* v, bool(T) pred)
pub bool any<T>(const vec.vec<T>* v, bool(T) pred)
pub bool all<T>(const vec.vec<T>* v, bool(T) pred)
pub vec.vec<T> take<T>(const vec.vec<T>* v, u64 n)
pub vec.vec<T> skip<T>(const vec.vec<T>* v, u64 n)
pub vec.vec<T> slice<T>(const vec.vec<T>* v, u64 start, u64 end)
pub vec.vec<Pair<T, U>> zip<T, U>(const vec.vec<T>* a, const vec.vec<U>* b)
pub u64 countIf<T>(const vec.vec<T>* v, bool(T) pred)
pub T minBy<T>(const vec.vec<T>* v, bool(T, T) less)
pub T maxBy<T>(const vec.vec<T>* v, bool(T, T) less)
pub vec.vec<T> unique<T>(const vec.vec<T>* v, bool(T, T) eq)
pub vec.vec<T> flatten<T>(const vec.vec<vec.vec<T>>* v)
pub vec.vec<u64> enumerate<T>(const vec.vec<T>* v)
pub T sum<T>(const vec.vec<T>* v)
pub f64 average(const vec.vec<f64>* v)
```

---

## 23. `std/collections/unordered_map` — Wrapper over hashmap

### `struct unordered_map<K, V>` — wraps `hashmap<K, V>`
- `static unordered_map<K, V> new(u64(K) hf, bool(K, K) ef)`
- `void dispose()`
- `u64 count()`
- `bool isEmpty()`
- `void insert(K key, V value)`
- `option.option<V> get(K key)`
- `V* getPtr(K key)`
- `bool contains(K key)`
- `void remove(K key)`
- `void clear()`
- `vec<K> keys()` — collect keys
- `vec<V> values()` — collect values
- `void each(void(K, V) fn)`

---

## 24. `std/text/string` — Strings and Views

### `struct ByteView` — `const u8* ptr`, `u64 len`
- `static ByteView fromParts(const u8* ptr, u64 len)`
- `static ByteView fromStrView(strView sv)`
- `static ByteView empty()`

### `struct strView` — `const char* ptr`, `u64 len`
- `static strView fromCstr(const char* cstr)`
- `static strView fromParts(const char* ptr, u64 len)`
- `static strView empty()`
- `const u8* asU8()`
- `char at(u64 idx)`
- `bool isEmpty()`
- `bool equals(strView other)`
- `i32 compare(strView other)`
- `bool startsWith(strView prefix)`
- `bool endsWith(strView suffix)`
- `bool containsView(strView needle)`
- `bool containsByte(char c)`
- `u64 findByte(char c)`
- `u64 rfindByte(char c)`
- `u64 findView(strView needle)`
- `strView slice(u64 start, u64 end)`
- `strView trimStart()`
- `strView trimEnd()`
- `strView trim()`
- `bool isAsciiDigit()` — all chars are '0'-'9'
- `bool isAsciiAlpha()` — all chars are 'a'-'z'/'A'-'Z'
- `bool isAsciiAlnum()`

### `struct String` — `char* ptr`, `u64 len`, `u64 cap`
- `static String new()`
- `static String withCap(u64 cap)`
- `static String fromView(strView sv)`
- `static String fromCstr(const char* cstr)`
- `static String join(strView sep, const vec.vec<strView>* parts)`
- `String clone()`
- `void free()` — deallocate
- `strView asView()`
- `const char* asCstr()`
- `const u8* asU8()`
- `void pushChar(char c)`
- `void pushView(strView sv)`
- `void pushStr(const String* other)`
- `void pushCstr(const char* cstr)`
- `void pushRepeat(char c, u64 n)`
- `void clear()`
- `void shrinkToFit()`
- `void truncate(u64 newLen)`
- `void insertView(u64 idx, strView sv)`
- `void removeRange(u64 start, u64 end)`
- `void replaceAll(strView needle, strView replacement)` — allocates new
- `void toUpper()` — ASCII only
- `void toLower()` — ASCII only
- `void reverse()`
- `char at(u64 idx)`
- `bool isEmpty()`
- `bool equals(const String* other)`
- `bool equalsView(strView sv)`
- `i32 compare(const String* other)`
- `u64 findChar(char c)`
- `u64 rfindChar(char c)`
- `u64 findView(strView needle)`
- `bool startsWith(strView prefix)`
- `bool endsWith(strView suffix)`
- `bool containsView(strView needle)`
- `String trim()` — new string trimmed
- `String trimStart()`
- `String trimEnd()`
- `String substr(u64 start, u64 end)` — substring as new String
- `vec.vec<strView> splitByte(char delim)` — split into views
- `String repeat(u64 n)` — repeat string n times
- `String padLeft(u64 totalLen, char padChar)`
- `String padRight(u64 totalLen, char padChar)`
- `u64 countChar(char c)`

---

## 25. `std/text/fmt` — Formatting Utilities

```coral
pub string.String format(string.strView fmt, ...)          // basic format (no interpolation yet)
pub string.String formatInt(i64 val, u64 radix, bool upper)
pub string.String formatUint(u64 val, u64 radix, bool upper)
pub string.String formatFloat(f64 val, u64 precision)
pub string.String formatHex(u64 val, bool prefix)          // lowercase hex
pub string.String formatHexUpper(u64 val, bool prefix)
pub string.String formatBin(u64 val, bool prefix)
pub string.String padLeft(string.strView sv, u64 width, char pad)
pub string.String padRight(string.strView sv, u64 width, char pad)
pub string.String repeat(string.strView sv, u64 count)
pub string.String join(const string.strView* parts, u64 count, string.strView sep)
pub string.String joinVec(const vec<string.String>* parts, string.strView sep)
```

---

## 26. `std/text/strutil` — String Utility Functions (strView based)

```coral
pub u64 split(strView sv, char delim, strView* out, u64 maxParts)     // fill array
pub vec<strView> splitVec(strView sv, char delim)
pub strView trim(strView sv)
pub strView trimLeft(strView sv)
pub strView trimRight(strView sv)
pub bool startsWith(strView sv, strView prefix)
pub bool endsWith(strView sv, strView suffix)
pub bool contains(strView sv, strView sub)
pub i64 indexOf(strView sv, strView sub)
pub i64 indexOfChar(strView sv, char ch)
pub i64 lastIndexOf(strView sv, strView sub)
pub string replace(strView sv, strView from, strView to)        // returns new String
pub string join(const strView* parts, u64 count, strView sep)   // returns new String
pub string joinVec(const vec<strView>* parts, strView sep)
pub strView substr(strView sv, u64 start, u64 len)
pub bool equalsIgnoreCase(strView a, strView b)                  // ASCII only
```

---

## 27. `std/text/utf8` — UTF-8 Encoding

```coral
pub u8 encodeCodepoint(u32 cp, u8* out)          // returns bytes written (1-4)
pub u32 decodeCodepoint(const u8* s, u64 len, u64* consumed)
                                                 // rejects overlong, surrogates,
                                                 // >U+10FFFF, bad continuations (0xFFFD)
pub u64 codepointLen(const u8* s, u64 len)
pub u64 countCodepoints(const u8* s, u64 len)
pub bool isValid(const u8* s, u64 len)           // valid UTF-8?
pub string toLower(const u8* s, u64 len)         // ASCII-only (A-Z → a-z)
pub string toUpper(const u8* s, u64 len)         // ASCII-only (a-z → A-Z)
```

---

## 28. `std/text/json` — JSON Parser/Serializer

### `enum JsonType` — Null, Bool, I64, F64, String, Array, Object
### `struct JsonValue` — type + union of values
- `JsonValue nullVal()`
- `JsonValue boolVal(bool b)`
- `JsonValue i64Val(i64 n)`
- `JsonValue f64Val(f64 n)`
- `JsonValue stringVal(string s)`
- `JsonValue arrayVal()` — creates empty array
- `JsonValue objectVal()` — creates empty object
- `void dispose()`

### `struct JsonPair` — `string key`, `JsonValue value`
- `pub bool parse(strView input, JsonValue* out)` — parse JSON
- `pub string serialize(JsonValue* v)` — serialize to string

---

## 29. `std/text/csv` — CSV Reader

### `struct csvReader` — `data`, `len`, `pos`, `line`, `error`, `delim`
- `csvReader new(strView input)`
- `bool eof()`
- `bool readRow(vec<string>* fields)` — read one row

---

## 30. `std/text/ini` — INI File Parser

### `struct iniSection` — wraps `hashmap<string, string>`
- `iniSection new()`
- `void dispose()`
- `string get(strView key)`
- `void set(strView key, strView value)`

### `struct iniFile` — sections + names
- `iniFile new()` — has a global section
- `void dispose()`
- `bool parse(strView input)`
- `iniSection* section(strView name)`
- `string get(strView section, strView key)`

---

## 31. `std/text/toml` — TOML Parser

### `enum TomlValueType` — String, Integer, Float, Bool, Array, Table
### `struct TomlValue`
- Static constructors: `stringVal`, `intVal`, `floatVal`, `boolVal`, `arrayVal`, `tableVal`
- `void dispose()`

### `struct TomlPair` — `String key`, `TomlValue value`
### `struct TomlDoc` — `vec<TomlPair> root`
- `static TomlDoc new()`
- `void dispose()`
- `TomlValue* get(strView key)` — top-level key
- `TomlValue* getIn(strView table, strView key)` — table.key
- `pub bool parseToml(strView input, TomlDoc* doc)` — parse function

---

## 32. `std/text/xml` — XML Parser/Serializer

### `struct XmlAttribute` — `String name`, `String value` + `void dispose()`
### `enum XmlNodeType` — Element, Text, Comment, CData
### `struct XmlNode`
- `static XmlNode element(strView tag)`
- `static XmlNode text(strView content)`
- `void dispose()`
- `bool hasAttr(strView name)`
- `strView getAttr(strView name)`
- `XmlNode* firstChild(strView tagName)`
- `pub bool parseXml(strView input, XmlNode* out)` — parse
- `pub String serializeXml(XmlNode* node)` — serialize

---

## 33. `std/text/regex` — POSIX Regex Wrapper

### `struct Regex` — `void* impl[8]`, `bool compiled`, `u8* findBuf`, `u64 findBufCap`
- `bool compile(strView pattern, bool caseInsensitive)` — POSIX extended; resets on failure
- `void free()` — regfree only if compiled; frees find buffer
- `bool matches(strView input)` — anchored full-string match
- `bool find(strView input, vec<strView>* groups)` — match with groups; group views point
  into an internal buffer that stays valid until the next `find`/`free`
- `pub i32 regexFlags(bool extended, bool icase, bool nosub)` — helper

---

## 34. `std/text/uuid` — UUID v4

### `struct Uuid` — `u8 bytes[16]`
- `static Uuid zero()`
- `static Uuid v4()` — random v4
- `String toString()` — canonical form (xxxxxxxx-xxxx-...)
- `String toHex()` — hex without dashes
- `static Uuid fromString(strView s)`
- `bool eq(Uuid other)`
- `bool isNil()`
- `pub String uuidV4()` — convenience: returns String
- `pub Uuid parseUuid(strView s)` — convenience

---

## 35. `std/text/uri` — URI Parser

### `struct uri` — scheme, userInfo, host, port, path, query, fragment, hasPort
- `uri new()`
- `void dispose()`
- `bool parse(strView input)` — parse RFC 3986 URI

---

## 36. `std/io/ios` — I/O System (print/read)

### Print manipulator types:
```coral
pub struct FmtSpaces { u64 count; }
pub struct FmtRepeat { char ch; u64 count; }
pub struct FmtHex { u64 value; }
pub struct FmtBin { u64 value; }
pub struct FmtFixed { f64 value; u64 precision; }
```

### Print manipulator constructors:
```coral
pub FmtSpaces spaces(u64 count)
pub FmtRepeat repeat(char ch, u64 count)
pub FmtHex hex(u64 value)
pub FmtBin bin(u64 value)
pub FmtFixed fixed(f64 value, u64 precision)
```

### Variadic print:
```coral
pub void print<T...>(T... args)      // stdout
pub void nprint<T...>(T... args)     // stdout + newline
pub void eprint<T...>(T... args)     // stderr
pub void neprint<T...>(T... args)    // stderr + newline
pub void flush()                     // stdout flush
```

### Parsing:
```coral
pub i64 parseI64(string.strView sv, bool* ok)   // overflow-safe (INT64_MIN OK)
pub f64 parseF64(string.strView sv, bool* ok)   // rejects trailing garbage
```

### Reading:
```coral
pub char readChar()
pub bool readLine(string.String* out)
pub void read<T>(T* out)            // comptime-dispatched: i8..i64, u8..u64, f32, f64, bool, char, String
pub T readVal<T>()                  // read and return
```

---

## 37. `std/io/fs` — File System Operations

### Constants: O_RDONLY, O_WRONLY, O_RDWR, O_CREAT, O_TRUNC, O_APPEND, S_IRWXU, S_IRUSR, S_IWUSR, S_IXUSR, SEEK_SET/CUR/END, F_OK, R_OK, W_OK, X_OK

### `distinct File = i32`
### `distinct Dir = void*`
### `struct Stat` — full stat fields

### `enum FileType` — Unknown, Regular, Directory, CharDevice, BlockDevice, Fifo, Symlink, Socket

```coral
pub File fileOpen(strView path, strView mode)     // mode: "r", "w", "a", "+"
pub void fileClose(File f)
pub i64 fileRead(File f, u8* buf, u64 count)
pub i64 fileWrite(File f, const u8* buf, u64 count)
pub i64 fileSeek(File f, i64 offset, i32 whence)
pub bool fileExists(strView path)
pub bool statPath(strView path, Stat* out)
pub FileType getFileType(const Stat* s)
pub bool createDir(strView path, i32 mode)         // mkdir
pub bool removeDir(strView path)                   // rmdir
pub bool deleteFile(strView path)                  // unlink
pub bool renameFile(strView oldPath, strView newPath)
pub bool canAccess(strView path, i32 mode)          // access()
pub Dir openDir(strView path)                      // opendir
pub void* readDir(Dir dir)                         // readdir
pub void closeDir(Dir dir)                         // closedir
pub String readFileToString(strView path)          // read whole file
```

---

## 38. `std/io/fios` — FILE*-based File I/O

### `distinct FileHandle = void*` (C FILE*)
```coral
pub FileHandle fileOpen(strView path, strView mode)
pub void fileClose(FileHandle fh)
pub u64 fileWrite(FileHandle fh, strView data)
pub u64 fileRead(FileHandle fh, u8* buf, u64 maxLen)
pub bool fileEof(FileHandle fh)
pub void fileFlush(FileHandle fh)
pub u64 fileWriteString(FileHandle fh, const string* s)
pub bool fileReadAll(strView path, string* out)    // read whole file into string
```

---

## 39. `std/io/bio` — Binary I/O (raw fd)

### `struct FileReader` — `i32 fd`
- `FileReader fromFd(i32 fd)`
- `bool readBytes(u8* dst, u64 n)` — exact read
- `u8 readU8()` / `u16 readU16Le()` / `u32 readU32Le()` / `u64 readU64Le()`
- `i8 readI8()` / `i16 readI16Le()` / `i32 readI32Le()` / `i64 readI64Le()`
- Big-endian variants: `readU16Be`, `readU32Be`, `readU64Be`, etc.
- `f32 readF32Le()` / `f64 readF64Le()` / `f32 readF32Be()` / `f64 readF64Be()`
- integer reads zero-initialize on EOF (no garbage)
- `void skip(u64 n)` — lseek SEEK_CUR

### `struct FileWriter` — `i32 fd`
- `FileWriter fromFd(i32 fd)`
- `bool writeBytes(const u8* src, u64 n)`
- `void writeU8()` / `writeU16Le` / `writeU32Le` / `writeU64Le` / signed variants
- Big-endian write variants
- `writeF32Le` / `writeF64Le` / big-endian variants

### Byte swap helpers:
- `u16 bswapU16(u16 v)` / `u32 bswapU32(u32 v)` / `u64 bswapU64(u64 v)`

---

## 40. `std/io/net` — Networking (TCP/UDP)

```coral
pub distinct TcpSocket = i32

pub TcpSocket tcpConnect(strView ip, u16 port)
pub TcpSocket tcpListen(u16 port)
pub TcpSocket tcpAccept(TcpSocket server)
pub i64 tcpSend(TcpSocket sock, const u8* buf, u64 len)
pub i64 tcpRecv(TcpSocket sock, u8* buf, u64 len)
pub void tcpClose(TcpSocket sock)

pub struct UdpSocket { i32 fd; }
pub UdpSocket udpSocket()
pub bool udpBind(UdpSocket* s, u16 port)
pub i64 udpSendTo(UdpSocket* s, const u8* buf, u64 len, strView ip, u16 port)
pub i64 udpRecvFrom(UdpSocket* s, u8* buf, u64 len)
pub void udpClose(UdpSocket* s)
```

---

## 41. `std/io/process` — Process Spawning

### `struct Process` — pid, stdinFd, stdoutFd, stderrFd
### `struct ProcessResult` — exitCode, signaled, termSignal
```coral
pub Process spawn(strView cmd, vec<strView>* args)    // spawn with pipes
pub ProcessResult waitFor(Process* p)                  // wait + close pipes
pub i64 writeStdin(Process* p, const char* data, u64 len)
pub i64 readStdout(Process* p, u8* buf, u64 maxLen)
pub i64 readStderr(Process* p, u8* buf, u64 maxLen)
pub i32 run(strView cmd, vec<strView>* args)           // spawn + wait, returns exit code
pub void exit(i32 code)
```

---

## 42. `std/io/env` — Environment Variables

```coral
pub string get(strView name)              // get env var or empty
pub bool getInto(strView name, string* out)  // get into existing string
pub bool set(strView name, strView value)    // setenv overwrite=1
pub bool unset(strView name)                // unsetenv
pub u64 all(vec<string>* out)               // get all env vars
```

---

## 43. `std/io/path` — Path Manipulation

```coral
pub u64 findLastSep(string.strView p)
pub bool isAbsolute(string.strView p)
pub bool hasExtension(string.strView p)
pub string.strView extension(string.strView p)        // ".ext"
pub string.strView stem(string.strView p)             // filename without ext
pub string.strView parent(string.strView p)           // dirname
pub string.strView filename(string.strView p)         // basename
pub string.String join(string.strView a, string.strView b)
pub string.String normalize(string.strView p)         // drop ".", keep "..", dedupe "/"
pub string.String absolute(string.strView base, string.strView rel)
pub string.String changeExtension(string.strView p, string.strView newExt)
```

---

## 44. `std/io/temp` — Temporary Files/Dirs

### `struct TempFile` — fd, path, autoDelete
- `static TempFile create(strView prefix, strView suffix)`
- `void dispose()` — close + unlink if autoDelete
- `i32 fd()` / `strView pathStr()` / `void setAutoDelete(bool ad)`

### `struct TempDir` — path, autoDelete
- `static TempDir create(strView prefix)`
- `void dispose()` — rmdir if autoDelete
- `strView pathStr()` / `void setAutoDelete(bool ad)` / `bool isValid()`

---

## 45. `std/io/term` — Terminal ANSI Codes

```coral
pub void reset()           // 0m
pub void bold() / dim() / italic() / underline() / blink() / reverse() / hidden() / strikethrough()
pub void black() / red() / green() / yellow() / blue() / magenta() / cyan() / white()
pub void bgBlack() / bgRed() / bgGreen() / bgYellow() / bgBlue() / bgMagenta() / bgCyan() / bgWhite()
pub void brightBlack() / brightRed() / brightGreen() / brightYellow() / brightBlue() / brightMagenta() / brightCyan() / brightWhite()
pub void cursorUp(u64 n) / cursorDown / cursorRight / cursorLeft
pub void cursorPos(u64 row, u64 col)  // 1-based
pub void clearScreen() / clearLine() / clearToEnd() / clearLineEnd()
pub void saveCursor() / restoreCursor() / hideCursor() / showCursor()
```

---

## 46. `std/io/log` — Logging

### `enum LogLevel` — Debug, Info, Warn, Error, Fatal
### `struct Logger` — minLevel, name
- `Logger new(string.strView name, LogLevel minLevel)`
- `void dispose()`
- `void setLevel(LogLevel level)`
- `bool enabled(LogLevel level)`
- `void debug(strView msg)` / `info` / `warn` / `error` / `fatal`

---

## 47. `std/io/cmd` — Command-Line Argument Parsing

### `struct ArgParser` — positional, error, errMsg, pos
- `ArgParser new()`
- `void dispose()`
- `void parse(i32 argc, char** argv)` — collect positional args
- `bool hasFlag(i32 argc, char** argv, strView shortFlag, strView longFlag)`
- `bool getOption(i32 argc, char** argv, strView shortFlag, strView longFlag, string* out)`
- `u64 count()` / `strView get(u64 idx)`

---

## 48. `std/memory/mman` — Memory Management

### `struct Allocator` — ctx, alloc, free, realloc (function pointers)
```coral
pub Allocator* defaultAllocator          // global allocator
pub void initDefaultAllocator()          // TLSF over a mmap'd heap
pub void deinitDefaultAllocator()        // tear the default allocator down
pub void ensureDefaultAllocator()        // lazily init if null
pub Allocator cAllocator                 // free-list heap over mmap (no libc)
pub const u64 pageSize = 4096
pub Allocator pageAllocator              // mmap-based page allocator
```

### `struct FixedBufferAllocator` — buffer, cap, used
- `void init(u8* buffer, u64 size)`
- `Allocator allocator()`
- `void reset()`
- `u64 remaining()`

### `struct StackFallbackAllocator` — fba + fallback + stackBuf[1024]
- `void init(Allocator* fallback)`
- `Allocator allocator()`

### `struct ArenaAllocator` — backing, base, cap, used
- `void init(Allocator* backing, u64 initialCap)`
- `void deinit()`
- `Allocator allocator()`
- `void* push(u64 size)`
- `T* pushType<T>(u64 count)`
- `void reset()`
- `u64 remaining()`

### `struct PoolAllocator` — freeList, blockSize, blockCount, backing, source
- `void init(Allocator* source, u64 blockSize, u64 blockCount)`
- `void deinit()`
- `Allocator allocator()`
- `void* allocBlock()` / `void freeBlock(void* block)`

### `struct ScopeAlloc` — backing + tracked ptrs/sizes
- `void init(Allocator* backing, u64 cap)`
- `void* alloc(u64 size)` / `T* allocType<T>(u64 count)`
- `void freeAll()` / `void deinit()`
- `u64 bytesUsed()`

### `struct LoggingAllocator` — parent + stats
- `void init(Allocator* parent)`
- `Allocator allocator()`
- `void printStats()`

### Generic helpers (use `defaultAllocator`):
```coral
pub T* alloc<T>(u64 count)
pub void dealloc<T>(T* ptr)
pub T* realloc<T>(T* ptr, u64 newCount)
pub void copy<T>(T* dst, const T* src, u64 count)
pub void move<T>(T* dst, T* src, u64 count)
pub void zero<T>(T* ptr, u64 count)
pub bool equal<T>(const T* a, const T* b, u64 count)
```

---

## 49. `std/memory/tlsf` — TLSF Allocator

### `struct Tlsf` — O(1) bounded-time allocator
- `void init(void* heap, u64 size)`
- `void* alloc(u64 size)`
- `void free(void* ptr)`
- `void* realloc(void* ptr, u64 newSize)`
- `u64 getHeapSize()`
- `u64 getFreeSize()`
- `mman.Allocator allocator()` — wrap as Allocator interface

---

## 50. `std/memory/pool` — Generic Object Pool

### `struct pool<T>` — freeList, blocks, blockSize, blockCount, total, used
- `pool<T> new()` — empty pool (grows on demand)
- `void dispose()`
- `T* acquire()` — get a block (grows if empty)
- `void release(T* obj)` — return to pool
- `u64 available()` / `u64 used()` / `u64 capacity()`

---

## 51. `std/memory/smart_ptr` — Unique Owning Pointer

### `struct smart_ptr<T>` — `T* ptr`
- `void init(T value)` — allocate and copy
- `void dispose()` — deallocate
- `T get()` — value copy
- `T* data()` — mutable pointer
- `const T* constData()` — const pointer
- `void set(T value)`
- `bool isValid()`
- `T take()` — move out, deallocate old

---

## 52. `std/memory/shared_ptr` — Reference-Counted Pointer

### `struct shared_ptr<T>` — `T* ptr`, `RefCount* rc`
- `void init(T value)` — allocate + rc=1
- `void dispose()` — decrement, free if 0
- `T get()` / `T* data()` / `const T* constData()`
- `u64 refCount()`
- `bool isValid()`

---

## 53. `std/concurrent/thread` — Threading

```coral
pub distinct Thread = void*

pub struct Mutex { void* impl[6]; }
  void init() / destroy() / lock() / unlock()

pub struct ConditionVar { void* impl[6]; }
  void init() / destroy() / wait(Mutex*) / signal() / broadcast()

pub struct AtomicU64 { u64 value; }
  u64 load() / void store(u64 val) / u64 fetchAdd(u64 delta)
  u64 fetchSub(u64 delta) / bool compareExchange(u64 expected, u64 desired)

pub struct AtomicU32 { u32 value; }
  u32 load() / void store(u32 val) / u32 fetchAdd(u32 delta)

pub Thread threadCreate(void*(void*) fn, void* arg)
pub bool threadJoin(Thread t, void** retval)
pub void threadExit(void* retval)
pub Thread threadCurrent()
```

---

## 54. `std/concurrent/mutex` — POSIX Mutex

### `struct mutex` — wraps `pthread_mutex_t`
- `void init()` / `void initRecursive()`
- `void destroy()` / `void lock()` / `void unlock()`
- `bool tryLock()`

---

## 55. `std/concurrent/rwlock` — Read-Write Lock

### `struct rwlock`
- `void init()` / `void destroy()`
- `void readLock()` / `void writeLock()`
- `bool tryReadLock()` / `bool tryWriteLock()`
- `void unlock()`

---

## 56. `std/concurrent/semaphore` — POSIX Semaphore

### `struct semaphore`
- `void init(u32 value)` / `void destroy()`
- `void wait()` / `bool tryWait()` / `void post()`
- `i32 value()`

---

## 57. `std/concurrent/signal` — POSIX Signals

```coral
// Signal constants: SIGABRT, SIGALRM, SIGBUS, SIGCHLD, SIGCONT, SIGFPE,
// SIGHUP, SIGILL, SIGINT, SIGKILL, SIGPIPE, SIGQUIT, SIGSEGV, SIGSTOP,
// SIGTERM, SIGTSTP, SIGTTIN, SIGTTOU, SIGUSR1, SIGUSR2, SIGSYS, SIGTRAP,
// SIGURG, SIGXCPU, SIGXFSZ, and SIG_DFL/SIG_IGN values

pub typedef SigHandler = void(i32)

pub void(i32) handle(i32 sig, SigHandler* handler)     // signal()
pub void ignore(i32 sig)                                // SIG_IGN
pub void defaultHandler(i32 sig)                        // SIG_DFL
pub i32 send(i32 pid, i32 sig)                          // kill()
pub i32 raiseSig(i32 sig)                               // raise()
```

---

## 58. `std/concurrent/threadpool` — Thread Pool

### `struct threadpool`
- `bool init(u32 numThreads)` — create worker threads
- `void deinit()` — join all + clean up
- `bool enqueue(void(void*) func, void* arg)` — push task
- `u32 threadCount()`

---

## 59. `std/math/math` — Math Utilities

```coral
pub const f64 pi / f64 e / f64 srt2          // constants (srt2 is the historic sqrt2 spelling)
pub f64 pi() / f64 e() / f64 sqrt2()
pub f64 degToRad(f64 deg) / f64 radToDeg(f64 rad)
pub i64 clampI64(i64 v, i64 lo, i64 hi)
pub u64 clampU64(u64 v, u64 lo, u64 hi)
pub f64 clampF64(f64 v, f64 lo, f64 hi)
pub f64 lerp(f64 a, f64 b, f64 t)
pub f64 invLerp(f64 a, f64 b, f64 v)
pub f64 mapRange(f64 v, f64 a1, f64 b1, f64 a2, f64 b2)
pub i64 minI64(i64 a, i64 b) / i64 maxI64(i64 a, i64 b)
pub u64 minU64(u64 a, u64 b) / u64 maxU64(u64 a, u64 b)
pub f64 minF64(f64 a, f64 b) / f64 maxF64(f64 a, f64 b)
pub u64 absI64(i64 x) / f64 absF64(f64 x)
pub i64 signI64(i64 x) / f64 signF64(f64 x)
pub bool isFinite(f64 x) / bool isNan(f64 x)
pub f64 sin(f64 x) / cos(f64 x) / tan(f64 x)          // libc wrappers - inline functions
pub f64 sqrt(f64 x) / pow(f64 x, f64 y) / cbrt(f64 x)
pub f64 floor(f64 x) / ceil(f64 x) / round(f64 x) / fabs(f64 x) / fmod(f64 x, f64 y)
pub f64 asin(f64 x) / acos(f64 x) / atan(f64 x) / atan2(f64 y, f64 x)
pub f64 sinh(f64 x) / cosh(f64 x) / tanh(f64 x)
pub f64 exp(f64 x) / log(f64 x) / log2(f64 x) / log10(f64 x)
pub f64 hypot(f64 x, f64 y)
pub f64 erf(f64 x) / erfc(f64 x) / tgamma(f64 x) / lgamma(f64 x)
pub f64 strtod(const char* s, char** end)
```

---

## 60. `std/math/random` — Random Number Generation

```coral
pub u64 nextU64()          // /dev/urandom
pub u32 nextU32()
pub u64 nextRange(u64 lo, u64 hi)
pub f64 nextF64()          // uniform in [0,1), 52-bit precision

pub struct XorShift32 { u32 state; }
  XorShift32 seed(u32 s) -> u32 next() -> u64 nextU64() -> u64 nextRange()

pub struct Pcg32 { u64 state; u64 inc; }
  Pcg32 seed(u64 initState, u64 initSeq) -> u32 next()
  -> u64 nextU64() -> u64 nextRange()
```

---

## 61. `std/math/vector` — 2D/3D/4D Vectors

### `struct Vec2` — f64 x, y
- `static Vec2 new(f64 x, f64 y)`
- `Vec2 add(Vec2)` / `sub(Vec2)` / `scale(f64)` / `dot(Vec2)` / `lerp(Vec2, f64)`
- `f64 lengthSq()` / `f64 length()` / `Vec2 normalize()`

### `struct Vec3` — f64 x, y, z
- Same as Vec2 + `Vec3 cross(Vec3)`

### `struct Vec4` — f64 x, y, z, w
- Same pattern: add, sub, scale, dot, lengthSq, length, normalize, lerp

---

## 62. `std/math/matrix` — 2x2/3x3/4x4 Matrices

### `struct Mat2` / `Mat3` / `Mat4`
- `static identity()` / `fromRows(...)`
- `f64 at(row, col)` / `void set(row, col, val)`
- `Mat mul(Mat)` / `Vec mulVec(Vec)` / `transpose()`
- `f64 det()` — Mat2/Mat3 only; Mat4 has no determinant
- `Mat2 inverse()` / `Mat4 translation()/rotationX()/rotationY()/rotationZ()/scale()/perspective()/lookAt()`

---

## 63. `std/math/complex` — Complex Numbers

### `struct Complex` — f64 re, im
- `static new(f64 re, f64 im)` / `fromRe(f64)` / `fromIm(f64)`
- `add/sub/mul/div` — arithmetic
- `conj()` / `abs()` / `arg()` / `absSq()` / `neg()` / `scale(f64)`
- `exp()` / `log()` / `pow(Complex)` / `sin()` / `cos()` / `sqrt()`

---

## 64. `std/crypto/sha256` — SHA-256 Hash

### `struct sha256` — state, buf, count, bitLen
- `void init()`
- `void update(const u8* data, u64 len)`
- `void final(u8* digest)` — 32-byte digest
- `pub void hash(const u8* data, u64 len, u8* digest)` — one-shot

---

## 65. `std/crypto/hmac` — HMAC-SHA256

### `struct HmacSha256`
- `void init(const u8* key, u64 keyLen)`
- `void compute(const u8* msg, u64 msgLen, u8* outDigest)`
- `void computeWithKey(const u8* key, u64 keyLen, const u8* msg, u64 msgLen, u8* outDigest)`
- `bool verify(const u8* msg, u64 msgLen, const u8* expectedDigest)`
- `pub void hmacSha256(const u8* key, u64 keyLen, const u8* msg, u64 msgLen, u8* outDigest)` — one-shot

---

## 66. `std/crypto/aes` — AES Encryption

### `struct Aes256` — 256-bit key, 14 rounds
- `void init(const u8* key)`
- `void encryptBlock(u8* block)` / `void decryptBlock(u8* block)`
- `bool encryptCbc(const u8* iv, u8* data, u64 len)` — false if len==0 or not multiple of 16
- `bool decryptCbc(const u8* iv, u8* data, u64 len)` — false if len==0 or not multiple of 16

### `struct Aes128` — 128-bit key, 10 rounds
- Same methods as Aes256

---

## 67. `std/crypto/crc` — CRC32/CRC64

```coral
pub u32 crc32(const u8* data, u64 len)
pub u64 crc64(const u8* data, u64 len)
```

---

## 68. `std/crypto/base64` — Base64 Encoding

```coral
pub u64 encode(const u8* src, u64 srcLen, u8* dst, u64 dstCap)
pub string encodeToString(const u8* src, u64 srcLen)
pub u64 decode(const u8* src, u64 srcLen, u8* dst, u64 dstCap)
```

---

## 69. `std/crypto/hex` — Hex Encoding

```coral
pub u64 encode(const u8* src, u64 srcLen, u8* dst, u64 dstCap)
pub string encodeToString(const u8* src, u64 srcLen)
pub u64 decode(const u8* src, u64 srcLen, u8* dst, u64 dstCap)
pub bool isValid(const u8* src, u64 len)
```

---

## 70. `std/crypto/bloom` — Bloom Filter

### `struct bloom` — vec<u64> bits, numBits, numHashes
- `bloom new(u64 numBits, u64 numHashes)`
- `void dispose()`
- `void insert(const u8* data, u64 len)`
- `bool contains(const u8* data, u64 len)`
- `void clear()`
- `u64 bitsCount()` — number of set bits

---

## 71. `std/platform/libc` — System Bindings (POSIX + Windows)

All platform extern declarations in one place:
- **I/O:** read, write, getchar, putchar, fflush
- **String:** strlen, strcmp, strcpy
- **Memory:** malloc, free, realloc, memcpy, memmove, memset, memcmp
- **Math:** sin, cos, tan, sqrt, pow, floor, ceil, fabs, asin, acos, atan, atan2, sinh, cosh, tanh, cbrt, exp, log, log2, log10, round, fmod, hypot, erf, erfc, tgamma, lgamma, strtod
- **POSIX:** mmap, munmap, open, close, stat, mkdir, rmdir, unlink, rename, access, opendir, readdir, closedir
- **Stdio:** fopen, fclose, fread, fwrite, feof, snprintf
- **File ops:** lseek, mkstemp, mkdtemp
- **Regex:** regcomp, regexec, regfree, regerror
- **Process:** fork, execvp, waitpid, _exit, pipe, dup2, execvpe
- **Signals:** signal, kill, raise
- **Environment:** getenv, setenv, unsetenv, environ
- **Time:** gettimeofday, time, clock_gettime, nanosleep
- **Terminal:** isatty
- **Threads (POSIX):** pthread_create/join/exit/self, mutex, cond, rwlock, sem_*
- **Windows:** GetStdHandle, ReadFile, WriteFile, ExitProcess, CreateFileA, CloseHandle, DeleteFileA, etc.

---

## 72. `std/platform/os` — OS Constants

Selected via `flag (platform)` — one of `LINUX:` / `MACOS:` / `WINDOWS:` / `default:`:

```coral
pub const bool IS_LINUX / IS_MACOS / IS_WINDOWS / IS_FREEBSD / IS_OPENBSD / IS_WASM / IS_POSIX
pub const char PATH_SEP              // '/' (POSIX), '\\' (Windows)
pub const bool USES_CRLF             // true on Windows
pub const strView EXE_EXT            // "" / ".exe"
pub const strView DLL_EXT            // ".so" / ".dylib" / ".dll"
pub const strView NULL_DEV           // "/dev/null" / "NUL"
```

Always defined (outside the flag block):
```coral
pub const u64 SYS_PAGE_SIZE = 4096
pub const i32 STDIN_FD=0 / STDOUT_FD=1 / STDERR_FD=2
```

---

## 73. `std/platform/arch` — Architecture Constants

```coral
// Per-architecture via flag(ARCH):
pub const u64 CACHE_LINE_SIZE  // 64 (x86_64, x86, arm64, riscv64) / 32 (arm32)
pub const u64 PAGE_SIZE = 4096  // all
```

---

## 74. `std/platform/endian` — Endianness

Selected via `flag (ENDIAN)` — one of `little:` / `big:` / `default:`:

```coral
pub const bool IS_LITTLE_ENDIAN   // true only under flag (ENDIAN) little
pub const bool IS_BIG_ENDIAN

pub u16 bswapU16(u16) / u32 bswapU32(u32) / u64 bswapU64(u64)
pub i16 bswapI16(i16) / i32 bswapI32(i32) / i64 bswapI64(i64)
pub u16 htons(u16) / u16 ntohs(u16)
pub u32 htonl(u32) / u32 ntohl(u32)
pub u64 htonll(u64) / u64 ntohll(u64)
```

---

## 75. `std/misc/any` — Type-Erased Pointer

Type-erased holder: wraps a raw `void*` and recovers the typed pointer at the use site. Under the hood `any` is a `void*`.

### `struct any` — `void* p`
- `void* ptr()` — raw void pointer to the wrapped value
- `bool isNull()` — true if `p == null`
- `T* as<T>()` — reinterpret cast of `p` to `T*`

**Free functions:**
- `pub any wrap(void* value)` — store a raw pointer in an `any`

---

## 76. `std/misc/cast` — Generic Type Cast Through `any`

```coral
pub T cast<T>(any val)   // reinterprets the wrapped pointer as T
```