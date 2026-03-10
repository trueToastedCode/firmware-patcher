.syntax unified
    .thumb
    .text

@ int32_t new_clamp(int32_t r0, uint16_t r1);
@ r0 = input value
@ r1 = the uint16 limit word
@ returns clamped value in r0

    .global new_clamp
    .thumb_func
new_clamp:
    @ CMP.W R0, R1,LSL#15
    CMP.W   r0, r1, LSL #15
    BLE     loc_new_neg_path

    @ High clamp: identical to original
    LSLS    r0, r1, #15
    BX      lr

loc_new_neg_path:
    @ loc_8006898 equivalent
    @ MOVW R2, #0xA666
    MOVW    r2, #0xA666
    @ MUL.W R2, R1, R2
    MUL.W   r2, r1, r2
    @ NEGS R2, R2
    NEGS    r2, r2
    @ CMP R0, R2
    CMP     r0, r2
    @ BGE → in range, store r0 unchanged
    BGE     loc_new_in_range

    @ clamp to new floor
    @ MOV R0, R2
    MOV     r0, r2
    @ MOV.W R2, R2,LSR#15  (dead write — computed but unused, replicate anyway)
    MOV.W   r2, r2, LSR #15
    BX      lr

loc_new_in_range:
    BX      lr
