#include <stdio.h>
#include <stdint.h>

/* Defined in original.s and new.s */
extern int32_t original_clamp(int32_t r0, uint16_t r1);
extern int32_t new_clamp(int32_t r0, uint16_t r1);

static int pass = 0;
static int fail = 0;

static void check(const char *label,
                  int32_t r0, uint16_t r1,
                  int32_t exp_orig, int32_t exp_new)
{
    int32_t got_orig = original_clamp(r0, r1);
    int32_t got_new  = new_clamp(r0, r1);

    int ok_o = (got_orig == exp_orig);
    int ok_n = (got_new  == exp_new);

    printf("%-45s R0=%-10d R1=%u\n", label, r0, r1);
    printf("  ORIG  exp=%11d  got=%11d  %s\n", exp_orig, got_orig, ok_o ? "PASS" : "FAIL <<<");
    printf("  NEW   exp=%11d  got=%11d  %s\n", exp_new,  got_new,  ok_n ? "PASS" : "FAIL <<<");
    printf("\n");

    if (ok_o) pass++; else fail++;
    if (ok_n) pass++; else fail++;
}

int main(void)
{
    /* ── R1 = 1 ──────────────────────────────────────────────────────────
     *   pos_clamp  =  1 << 15  =  32768
     *   orig_floor = -32768
     *   new_floor  = -(1 * 0xA666) = -42598
     * ──────────────────────────────────────────────────────────────────── */
    uint16_t R1 = 1;
    int32_t  pos      =  32768;
    int32_t  orig_neg = -32768;
    int32_t  new_neg  = -42598;

    printf("=== R1=%u  pos=%d  orig_floor=%d  new_floor=%d ===\n\n",
           R1, pos, orig_neg, new_neg);

    check("in-range: R0=0",
           0,          R1,  0,         0);
    check("in-range: R0=1000",
           1000,       R1,  1000,      1000);
    check("in-range: R0=-1000",
          -1000,       R1, -1000,     -1000);

    check("R0 == pos_clamp (at boundary)",
           pos,        R1,  pos,       pos);
    check("R0 == pos_clamp+1 (just over high)",
           pos+1,      R1,  pos,       pos);
    check("R0 >> pos_clamp (far over high)",
           999999,     R1,  pos,       pos);

    check("R0 == orig_floor (at orig low boundary)",
           orig_neg,   R1,  orig_neg,  orig_neg);
    check("R0 == orig_floor-1 [KEY DIFF: orig clamps, new passes]",
           orig_neg-1, R1,  orig_neg,  orig_neg-1);
    check("R0 == -37000 [KEY DIFF: between floors]",
          -37000,      R1,  orig_neg, -37000);
    check("R0 == new_floor (at new low boundary)",
           new_neg,    R1,  orig_neg,  new_neg);
    check("R0 == new_floor-1 [both clamp, different values]",
           new_neg-1,  R1,  orig_neg,  new_neg);
    check("R0 << both floors (far below)",
          -999999,     R1,  orig_neg,  new_neg);

    /* ── R1 = 2 ──────────────────────────────────────────────────────────
     *   pos_clamp  = 65536
     *   orig_floor = -65536
     *   new_floor  = -(2 * 0xA666) = -85196
     * ──────────────────────────────────────────────────────────────────── */
    R1       = 2;
    pos      =  65536;
    orig_neg = -65536;
    new_neg  = -85196;

    printf("=== R1=%u  pos=%d  orig_floor=%d  new_floor=%d ===\n\n",
           R1, pos, orig_neg, new_neg);

    check("R1=2 in-range",
           0,          R1,  0,         0);
    check("R1=2 above high",
           999999,     R1,  pos,       pos);
    check("R1=2 between floors [KEY DIFF]",
           orig_neg-1, R1,  orig_neg,  orig_neg-1);
    check("R1=2 below new_floor",
           new_neg-1,  R1,  orig_neg,  new_neg);

    /* ── R1 = 0 edge case ───────────────────────────────────────────────── */
    R1 = 0;
    printf("=== R1=0 edge case ===\n\n");
    check("R1=0, R0=1000  (pos clamp=0)",
           1000,  R1,  0,  0);
    check("R1=0, R0=-1000 (neg clamp=0)",
          -1000,  R1,  0,  0);

    /* ── Result ─────────────────────────────────────────────────────────── */
    printf("============================================\n");
    printf("  %d passed,  %d failed\n", pass, fail);
    printf("============================================\n");
    return (fail > 0) ? 1 : 0;
}
