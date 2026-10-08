// probe_ach_vm.c - see probe_ach_vm.h. Each function names the rcheevos
// 12.5 function it ports; keep them in step with that code.
//
// The program (version 2), little endian, built by DSiRPC with rcheevos'
// own parser (third_party/rcheevos/dsirpc_offline.c):
//
//   u32 2, u16 plain memrefs P, u16 modified memrefs M, u16 achievements A,
//   u16 0, u32 conditions C
//   P x 8 bytes: u32 address, u8 size, u8 value type, u16 0
//   M x 20 bytes: u8 size, u8 value type, u8 modifier type, u8 0,
//                 operand parent, operand modifier
//   A x achievement: u32 id, u8 condsets, u8 has core, u16 conditions,
//       then each condset: u16 pause, reset, hit target, measured, other
//       counts, u16 0, and its conditions in that order, 16 bytes each:
//       u32 w (type 0-3, operator 4-7, kind1 8-11, kind2 12-15, size1 16-20,
//       size2 21-25, read1 27-28, read2 29-30, 31: rcheevos' memref-to-
//       its-own-delta shortcut), u32 value1, u32 value2, u32 hit target
//
// An operand is a kind (rcheevos' RC_OPERAND_*: 0 value, 1 delta, 2 constant,
// 5 prior, 6 BCD, 7 inverted, 8 recall), a size (RC_MEMSIZE_*) and a value
// (a memref index - the plain ones first - or the constant). A recall says
// how it reads its memref (0 value, 1 delta, 2 prior). In a modified memref
// an operand is 8 bytes: u8 kind, u8 size, u8 read, u8 0, u32 value.

#include "probe_ach_vm.h"

// rcheevos' constants (rc_runtime_types.h, rc_internal.h)
enum { K_ADDRESS = 0, K_DELTA = 1, K_CONST = 2, K_PRIOR = 5, K_BCD = 6, K_INVERTED = 7, K_RECALL = 8 };
enum { READ_VALUE = 0, READ_DELTA = 1, READ_PRIOR = 2 };
enum {
	C_STANDARD, C_PAUSE_IF, C_RESET_IF, C_MEASURED_IF, C_TRIGGER, C_MEASURED, C_ADD_SOURCE,
	C_SUB_SOURCE, C_ADD_ADDRESS, C_REMEMBER, C_ADD_HITS, C_SUB_HITS, C_RESET_NEXT_IF,
	C_AND_NEXT, C_OR_NEXT
};
enum {
	O_EQ, O_LT, O_LE, O_GT, O_GE, O_NE, O_NONE, O_MULT, O_DIV, O_AND, O_XOR, O_MOD, O_ADD, O_SUB,
	O_SUB_PARENT, O_ADD_ACCUMULATOR, O_SUB_ACCUMULATOR, O_INDIRECT_READ
};
enum {
	S_8, S_16, S_24, S_32, S_LOW, S_HIGH, S_BIT0, S_BIT1, S_BIT2, S_BIT3, S_BIT4, S_BIT5, S_BIT6,
	S_BIT7, S_BITCOUNT, S_16BE, S_24BE, S_32BE, S_COUNT
};
enum { T_NONE, T_UNSIGNED, T_SIGNED };

// How often AchVm_Run() asks keepGoing(): every this many memory values or
// conditions (a power of 2)
#define ACHVM_CHECK_EVERY 8

#define PLAIN_SIZE  8
#define MOD_SIZE    20
#define SET_SIZE    12
#define COND_SIZE   16
#define HEADER_SIZE 16
#define HAD_HITS    0x80

typedef struct { uint32_t v; uint8_t t; } Tv;   // rc_typed_value_t without floats

typedef AchVm_Eval Ev;

// The program is word aligned throughout (the set file is loaded at a word
// boundary), and both the console and the PCs it's tested on are little
// endian, so fields are read directly.
typedef uint32_t __attribute__((may_alias)) u32_alias;
typedef uint16_t __attribute__((may_alias)) u16_alias;
static uint32_t rd16(const uint8_t *p) { return *(const u16_alias *)p; }
static uint32_t rd32(const uint8_t *p) { return *(const u32_alias *)p; }

// -- memory -----------------------------------------------------------------

// DSiRPC's peek: little endian, 0 if any byte is past main RAM
static uint32_t peek(const AchVm *vm, uint32_t a, uint32_t n) {
	if (a > vm->ramSize - n) return 0;
	const uint8_t *p = vm->ram + a;
	if (n == 1) return p[0];
	if (n == 2) return (a & 1) ? (uint32_t)(p[0] | (p[1] << 8)) : rd16(p);
	return (a & 3) ? (p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24)) : rd32(p);
}

// rc_memref_masks, rc_memref_shared_sizes (in bytes), rc_bits_set
static const uint32_t masks[S_COUNT] = {
	0xff, 0xffff, 0xffffff, 0xffffffff, 0x0f, 0xf0, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80,
	0xff, 0xffff, 0xffffff, 0xffffffff
};
static const uint8_t sharedBytes[S_COUNT] = { 1, 2, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 4, 4 };
static const uint8_t bitsSet[16] = { 0, 1, 1, 2, 1, 2, 2, 3, 1, 2, 2, 3, 2, 3, 3, 4 };

// rc_peek_value
static uint32_t peekSized(const AchVm *vm, uint32_t a, uint8_t size) {
	if (size >= S_COUNT) return 0;
	uint32_t v = peek(vm, a, sharedBytes[size]);
	if (size == S_8 || size == S_16 || size == S_32) return v;
	return v & masks[size];
}

// rc_transform_memref_value (integer sizes). Sizes up to S_BIT7 are a mask
// and a shift: (v & masks[size]) >> maskShifts[size].
static const uint8_t maskShifts[S_BITCOUNT] = { 0, 0, 0, 0, 0, 4, 0, 1, 2, 3, 4, 5, 6, 7 };

static uint32_t transformSize(uint32_t v, uint32_t size) {
	if (size < S_BITCOUNT) return (v & masks[size]) >> maskShifts[size];
	switch (size) {
		case S_BITCOUNT: return bitsSet[v & 0x0f] + bitsSet[(v >> 4) & 0x0f];
		case S_16BE: return ((v & 0xff00) >> 8) | ((v & 0x00ff) << 8);
		case S_24BE: return ((v & 0xff0000) >> 16) | (v & 0x00ff00) | ((v & 0x0000ff) << 16);
		case S_32BE: return (v >> 24) | ((v >> 8) & 0xff00) | ((v << 8) & 0xff0000) | (v << 24);
		default: return v;
	}
}

// rc_transform_operand_value
static uint32_t transformOperand(uint32_t v, uint8_t kind, uint8_t size) {
	if (kind == K_BCD) {
		int digits;
		switch (size) {
			case S_8: digits = 2; break;
			case S_16: case S_16BE: digits = 4; break;
			case S_24: case S_24BE: digits = 6; break;
			case S_32: case S_32BE: digits = 8; break;
			default: return v;
		}
		uint32_t out = 0, scale = 1;
		for (int i = 0; i < digits; i++) {
			out += ((v >> (i * 4)) & 0x0f) * scale;
			scale *= 10;
		}
		return out;
	}
	if (kind == K_INVERTED) {
		switch (size) {
			case S_LOW: case S_HIGH: return v ^ 0x0f;
			case S_8: return v ^ 0xff;
			case S_16: case S_16BE: return v ^ 0xffff;
			case S_24: case S_24BE: return v ^ 0xffffff;
			case S_32: case S_32BE: return v ^ 0xffffffff;
			default: return v ^ 0x01;
		}
	}
	return v;
}

static uint8_t memrefType(const AchVm *vm, uint32_t i) {
	if (i < vm->nPlain) return vm->plain[i * PLAIN_SIZE + 5];
	return vm->mod[(i - vm->nPlain) * MOD_SIZE + 1];
}

// rc_get_memref_value_value
static uint32_t memrefRead(const AchVm *vm, uint32_t i, uint8_t read) {
	if (read == READ_DELTA && !vm->memChanged[i]) return vm->memValue[i];
	if (read == READ_DELTA || read == READ_PRIOR) return vm->memPrior[i];
	return vm->memValue[i];
}

// rc_evaluate_operand: the value in the low 32 bits, its type above, so
// both come back in registers. A memref operand always names one of the
// program's memrefs (checkProgram() makes sure).
#define TV(t, v) (((uint64_t)(t) << 32) | (uint32_t)(v))
#define TV_T(p)  ((uint32_t)((p) >> 32))
#define TV_V(p)  ((uint32_t)(p))

static uint64_t operand(const AchVm *vm, uint32_t kind, uint32_t size, uint32_t read, uint32_t value) {
	if (kind == K_CONST) return TV(T_UNSIGNED, value);
	if (kind != K_RECALL) read = (kind == K_DELTA) | ((uint32_t)(kind == K_PRIOR) << 1);
	uint32_t t = memrefType(vm, value);
	uint32_t v = transformSize(memrefRead(vm, value, read), size);
	if ((kind == K_BCD || kind == K_INVERTED) && t == T_UNSIGNED) v = transformOperand(v, kind, size);
	return TV(t, v);
}

// -- typed values (rcheevos' value.c, without floats) ------------------------

// rc_typed_value_convert
static void convert(Tv *v, uint8_t t) {
	if (t == T_UNSIGNED || t == T_SIGNED) {
		if (v->t != T_UNSIGNED && v->t != T_SIGNED) v->v = 0; // the bits stay for the other
	}
	v->t = t;
}

// rc_typed_value_negate
static void negate(Tv *v) {
	if (v->t == T_UNSIGNED) v->t = T_SIGNED;
	if (v->t == T_SIGNED) v->v = 0u - v->v;
}

// rc_typed_value_add
static void add(Tv *v, const Tv *amount) {
	Tv a = *amount;
	if (v->t == T_NONE) {
		*v = a;
		return;
	}
	if (a.t != v->t) convert(&a, v->t);
	v->v += a.v; // same bits for unsigned and signed
}

static int isInt(uint8_t t) { return t == T_UNSIGNED || t == T_SIGNED; }

// rc_typed_value_multiply
static void multiply(Tv *v, const Tv *a) {
	if (isInt(v->t) && isInt(a->t)) v->v *= a->v; // the low 32 bits are the same either way
	else v->t = T_NONE;
}

// rc_typed_value_divide / rc_typed_value_modulus (mod = 1)
static void divide(Tv *v, const Tv *a, int mod) {
	if (!isInt(a->t) || a->v == 0 || !isInt(v->t)) {
		v->t = T_NONE;
		return;
	}
	// rcheevos does the signed math when the left side is signed, the
	// unsigned math when it's unsigned, whatever the right side is
	if (v->t == T_UNSIGNED) {
		v->v = mod ? v->v % a->v : v->v / a->v;
	} else {
		int32_t x = (int32_t)v->v, y = (int32_t)a->v;
		if (y == -1) v->v = mod ? 0 : 0u - v->v; // INT_MIN / -1 would trap on a PC
		else v->v = (uint32_t)(mod ? x % y : x / y);
	}
}

// rc_typed_value_combine
static void combine(Tv *v, Tv *a, uint8_t oper) {
	switch (oper) {
		case O_MULT: multiply(v, a); break;
		case O_DIV: divide(v, a, 0); break;
		case O_MOD: divide(v, a, 1); break;
		case O_AND: convert(v, T_UNSIGNED); convert(a, T_UNSIGNED); v->v &= a->v; break;
		case O_XOR: convert(v, T_UNSIGNED); convert(a, T_UNSIGNED); v->v ^= a->v; break;
		case O_ADD: add(v, a); break;
		case O_SUB: negate(a); add(v, a); break;
		default: break;
	}
}

// rc_typed_value_compare. Which outcomes (bit 0 less, 1 equal, 2 greater)
// each operator accepts: EQ, LT, LE, GT, GE, NE, NONE.
static const uint8_t accepts[O_NONE + 1] = { 2, 1, 3, 4, 6, 5, 7 };

// (b takes a's type first: a value that isn't a number becomes 0, and
// anything compared with a non-number is true)
static int compare(uint64_t pa, uint64_t pb, uint32_t oper) {
	uint32_t at = TV_T(pa), av = TV_V(pa), bt = TV_T(pb), bv = TV_V(pb), outcome;
	if (bt != T_UNSIGNED && bt != T_SIGNED) bv = 0;
	if (oper > O_NONE) return 1;
	if (at == T_UNSIGNED) {
		outcome = (av < bv) ? 1 : (av == bv) ? 2 : 4;
	} else if (at == T_SIGNED) {
		outcome = ((int32_t)av < (int32_t)bv) ? 1 : (av == bv) ? 2 : 4;
	} else {
		return 1;
	}
	return (accepts[oper] & outcome) != 0;
}

// -- memrefs ------------------------------------------------------------------

static uint64_t packedOperand(const AchVm *vm, const uint8_t *op) {
	uint32_t ksr = rd32(op); // kind, size, read, 0
	return operand(vm, ksr & 0xff, (ksr >> 8) & 0xff, (ksr >> 16) & 0xff, rd32(op + 4));
}

// rc_get_modified_memref_value
static uint32_t modifiedValue(const AchVm *vm, const uint8_t *m) {
	uint32_t head = rd32(m); // size, type, modifier type, 0
	uint64_t pv = packedOperand(vm, m + 4), pm = packedOperand(vm, m + 12);
	uint32_t oper = (head >> 16) & 0xff;
	if (isInt(TV_T(pv)) && isInt(TV_T(pm))) {
		// two numbers: what the general code below works out, directly
		if (oper == O_ADD_ACCUMULATOR) return TV_V(pv) + TV_V(pm);
		if (oper == O_SUB_ACCUMULATOR) return TV_V(pv) - TV_V(pm);
		if (oper == O_INDIRECT_READ) return peekSized(vm, TV_V(pv) + TV_V(pm), head & 0xff);
	}
	Tv value = { TV_V(pv), (uint8_t)TV_T(pv) }, modifier = { TV_V(pm), (uint8_t)TV_T(pm) };
	uint8_t size = head & 0xff, type = (head >> 8) & 0xff;
	switch (oper) {
		case O_INDIRECT_READ:
			add(&value, &modifier);
			convert(&value, T_UNSIGNED);
			return peekSized(vm, value.v, size);
		case O_SUB_PARENT:
			negate(&value);
			add(&value, &modifier);
			break;
		case O_SUB_ACCUMULATOR:
			negate(&modifier);
			/* fallthrough */
		case O_ADD_ACCUMULATOR:
			convert(&modifier, value.t);
			add(&value, &modifier);
			break;
		default:
			combine(&value, &modifier, oper);
			break;
	}
	convert(&value, type);
	return value.v;
}

// rc_update_memref_value
static inline __attribute__((always_inline)) void setMemref(AchVm *vm, uint32_t i, uint32_t v) {
	if (vm->memValue[i] == v) {
		vm->memChanged[i] = 0;
	} else {
		vm->memPrior[i] = vm->memValue[i];
		vm->memValue[i] = v;
		vm->memChanged[i] = 1;
	}
}

// rc_update_memref_values, from memref vm->memNext on. Returns 1 when
// they're all done, 0 if it stopped for keepGoing.
static int updateMemrefs(AchVm *vm, int (*keepGoing)(void *ud), void *ud) {
	uint32_t nPlain = vm->nPlain, nMem = nPlain + vm->nMod, i = vm->memNext;
	while (i < nMem) {
		if (i < nPlain) {
			const uint8_t *p = vm->plain + i * PLAIN_SIZE;
			uint32_t head = rd32(p + 4); // size, type
			if (((head >> 8) & 0xff) != T_NONE) setMemref(vm, i, peekSized(vm, rd32(p), head & 0xff));
		} else {
			setMemref(vm, i, modifiedValue(vm, vm->mod + (i - nPlain) * MOD_SIZE));
		}
		i++;
		if (!(i & (ACHVM_CHECK_EVERY - 1)) && i < nMem && keepGoing && !keepGoing(ud)) {
			vm->memNext = i;
			return 0;
		}
	}
	vm->memNext = i;
	return 1;
}

// -- conditions (rcheevos' condition.c and condset.c) --------------------------

#define COND_TYPE(w)  ((w) & 0x0f)
#define COND_OPER(w)  (((w) >> 4) & 0x0f)

#define COND_SAME_DELTA 0x80000000u // a memref against its own delta

// rc_test_condition
static int testCondition(const AchVm *vm, const uint8_t *c, uint32_t w) {
	if ((w & COND_SAME_DELTA) && !vm->memChanged[rd32(c + 4)]) {
		// rcheevos' shortcut: unchanged, so "equal", whichever bits each side reads
		uint8_t oper = COND_OPER(w);
		return oper == O_EQ || oper == O_GE || oper == O_LE;
	}
	uint64_t a = operand(vm, (w >> 8) & 0x0f, (w >> 16) & 0x1f, (w >> 27) & 3, rd32(c + 4));
	uint64_t b = operand(vm, (w >> 12) & 0x0f, (w >> 21) & 0x1f, (w >> 29) & 3, rd32(c + 8));
	return compare(a, b, COND_OPER(w));
}

// rc_condset_evaluate_condition_no_add_hits
static int evalNoAddHits(const AchVm *vm, Ev *ev, const uint8_t *c, uint32_t w, uint32_t *hits) {
	int valid = testCondition(vm, c, w);
	if (ev->resetNext) {
		*hits = 0;
		valid = 0;
	} else {
		valid &= ev->andNext;
		valid |= ev->orNext;
		uint32_t required = rd32(c + 12);
		if (valid) {
			ev->hasHits = 1;
			if (required == 0) {
				++*hits;
			} else if (*hits < required) {
				++*hits;
				valid = (*hits == required);
			}
		} else if (*hits > 0) {
			ev->hasHits = 1;
			valid = (*hits == required);
		}
	}
	ev->andNext = 1;
	ev->orNext = 0;
	return valid;
}

// rc_condset_evaluate_total_hits
static uint32_t totalHits(Ev *ev, uint32_t hits, uint32_t required) {
	uint32_t total = hits;
	if (required != 0) {
		int32_t s = (int32_t)hits + ev->addHits;
		total = (s >= 0) ? (uint32_t)s : 0;
	}
	ev->addHits = 0;
	return total;
}

// rc_condset_evaluate_condition
static int evalCondition(const AchVm *vm, Ev *ev, const uint8_t *c, uint32_t w, uint32_t *hits) {
	int valid = evalNoAddHits(vm, ev, c, w, hits);
	uint32_t required = rd32(c + 12);
	if (ev->addHits != 0 && required != 0)
		valid = (totalHits(ev, *hits, required) >= required);
	ev->resetNext = 0;
	return valid;
}

// rc_test_condset_internal, from condition cur->i of a phase on. Returns 1
// when the phase is done, 0 if it stopped for keepGoing (cur->i is where).
static int testConditions(const AchVm *vm, AchVm_Cursor *cur, const uint8_t *c, uint32_t *hits,
                          uint32_t n, int canShort, int (*keepGoing)(void *ud), void *ud) {
	Ev *ev = &cur->ev;
	uint32_t i = cur->i;
	c += i * COND_SIZE;
	hits += i;
	while (i < n) {
		uint32_t w = rd32(c), type = COND_TYPE(w);
		int valid;
		// the commonest types first, without the switch's table lookup
		if (type == C_STANDARD) {
			valid = evalCondition(vm, ev, c, w, hits);
			ev->isTrue &= valid;
			if (!valid && canShort) ev->stop = 1;
		} else if (type == C_AND_NEXT) {
			ev->andNext = (uint8_t)evalNoAddHits(vm, ev, c, w, hits);
		} else if (type == C_ADD_HITS) {
			evalNoAddHits(vm, ev, c, w, hits);
			ev->addHits += (int32_t)*hits;
			ev->resetNext = 0;
		} else switch (type) {
			case C_PAUSE_IF:
				valid = evalCondition(vm, ev, c, w, hits);
				if (valid) {
					ev->isPaused = 1;
					ev->isTrue = 0;
					ev->stop = 1;
				} else if (rd32(c + 12) == 0) {
					*hits = 0;
				}
				break;
			case C_RESET_IF:
				if (evalCondition(vm, ev, c, w, hits)) {
					ev->isTrue = 0;
					ev->wasReset = 1;
					ev->stop = 1;
				}
				break;
			case C_TRIGGER:
			case C_MEASURED_IF:
				ev->isTrue &= evalCondition(vm, ev, c, w, hits);
				break;
			case C_MEASURED: {
				uint32_t required = rd32(c + 12);
				if (required == 0) {
					valid = evalCondition(vm, ev, c, w, hits);
					ev->isTrue &= valid;
					if (!valid && canShort) ev->stop = 1;
				} else {
					evalNoAddHits(vm, ev, c, w, hits);
					ev->isTrue &= (totalHits(ev, *hits, required) >= required);
					ev->resetNext = 0;
				}
				break;
			}
			case C_ADD_SOURCE:
			case C_SUB_SOURCE:
			case C_ADD_ADDRESS:
			case C_REMEMBER:
				break; // done by the modified memrefs
			case C_SUB_HITS:
				evalNoAddHits(vm, ev, c, w, hits);
				ev->addHits -= (int32_t)*hits;
				ev->resetNext = 0;
				break;
			case C_RESET_NEXT_IF:
				ev->resetNext = (uint8_t)evalNoAddHits(vm, ev, c, w, hits);
				break;
			case C_OR_NEXT:
				ev->orNext = (uint8_t)evalNoAddHits(vm, ev, c, w, hits);
				break;
			default:
				ev->stop = 1;
				ev->isTrue = 0;
				break;
		}
		i++;
		c += COND_SIZE;
		hits++;
		if (ev->stop && canShort) break;
		if (!(i & (ACHVM_CHECK_EVERY - 1)) && i < n && keepGoing && !keepGoing(ud)) {
			cur->i = (uint16_t)i;
			return 0;
		}
	}
	cur->i = (uint16_t)i;
	return 1;
}

enum { PH_PAUSE, PH_RESET, PH_HIT, PH_MEASURED, PH_OTHER, PH_DONE };

static void beginCondset(AchVm_Cursor *cur) {
	uint32_t at = 0;
	cur->off[0] = 0;
	for (int k = 0; k < 5; k++) cur->off[k + 1] = (uint16_t)(at += rd16(cur->cs + 2 * k));
	cur->phase = PH_PAUSE;
	cur->i = 0;
	cur->ev.addHits = 0;
	cur->ev.isTrue = 1;
	cur->ev.isPaused = 0;
	cur->ev.andNext = 1;
	cur->ev.orNext = 0;
	cur->ev.resetNext = 0;
	cur->ev.stop = 0;
}

static uint32_t condsetSize(const AchVm_Cursor *cur) {
	return cur->off[5];
}

// rc_test_condset (triggers can't short circuit), a phase at a time.
// Returns 1 when the condset is done (cur->setResult), 0 if it stopped.
static int runCondset(const AchVm *vm, AchVm_Cursor *cur, int (*keepGoing)(void *ud), void *ud) {
	Ev *ev = &cur->ev;
	while (cur->phase < PH_DONE) {
		uint32_t p = cur->phase, start = cur->off[p], n = cur->off[p + 1] - start;
		const uint8_t *c = cur->cs + SET_SIZE + start * COND_SIZE;
		uint32_t *h = cur->hits + start;

		if (cur->i == 0) { // starting the phase
			int run = (n != 0);
			if (p == PH_HIT && ev->wasReset) run = 0;
			if (p == PH_OTHER && !ev->isTrue && ev->wasReset) run = 0;
			if (p == PH_MEASURED && run && ev->wasReset)
				for (uint32_t k = 0; k < n; k++) h[k] = 0;
			if (!run) {
				cur->phase++;
				continue;
			}
		}
		if (!testConditions(vm, cur, c, h, n, p == PH_PAUSE, keepGoing, ud)) return 0;
		cur->i = 0;
		if (p == PH_PAUSE && ev->isPaused) { // paused: nothing else counts
			cur->setResult = 0;
			cur->phase = PH_DONE;
			return 1;
		}
		cur->phase++;
	}
	cur->setResult = ev->isTrue;
	return 1;
}

static uint32_t achBytes(const uint8_t *a) {
	return 8 + a[4] * SET_SIZE + rd16(a + 6) * COND_SIZE;
}

// rc_evaluate_trigger, as rc_runtime_do_frame calls it, for the achievement
// at vm->nextAch. Returns 1 when it's done, 0 if it stopped for keepGoing.
static int runAchievement(AchVm *vm, AchVm_Triggered onTriggered, int (*keepGoing)(void *ud), void *ud) {
	AchVm_Cursor *cur = &vm->cur;
	const uint8_t *a = vm->nextAch;
	uint8_t *state = &vm->achState[vm->nextIndex];
	uint32_t *hits = vm->hits + vm->nextHit;
	uint32_t nSets = a[4], hasCore = a[5], nConds = rd16(a + 6), i;

	if (!cur->inAchievement) {
		if ((*state & 3) == ACHVM_TRIGGERED) return 1;
		Ev zero = { 0, 0, 0, 0, 0, 0, 0, 0, 0 };
		cur->ev = zero;
		cur->set = 0;
		cur->ret = 1;
		cur->sub = 0;
		cur->cs = a + 8;
		cur->hits = hits;
		cur->inAchievement = 1;
		if (nSets) beginCondset(cur);
	}
	while (cur->set < nSets) {
		if (!runCondset(vm, cur, keepGoing, ud)) return 0;
		if (hasCore && cur->set == 0) cur->ret = cur->setResult; // the core
		else cur->sub |= cur->setResult;                         // an alt
		uint32_t total = condsetSize(cur);
		cur->cs += SET_SIZE + total * COND_SIZE;
		cur->hits += total;
		if (++cur->set < nSets) beginCondset(cur);
	}
	cur->inAchievement = 0;

	uint8_t st = *state;
	int ret = cur->ret;
	if (nSets > hasCore) ret &= cur->sub; // one of the alts has to be true too
	Ev *ev = &cur->ev;
	if (ev->wasReset) {
		for (i = 0; i < nConds; i++) hits[i] = 0;
		if (st & HAD_HITS) { // rcheevos reports RESET, the state doesn't change
			*state = st & 3;
			return 1;
		}
		ev->hasHits = 0;
	} else if (ret) {
		if ((st & 3) == ACHVM_WAITING) { // true from the start: it has to be false first
			for (i = 0; i < nConds; i++) hits[i] = 0;
			*state = ACHVM_WAITING;
			return 1;
		}
		*state = ACHVM_TRIGGERED;
		vm->triggered++;
		if (onTriggered) onTriggered(rd32(a), ud);
		return 1;
	}
	*state = ACHVM_ACTIVE | (ev->hasHits ? HAD_HITS : 0);
	return 1;
}

// -- loading and running -------------------------------------------------------

static uint32_t align4(uint32_t n) { return (n + 3) & ~3u; }

// Checks the program and works out where everything is. Returns the state
// size, or 0 if the program isn't valid.
static uint32_t checkProgram(const uint8_t *p, uint32_t size, AchVm *vm) {
	if (size < HEADER_SIZE || rd32(p) != ACHVM_PROGRAM_VERSION) return 0;
	uint32_t nPlain = rd16(p + 4), nMod = rd16(p + 6), nAch = rd16(p + 8), nConds = rd32(p + 12);
	uint32_t nMem = nPlain + nMod;
	uint32_t pos = HEADER_SIZE + nPlain * PLAIN_SIZE + nMod * MOD_SIZE;
	if (pos > size || nConds > size / COND_SIZE) return 0;

	// every operand has to name a memref (or be a constant). Usually an
	// earlier one; a later one (a Remember from a PauseIf further on) is
	// read as it was last update, which is what rcheevos does too.
	for (uint32_t i = 0; i < nMod; i++) {
		const uint8_t *m = p + HEADER_SIZE + nPlain * PLAIN_SIZE + i * MOD_SIZE;
		for (int j = 0; j < 2; j++) {
			const uint8_t *op = m + 4 + j * 8;
			if (op[0] != K_CONST && rd32(op + 4) >= nMem) return 0;
		}
	}
	uint32_t conds = 0;
	for (uint32_t i = 0; i < nAch; i++) {
		if (pos + 8 > size) return 0;
		const uint8_t *a = p + pos;
		uint32_t nSets = a[4], achConds = rd16(a + 6), counted = 0;
		if (pos + achBytes(a) > size) return 0;
		const uint8_t *cs = a + 8;
		for (uint32_t s = 0; s < nSets; s++) {
			uint32_t n = rd16(cs) + rd16(cs + 2) + rd16(cs + 4) + rd16(cs + 6) + rd16(cs + 8);
			const uint8_t *c = cs + SET_SIZE;
			for (uint32_t k = 0; k < n; k++, c += COND_SIZE) {
				uint32_t w = rd32(c);
				if (((w >> 8) & 0x0f) != K_CONST && rd32(c + 4) >= nMem) return 0;
				if (((w >> 12) & 0x0f) != K_CONST && rd32(c + 8) >= nMem) return 0;
			}
			counted += n;
			cs = c;
		}
		if (counted != achConds) return 0;
		conds += counted;
		pos += achBytes(a);
	}
	if (conds != nConds || pos != size) return 0;

	if (vm) {
		vm->plain = p + HEADER_SIZE;
		vm->mod = vm->plain + nPlain * PLAIN_SIZE;
		vm->achStart = vm->mod + nMod * MOD_SIZE;
		vm->nPlain = (uint16_t)nPlain;
		vm->nMod = (uint16_t)nMod;
		vm->nAch = (uint16_t)nAch;
		vm->nConds = nConds;
	}
	return nMem * 8 + nConds * 4 + align4(nMem) + align4(nAch);
}

uint32_t AchVm_StateSize(const void *program, uint32_t size) {
	return checkProgram((const uint8_t *)program, size, 0);
}

int AchVm_Load(AchVm *vm, const void *program, uint32_t size, void *state, uint32_t stateSize,
               const uint8_t *ram, uint32_t ramSize) {
	uint32_t need = checkProgram((const uint8_t *)program, size, vm);
	if (need == 0) return ACHVM_E_FORMAT;
	if (need > stateSize || ((uintptr_t)state & 3)) return ACHVM_E_SPACE;

	uint32_t nMem = vm->nPlain + vm->nMod;
	uint32_t *s = (uint32_t *)state;
	for (uint32_t i = 0; i < need / 4; i++) s[i] = 0;
	vm->memValue = s;
	vm->memPrior = s + nMem;
	vm->hits = s + nMem * 2;
	vm->memChanged = (uint8_t *)(vm->hits + vm->nConds);
	vm->achState = vm->memChanged + align4(nMem);

	vm->ram = ram;
	vm->ramSize = ramSize;
	vm->nextAch = vm->achStart;
	vm->nextHit = 0;
	vm->nextIndex = 0;
	vm->passStage = 0;
	vm->memNext = 0;
	vm->cur.inAchievement = 0;
	vm->rounds = 0;
	vm->triggered = 0;
	return ACHVM_OK;
}

int AchVm_Run(AchVm *vm, int (*keepGoing)(void *ud), AchVm_Triggered onTriggered, void *ud) {
	if (vm->nAch == 0) return 0;
	if (vm->passStage == 0) {
		vm->memNext = 0;
		vm->passStage = 1;
	}
	if (vm->passStage == 1) {
		if (!updateMemrefs(vm, keepGoing, ud)) return 0;
		vm->passStage = 2;
	}
	for (;;) {
		if (!runAchievement(vm, onTriggered, keepGoing, ud)) return 0;
		const uint8_t *a = vm->nextAch;
		vm->nextHit += rd16(a + 6);
		vm->nextAch = a + achBytes(a);
		if (++vm->nextIndex == vm->nAch) {
			vm->nextIndex = 0;
			vm->nextAch = vm->achStart;
			vm->nextHit = 0;
			vm->passStage = 0;
			vm->rounds++;
			return 1;
		}
		if (keepGoing && !keepGoing(ud)) return 0;
	}
}

uint32_t AchVm_AchievementId(const AchVm *vm, uint16_t i) {
	const uint8_t *a = vm->achStart;
	while (i-- > 0) a += achBytes(a);
	return rd32(a);
}

int AchVm_SetUnlocked(AchVm *vm, uint32_t id) {
	const uint8_t *a = vm->achStart;
	for (uint16_t i = 0; i < vm->nAch; i++, a += achBytes(a)) {
		if (rd32(a) == id) {
			vm->achState[i] = ACHVM_TRIGGERED;
			return 1;
		}
	}
	return 0;
}
