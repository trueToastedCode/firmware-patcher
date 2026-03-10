.syntax unified
    .thumb
    .text

@ int32_t original_clamp(int32_t r0, uint16_t r1);
@ r0 = input value
@ r1 = the uint16 limit word (word_200003D6)
@ returns clamped value in r0

    .global original_clamp
    .thumb_func
original_clamp:
    @ r1 already has the uint16 value (zero-extended by ABI)
    @ Replicate: CMP.W R0, R1,LSL#15
    CMP.W   r0, r1, LSL #15
    BLE     loc_neg_check

    @ High clamp: R0 = R1 << 15
    LSLS    r0, r1, #15
    BX      lr

loc_neg_check:
    @ Replicate: NEGS R2, R1 / CMP.W R0, R2,LSL#15
    NEGS    r2, r1
    CMP.W   r0, r2, LSL #15
    BGE     loc_in_range

    @ Low clamp: R0 = -(R1 << 15)
    LSLS    r0, r1, #15
    NEGS    r0, r0
    BX      lr

loc_in_range:
    @ In range: r0 unchanged
    BX      lr
