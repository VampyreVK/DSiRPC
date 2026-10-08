/*
 * dsirpc_offline.c - DSiRPC's addition to rcheevos: turns the achievements
 * loaded in an rc_runtime_t into the program the console runs in offline
 * play (DSiRPC's core/offline.py puts it in the set file; the console's
 * interpreter is nds-bootstrap's rpcprobe/probe_ach_vm.c, which describes
 * the format).
 *
 * rcheevos parses the achievements itself, so the console runs exactly what
 * rcheevos would: the same shared memory references, the same AddSource /
 * AddAddress / Remember chains (rcheevos 12 turns them into "modified
 * memrefs"), and the conditions in the order rcheevos evaluates them. Left
 * out: achievements that need floating point (the console's ARM7 has no
 * FPU) and the very rare ones with more than 255 groups or 65535 conditions;
 * dsirpc_offline_supported() says which.
 *
 * Built into the rcheevos library DSiRPC ships, with rcheevos' internal
 * headers (third_party/rcheevos/README.md). MIT, like rcheevos.
 */

#include "rc_internal.h"
#include "rc_runtime.h"

#include <stdlib.h>
#include <string.h>

#define DO_VERSION 2

typedef struct {
  const void** ptrs;          /* memref pointers, in the order they get indexes */
  uint32_t count;
  uint32_t capacity;
} ptr_list_t;

typedef struct {
  uint8_t* out;
  uint32_t size;
  uint32_t pos;
} writer_t;

static int ptr_index(const ptr_list_t* list, const void* p) {
  uint32_t i;
  for (i = 0; i < list->count; i++)
    if (list->ptrs[i] == p)
      return (int)i;
  return -1;
}

static int ptr_add(ptr_list_t* list, const void* p) {
  if (list->count == list->capacity) {
    uint32_t cap = list->capacity ? list->capacity * 2 : 64;
    const void** n = (const void**)realloc((void*)list->ptrs, cap * sizeof(void*));
    if (!n)
      return 0;
    list->ptrs = n;
    list->capacity = cap;
  }
  list->ptrs[list->count++] = p;
  return 1;
}

static void put8(writer_t* w, uint8_t v) {
  if (w->pos < w->size)
    w->out[w->pos] = v;
  w->pos++;
}

static void put16(writer_t* w, uint16_t v) {
  put8(w, (uint8_t)v);
  put8(w, (uint8_t)(v >> 8));
}

static void put32(writer_t* w, uint32_t v) {
  put16(w, (uint16_t)v);
  put16(w, (uint16_t)(v >> 16));
}

static int size_is_float(uint8_t size) {
  switch (size) {
    case RC_MEMSIZE_FLOAT:
    case RC_MEMSIZE_MBF32:
    case RC_MEMSIZE_MBF32_LE:
    case RC_MEMSIZE_FLOAT_BE:
    case RC_MEMSIZE_DOUBLE32:
    case RC_MEMSIZE_DOUBLE32_BE:
    case RC_MEMSIZE_VARIABLE:
      return 1;
    default:
      return 0;
  }
}

/* -- support checks ---------------------------------------------------------- */

/* An operand on its own (not what its memref is built from) */
static int operand_ok(const rc_operand_t* op) {
  switch (op->type) {
    case RC_OPERAND_CONST:
      return 1;
    case RC_OPERAND_FP:
    case RC_OPERAND_FUNC:
      return 0;
    case RC_OPERAND_RECALL:
      if (!rc_operand_type_is_memref(op->memref_access_type))
        return op->memref_access_type == RC_OPERAND_CONST;
      break;
    default:
      break;
  }
  return !size_is_float(op->size);
}

static const rc_memref_t* operand_memref(const rc_operand_t* op) {
  if (op->type == RC_OPERAND_CONST || op->type == RC_OPERAND_FP || op->type == RC_OPERAND_FUNC)
    return NULL;
  if (op->type == RC_OPERAND_RECALL && !rc_operand_type_is_memref(op->memref_access_type))
    return NULL;
  return op->value.memref; /* NULL for a recall of nothing */
}

/* A memref on its own */
static int memref_ok(const rc_memref_t* m) {
  if (m->value.type == RC_VALUE_TYPE_FLOAT || size_is_float(m->value.size))
    return 0;
  if (m->value.memref_type == RC_MEMREF_TYPE_MODIFIED_MEMREF) {
    const rc_modified_memref_t* mm = (const rc_modified_memref_t*)m;
    return operand_ok(&mm->parent) && operand_ok(&mm->modifier);
  }
  return m->value.memref_type == RC_MEMREF_TYPE_MEMREF;
}

/* Adds the memref, and every memref it's built from, to list (each once).
 * Returns 0 if any of them can't run on the console. Not recursive: an
 * AddSource chain is a chain of memrefs hundreds long. */
static int add_memref_tree(ptr_list_t* list, const rc_memref_t* root) {
  ptr_list_t todo = { NULL, 0, 0 };
  int ok = 1;
  if (!root)
    return 1;
  ptr_add(&todo, root);
  while (todo.count) {
    const rc_memref_t* m = (const rc_memref_t*)todo.ptrs[--todo.count];
    if (ptr_index(list, m) >= 0)
      continue;
    if (!ptr_add(list, m))
      ok = 0;
    if (!memref_ok(m))
      ok = 0;
    if (m->value.memref_type == RC_MEMREF_TYPE_MODIFIED_MEMREF) {
      const rc_modified_memref_t* mm = (const rc_modified_memref_t*)m;
      const rc_memref_t* a = operand_memref(&mm->parent);
      const rc_memref_t* b = operand_memref(&mm->modifier);
      if (a && !ptr_add(&todo, a)) ok = 0;
      if (b && !ptr_add(&todo, b)) ok = 0;
    }
  }
  free((void*)todo.ptrs);
  return ok;
}

/* Adds the memrefs a condset uses to list. Returns 0 if it can't run on the console. */
static int add_condset(ptr_list_t* list, rc_condset_t* condset) {
  rc_condition_t* c;
  int ok = 1;
  if (!condset)
    return 1;
  for (c = condset->conditions; c; c = c->next) {
    if (c->type > RC_CONDITION_OR_NEXT || c->oper > RC_OPERATOR_SUB)
      ok = 0;
    if (!operand_ok(&c->operand1) || !add_memref_tree(list, operand_memref(&c->operand1)))
      ok = 0;
    if (c->oper != RC_OPERATOR_NONE &&
        (!operand_ok(&c->operand2) || !add_memref_tree(list, operand_memref(&c->operand2))))
      ok = 0;
  }
  return ok;
}

static int trigger_supported(rc_trigger_t* trigger) {
  ptr_list_t list = { NULL, 0, 0 };
  rc_condset_t* cs;
  int ok;
  if (!trigger)
    return 0;
  ok = add_condset(&list, trigger->requirement);
  for (cs = trigger->alternative; cs; cs = cs->next)
    if (!add_condset(&list, cs))
      ok = 0;
  free((void*)list.ptrs);
  return ok;
}

/* -- writing ---------------------------------------------------------------- */

/* How a recall reads its memref: 0 value, 1 delta, 2 prior (rc_get_memref_value_value) */
static uint8_t read_code(uint8_t access) {
  return access == RC_OPERAND_DELTA ? 1 : access == RC_OPERAND_PRIOR ? 2 : 0;
}

/* An operand as (kind, size, read, value): kind is RC_OPERAND_*, value a
 * memref index or the constant. A recall of nothing is the constant 0 and a
 * recall of a constant is that constant (what rc_evaluate_operand does). */
typedef struct {
  uint8_t kind, size, read;
  uint32_t value;
} operand_out_t;

static int encode_operand(const ptr_list_t* index, const rc_operand_t* op, operand_out_t* out) {
  int i;
  out->kind = op->type;
  out->size = op->size;
  out->read = 0;
  out->value = 0;

  switch (op->type) {
    case RC_OPERAND_CONST:
      out->value = op->value.num;
      return 1;
    case RC_OPERAND_RECALL:
      if (!rc_operand_type_is_memref(op->memref_access_type)) {
        out->kind = RC_OPERAND_CONST;
        out->value = op->value.num;
        return 1;
      }
      if (!op->value.memref) {
        out->kind = RC_OPERAND_CONST;
        return 1;
      }
      out->read = read_code(op->memref_access_type);
      break;
    default:
      break;
  }
  i = ptr_index(index, op->value.memref);
  if (i < 0)
    return 0;
  out->value = (uint32_t)i;
  return 1;
}

static const rc_operand_t none_operand = { { 0 }, RC_OPERAND_CONST, 0, 0, 0 };

static int put_condset(writer_t* w, const ptr_list_t* index, rc_condset_t* condset, uint32_t* n_conds) {
  rc_condition_t* c = rc_condset_get_conditions(condset);
  uint32_t evaluated = 0, i;
  if (c)
    evaluated = condset->num_pause_conditions + condset->num_reset_conditions +
                condset->num_hittarget_conditions + condset->num_measured_conditions +
                condset->num_other_conditions;

  put16(w, condset->num_pause_conditions);
  put16(w, condset->num_reset_conditions);
  put16(w, condset->num_hittarget_conditions);
  put16(w, condset->num_measured_conditions);
  put16(w, condset->num_other_conditions);
  put16(w, 0);

  /* the conditions, in rcheevos' evaluation order */
  for (i = 0; i < evaluated; i++, c++) {
    operand_out_t a, b;
    int same_delta;
    if (!encode_operand(index, &c->operand1, &a) ||
        !encode_operand(index, c->oper == RC_OPERATOR_NONE ? &none_operand : &c->operand2, &b))
      return 0;
    /* rcheevos compares a memref with its own delta by the operator alone
     * when it hasn't changed, even if the two sides read different bits of
     * it (rc_test_condition_compare_memref_to_delta_transformed) */
    same_delta = (c->optimized_comparator == RC_PROCESSING_COMPARE_MEMREF_TO_DELTA ||
                  c->optimized_comparator == RC_PROCESSING_COMPARE_MEMREF_TO_DELTA_TRANSFORMED ||
                  c->optimized_comparator == RC_PROCESSING_COMPARE_DELTA_TO_MEMREF ||
                  c->optimized_comparator == RC_PROCESSING_COMPARE_DELTA_TO_MEMREF_TRANSFORMED);
    put32(w, (uint32_t)c->type | ((uint32_t)c->oper << 4) | ((uint32_t)a.kind << 8) |
             ((uint32_t)b.kind << 12) | ((uint32_t)a.size << 16) | ((uint32_t)b.size << 21) |
             ((uint32_t)a.read << 27) | ((uint32_t)b.read << 29) | ((uint32_t)same_delta << 31));
    put32(w, a.value);
    put32(w, b.value);
    put32(w, c->required_hits);
  }
  *n_conds += evaluated;
  return 1;
}

static uint32_t count_condsets(rc_trigger_t* t) {
  rc_condset_t* cs;
  uint32_t n = t->requirement ? 1 : 0;
  for (cs = t->alternative; cs; cs = cs->next)
    n++;
  return n;
}

static int achievement_fits(rc_trigger_t* t) {
  rc_condset_t* cs;
  uint32_t conds = 0;
  if (count_condsets(t) > 255)
    return 0;
  for (cs = t->requirement; cs; cs = NULL)
    conds += cs->num_pause_conditions + cs->num_reset_conditions + cs->num_hittarget_conditions +
             cs->num_measured_conditions + cs->num_other_conditions;
  for (cs = t->alternative; cs; cs = cs->next)
    conds += cs->num_pause_conditions + cs->num_reset_conditions + cs->num_hittarget_conditions +
             cs->num_measured_conditions + cs->num_other_conditions;
  return conds <= 0xFFFF;
}

static int usable(rc_trigger_t* t) {
  return t && trigger_supported(t) && achievement_fits(t);
}

RC_EXPORT int RC_CCONV dsirpc_offline_supported(rc_runtime_t* runtime, uint32_t id) {
  uint32_t i;
  for (i = 0; i < runtime->trigger_count; i++)
    if (runtime->triggers[i].id == id && runtime->triggers[i].trigger)
      return usable(runtime->triggers[i].trigger);
  return 0;
}

/*
 * Writes the program for the runtime's usable achievements into out (size
 * bytes) and returns how many bytes it takes (call again with a bigger
 * buffer if that's more than size), or -1 on failure. The format is described
 * in nds-bootstrap's rpcprobe/probe_ach_vm.c, which runs it.
 */
RC_EXPORT int RC_CCONV dsirpc_offline_compile(rc_runtime_t* runtime, uint8_t* out, uint32_t size) {
  ptr_list_t used = { NULL, 0, 0 }, index = { NULL, 0, 0 };
  writer_t w = { out, size, 0 };
  rc_memref_list_t* plain;
  rc_modified_memref_list_t* modified;
  uint32_t i, n_plain = 0, n_mod = 0, n_ach = 0, n_conds = 0;
  uint32_t counts_pos;
  int ok = 1;

  /* which memrefs the usable achievements use */
  for (i = 0; i < runtime->trigger_count; i++) {
    rc_trigger_t* t = runtime->triggers[i].trigger;
    rc_condset_t* cs;
    if (!usable(t))
      continue;
    add_condset(&used, t->requirement);
    for (cs = t->alternative; cs; cs = cs->next)
      add_condset(&used, cs);
    n_ach++;
  }

  /* index them in the runtime's update order: plain ones, then modified ones */
  for (plain = &runtime->memrefs->memrefs; plain; plain = plain->next) {
    rc_memref_t* m = plain->items;
    for (i = 0; i < plain->count; i++, m++)
      if (ptr_index(&used, m) >= 0) {
        ptr_add(&index, m);
        n_plain++;
      }
  }
  for (modified = &runtime->memrefs->modified_memrefs; modified; modified = modified->next) {
    rc_modified_memref_t* m = modified->items;
    for (i = 0; i < modified->count; i++, m++)
      if (ptr_index(&used, &m->memref) >= 0) {
        ptr_add(&index, &m->memref);
        n_mod++;
      }
  }
  if (index.count != used.count || n_plain > 0xFFFF || n_mod > 0xFFFF || n_ach > 0xFFFF)
    ok = 0;

  put32(&w, DO_VERSION);
  put16(&w, (uint16_t)n_plain);
  put16(&w, (uint16_t)n_mod);
  put16(&w, (uint16_t)n_ach);
  put16(&w, 0);
  counts_pos = w.pos;
  put32(&w, 0); /* conditions, filled in below */

  for (i = 0; ok && i < n_plain; i++) {
    const rc_memref_t* m = (const rc_memref_t*)index.ptrs[i];
    put32(&w, m->address);
    put8(&w, m->value.size);
    put8(&w, m->value.type);
    put16(&w, 0);
  }
  for (i = n_plain; ok && i < n_plain + n_mod; i++) {
    const rc_modified_memref_t* m = (const rc_modified_memref_t*)index.ptrs[i];
    operand_out_t ops[2];
    int j;
    put8(&w, m->memref.value.size);
    put8(&w, m->memref.value.type);
    put8(&w, m->modifier_type);
    put8(&w, 0);
    if (!encode_operand(&index, &m->parent, &ops[0]) || !encode_operand(&index, &m->modifier, &ops[1]))
      ok = 0;
    for (j = 0; j < 2; j++) {
      /* (a modified memref can use one that's updated after it: a Remember
       * from a PauseIf further on. rcheevos then reads last frame's value,
       * and so does the console.) */
      put8(&w, ops[j].kind);
      put8(&w, ops[j].size);
      put8(&w, ops[j].read);
      put8(&w, 0);
      put32(&w, ops[j].value);
    }
  }

  for (i = 0; ok && i < runtime->trigger_count; i++) {
    rc_trigger_t* t = runtime->triggers[i].trigger;
    rc_condset_t* cs;
    uint32_t before;
    if (!usable(t))
      continue;
    put32(&w, runtime->triggers[i].id);
    put8(&w, (uint8_t)count_condsets(t));
    put8(&w, t->requirement ? 1 : 0);
    put16(&w, 0); /* its conditions, filled in below */
    before = n_conds;
    if (t->requirement && !put_condset(&w, &index, t->requirement, &n_conds))
      ok = 0;
    for (cs = t->alternative; ok && cs; cs = cs->next)
      if (!put_condset(&w, &index, cs, &n_conds))
        ok = 0;
    if (ok) {
      /* write the count back into the achievement's header */
      uint32_t at = w.pos - (n_conds - before) * 16 - count_condsets(t) * 12 - 2;
      if (at + 2 <= size) {
        out[at] = (uint8_t)(n_conds - before);
        out[at + 1] = (uint8_t)((n_conds - before) >> 8);
      }
    }
  }

  if (counts_pos + 4 <= size) {
    out[counts_pos] = (uint8_t)n_conds;
    out[counts_pos + 1] = (uint8_t)(n_conds >> 8);
    out[counts_pos + 2] = (uint8_t)(n_conds >> 16);
    out[counts_pos + 3] = (uint8_t)(n_conds >> 24);
  }

  free((void*)used.ptrs);
  free((void*)index.ptrs);
  return ok ? (int)w.pos : -1;
}
