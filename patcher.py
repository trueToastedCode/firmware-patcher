#!/usr/bin/python3
#
# NGFW Patcher
# Copyright (C) 2022 Daljeet Nandha
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#
# Based on: https://github.com/BotoX/xiaomi-m365-firmware-patcher/blob/master/patcher.py
# I introduced mods into the patcher either by studying existing patchers or creating new mods myself.
# All original authors are mentioned in the function comments!
#

from binascii import hexlify, unhexlify
import struct
import keystone
import capstone

# https://web.eecs.umich.edu/~prabal/teaching/eecs373-f10/readings/ARMv7-M_ARM.pdf
MOVW_T3_IMM = [*[None]*5, 11, *[None]*6, 15, 14, 13, 12, None, 10, 9, 8, *[None]*4, 7, 6, 5, 4, 3, 2, 1, 0]
MOVS_T1_IMM = [*[None]*8, 7, 6, 5, 4, 3, 2, 1, 0]


def PatchImm(data, ofs, size, imm, signature):
    assert size % 2 == 0, 'size must be power of 2!'
    assert len(signature) == size * 8, 'signature must be exactly size * 8 long!'
    imm = int.from_bytes(imm, 'little')
    sfmt = '<' + 'H' * (size // 2)

    sigs = [signature[i:i + 16][::-1] for i in range(0, len(signature), 16)]
    orig = data[ofs:ofs+size]
    words = struct.unpack(sfmt, orig)

    patched = []
    for i, word in enumerate(words):
        for j in range(16):
            imm_bitofs = sigs[i][j]
            if imm_bitofs is None:
                continue

            imm_mask = 1 << imm_bitofs
            word_mask = 1 << j

            if imm & imm_mask:
                word |= word_mask
            else:
                word &= ~word_mask
        patched.append(word)

    packed = struct.pack(sfmt, *patched)
    data[ofs:ofs+size] = packed
    return (orig, packed)


class SignatureException(Exception):
    pass


def FindPattern(data, signature, mask=None, start=None, maxit=None):
    sig_len = len(signature)
    if start is None:
        start = 0
    stop = len(data) - len(signature)
    if maxit is not None:
        stop = start + maxit

    if mask:
        assert sig_len == len(mask), 'mask must be as long as the signature!'
        for i in range(sig_len):
            signature[i] &= mask[i]

    for i in range(start, stop):
        matches = 0

        while signature[matches] is None or signature[matches] == (data[i + matches] & (mask[matches] if mask else 0xFF)):
            matches += 1
            if matches == sig_len:
                return i

    raise SignatureException('Pattern not found!')


class FirmwarePatcher():
    def __init__(self, data):
        self.data = bytearray(data)
        self.ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)
        self.cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

    def remove_kers(self):
        '''
        Creator: NandTek
        Description: Alternate (improved) version of No Kers Mod
        '''
        sig = [0x00, 0xeb, 0x80, 0x00, 0x80, 0x00, 0x80, 0x0a]
        ofs = FindPattern(self.data, sig) + 6
        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm('MOVS R0, #0')[0])
        self.data[ofs:ofs+2] = post
        return [("no_kers", hex(ofs), pre.hex(), post.hex())]

    def remove_autobrake(self):
        '''
        Creator: BotoX
        '''
        sig = [None, 0x68, 0x42, 0xf6, 0x6e, 0x0c]
        ofs = FindPattern(self.data, sig) + 2
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('MOVW IP, #0xffff')[0])
        self.data[ofs:ofs+4] = post
        return [("no_autobrake", hex(ofs), pre.hex(), post.hex())]

    def remove_charging_mode(self):
        '''
        Creator: BotoX
        '''
        sig = [0xB8, 0xF8, 0x12, 0x00, 0x20, 0xB1, 0x84, 0xF8, 0x3A]
        ofs = FindPattern(self.data, sig) + 4
        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm('NOP')[0])
        self.data[ofs:ofs+2] = post
        return [("no_charge", hex(ofs), pre.hex(), post.hex())]

    def current_raising_coeff(self, coeff):
        '''
        Creator: SH
        '''
        ret = []

        # TODO: all trying to find same position
        reg = 0
        try:
            sig = [0x95, 0xf8, 0x34, None, None, 0x21, 0x4f, 0xf4, 0x96, 0x70]
            ofs = FindPattern(self.data, sig) + 6
        except SignatureException:
            try:
                # 242
                sig = [0x85, 0xf8, 0x40, 0x60, 0x95, 0xf8, 0x34, 0x30]
                ofs = FindPattern(self.data, sig) + 0x8
                reg = 2
            except SignatureException:
                # 016
                sig = [0x00, 0xe0, 0x2e, 0x72, 0x95, 0xf8, 0x34, 0xc0]
                ofs = FindPattern(self.data, sig) + 0xa
                reg = 1

        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('MOVW R{}, #{}'.format(reg, coeff))[0])
        self.data[ofs:ofs+4] = post
        ret.append(["crc", hex(ofs), pre.hex(), post.hex()])

        return ret

    def speed_limit_drive(self, kmh):
        '''
        Creator: BotoX
        '''
        ret = []

        # TODO: first two trying to find same position
        try:
            sig = [0x95, 0xf8, 0x34, None, None, 0x21, 0x4f, 0xf4, 0x96, 0x70]
            ofs = FindPattern(self.data, sig) + 4
            reg = 1
        except SignatureException:
            try:
                # 016
                sig = [0x00, 0xe0, 0x2e, 0x72, 0x95, 0xf8, 0x34, 0xc0]
                ofs = FindPattern(self.data, sig) + 0x8
                reg = 2
            except SignatureException:
                # 242
                sig = [0xa1, 0x85, 0x0f, 0x20, 0x20, 0x84]
                ofs = FindPattern(self.data, sig) + 2
                reg = 0

        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm('MOVS R{}, #{}'.format(reg, kmh))[0])
        self.data[ofs:ofs+2] = post
        ret.append(["sl_drive", hex(ofs), pre.hex(), post.hex()])

        return ret

    def speed_limit_speed(self, kmh):
        '''
        Creator: SH
        '''
        ret = []

        # TODO: all trying to find same position
        reg = 8
        try:
            # for 319 this moved to the top and 'movs' became 'mov.w'
            sig = [0x95, 0xf8, 0x34, None, None, 0x21, 0x4f, 0xf4, 0x96, 0x70]
            ofs = FindPattern(self.data, sig) + 0xe
        except SignatureException:
            try:
                # 242
                sig = [0x85, 0xf8, 0x40, 0x60, 0x95, 0xf8, 0x34, 0x30]
                ofs = FindPattern(self.data, sig) + 0xc
                reg = 12
            except SignatureException:
                # 016
                sig = [0x00, 0xe0, 0x2e, 0x72, 0x95, 0xf8, 0x34, 0xc0]
                ofs = FindPattern(self.data, sig) + 0x12
        pre = self.data[ofs:ofs+4]
        assert pre[-1] == reg
        post = bytes(self.ks.asm('MOVW R{}, #{}'.format(reg, kmh))[0])
        self.data[ofs:ofs+4] = post
        ret.append(["sl_speed", hex(ofs), pre.hex(), post.hex()])

        return ret

    def speed_limit_pedo(self, kmh):
        '''
        Creator: NandTek
        Description: Speed limit of pedestrian mode
        '''
        ret = []

        # TODO: both trying to find same position
        try:
            sig = [0x4f, 0xf0, 0x05, None, 0x01, None, 0x02, 0xd1]
            ofs = FindPattern(self.data, sig)
        except SignatureException:
            # 016
            sig = [0x00, 0xe0, 0x2e, 0x72, 0x95, 0xf8, 0x34, 0xc0]
            ofs = FindPattern(self.data, sig) + 0x16

        pre = self.data[ofs:ofs+4]
        reg = pre[-1]
        post = bytes(self.ks.asm('MOVW R{}, #{}'.format(reg, kmh))[0])
        self.data[ofs:ofs+4] = post
        ret.append(["sl_pedo", hex(ofs), pre.hex(), post.hex()])

        return ret

    def motor_start_speed(self, kmh):
        '''
        Creator: BotoX
        '''
        val = struct.pack('<H', round(kmh * 345))
        sig = [0x01, 0x68, 0x40, 0xF2, 0xBD, 0x62]
        ofs = FindPattern(self.data, sig) + 2
        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        return [("mss", hex(ofs), pre.hex(), post.hex())]

    def wheel_speed_const(self, factor, def1=345, def2=1387):
        '''
        Creator: BotoX
        '''
        ret = []

        val1 = struct.pack('<H', round(def1/factor))
        val2 = struct.pack('<H', round(def2*factor))

        sig = [0xB4, 0xF9, None, 0x00, 0x40, 0xF2, 0x59, 0x11, 0x48, 0x43]
        ofs = FindPattern(self.data, sig) + 4
        pre, post = PatchImm(self.data, ofs, 4, val1, MOVW_T3_IMM)
        ret.append(["wheel_speed_const_0", hex(ofs), pre.hex(), post.hex()])

        ofs -= 0x18
        pre = self.data[ofs+2:ofs+4]
        if pre[0] == 0x59 and pre[1] == 0x11:  # not in 247
            pre, post = PatchImm(self.data, ofs, 4, val1, MOVW_T3_IMM)
            ret.append(["wheel_speed_const_1", hex(ofs), pre.hex(), post.hex()])

        sig = [0x60, 0x60, 0x60, 0x68, 0x40, 0xF2, 0x6B, 0x51, 0x48, 0x43]
        ofs = FindPattern(self.data, sig) + 4
        pre, post = PatchImm(self.data, ofs, 4, val2, MOVW_T3_IMM)
        ret.append(["wheel_other_const", hex(ofs), pre.hex(), post.hex()])

        return ret

    def ampere_speed(self, amps, force=True):
        '''
        Creator: SH
        '''
        ret = []

        val = struct.pack('<H', amps)

        if force:
            try:
                sig = [0x13, 0xD2, None, 0x85, None, 0xE0, None, 0x8E]
                ofs = FindPattern(self.data, sig) + 8
            except SignatureException:
                try:
                    # 242
                    sig = [0x88, 0x42, 0x01, 0xd2, 0xa0, 0x85, 0x00, 0xe0]
                    ofs = FindPattern(self.data, sig)
                except SignatureException:
                    # 016
                    sig = [0x98, 0x42, 0x01, 0xd2, 0xe0, 0x85, 0x00, 0xe0]
                    ofs = FindPattern(self.data, sig)

            pre = self.data[ofs:ofs+2]
            post = bytes(self.ks.asm('CMP R0, R0')[0])
            self.data[ofs:ofs+2] = post
            ret.append(["amp_speed_nop", hex(ofs), pre.hex(), post.hex()])

        try:
            sig = [None, 0x21, 0x4f, 0xf4, 0x96, 0x70]
            ofs = FindPattern(self.data, sig) + 6
        except SignatureException:
            try:
                # 242
                sig = [0x85, 0xf8, 0x40, 0x60, 0x95, 0xf8, 0x34, 0x30]
                ofs = FindPattern(self.data, sig) + 0x10
            except SignatureException:
                # 016
                sig = [0x00, 0xe0, 0x2e, 0x72, 0x95, 0xf8, 0x34, 0xc0]
                ofs = FindPattern(self.data, sig) + 0xe

        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append(["amp_speed", hex(ofs), pre.hex(), post.hex()])

        return ret

    def ampere_drive(self, amps, force=True):
        '''
        Creator: BotoX
        '''
        ret = []

        val = struct.pack('<H', amps)

        try:
            sig = [0x95, 0xf8, 0x40, None, 0x01, None, 0x06, 0xd0, None, 0x8e]
            ofs = FindPattern(self.data, sig) + 0xa
            pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
            ret.append(["amp_drive", hex(ofs), pre.hex(), post.hex()])
            ofs_f = ofs + 4
        except SignatureException:
            try:
                # 016
                sig = [0x95, 0xf8, 0x40, 0xc0, 0xbc, 0xf1, 0x01, 0x0f, 0x05, 0xd0]
                ofs = FindPattern(self.data, sig) + len(sig)
                pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
                ret.append(["amp_drive", hex(ofs), pre.hex(), post.hex()])
                ofs_f = ofs + 4
            except SignatureException:
                # 242: drive has same amps as speed
                sig = [0x88, 0x42, 0x09, 0xd2, 0xa0, 0x85, 0x08, 0xe0]
                ofs_f = FindPattern(self.data, sig)

        if force:
            pre = self.data[ofs_f:ofs_f+2]
            post = bytes(self.ks.asm('CMP R0, R0')[0])
            self.data[ofs_f:ofs_f+2] = post
            ret.append(["amp_drive_nop", hex(ofs_f), pre.hex(), post.hex()])

        return ret

    def ampere_pedo(self, amps, force=True):
        '''
        Creator: NandTek
        Description: Nominal current of pedestrian mode
        '''
        ret = []

        val = struct.pack('<H', amps)

        sig = [None, None, 0x41, 0xf6, 0x58, None, None, None, 0x01, 0xd2]
        ofs = FindPattern(self.data, sig) + 2

        pre, post = PatchImm(self.data, ofs, 4, val, MOVW_T3_IMM)
        ret.append(["amp_pedo", hex(ofs), pre.hex(), post.hex()])

        if force:
            ofs += 4
            pre = self.data[ofs:ofs+2]
            post = bytes(self.ks.asm('CMP R0, R0')[0])
            self.data[ofs:ofs+2] = post
            ret.append(["amp_pedo_nop", hex(ofs), pre.hex(), post.hex()])

        return ret

    def ampere_max(self, amps_pedo, amps_drive, amps_speed):
        '''
        Creator: BotoX/SH
        '''
        ret = []

        #val_pedo = struct.pack('<H', amps_pedo)
        #val_drive = struct.pack('<H', amps_drive)
        #val_speed = struct.pack('<H', amps_speed)

        sig = [0xa4, 0xf8, None, None, 0x4f, 0xf4, 0xfa]
        ofs_p = FindPattern(self.data, sig) + 4

        reg = 0
        try:
            sig = [0x02, 0xd0, 0xa4, 0xf8, 0x22, 0x80, None, 0xe0, 0x61, 0x84, None, 0xe0]
            ofs = FindPattern(self.data, sig)

            b = self.data[ofs_p+3]
            if b == 0x52:  # 247
                reg = 2
                ofs_s = ofs - 6
                ofs_d = ofs + len(sig) + 6
            elif b == 0x53:  # 319
                reg = 3
                ofs_s = ofs - 8
                ofs_d = ofs + len(sig) + 8
            else:
                raise Exception(f"invalid firmware file: {hex(b)}")

            #pre, post = PatchImm(self.data, ofs, 4, val_pedo, MOVW_T3_IMM)
            pre = self.data[ofs_p:ofs_p+4]
            post = bytes(self.ks.asm('MOVW R{},#{}'.format(reg, amps_pedo))[0])
            self.data[ofs_p:ofs_p+4] = post
            ret.append(["amp_max_pedo", hex(ofs_p), pre.hex(), post.hex()])

            #pre, post = PatchImm(self.data, ofs, 4, val_drive, MOVW_T3_IMM)
            pre = self.data[ofs_d:ofs_d+4]
            post = bytes(self.ks.asm('MOVW R{},#{}'.format(reg, amps_drive))[0])
            self.data[ofs_d:ofs_d+4] = post
            ret.append(["amp_max_drive", hex(ofs_d), pre.hex(), post.hex()])
        except SignatureException:
            # 242 / 016
            pre = self.data[ofs_p:ofs_p+4]
            post = bytes(self.ks.asm('MOVW R{},#{}'.format(reg, amps_pedo))[0])
            self.data[ofs_p:ofs_p+4] = post
            ret.append(["amp_max_pedo", hex(ofs_p), pre.hex(), post.hex()])

            try:
                # 242
                sig = [0x95, 0xf8, 0x34, 0x80, 0x4f, 0xf4, 0xfa, 0x43]
                ofs_s = FindPattern(self.data, sig) + 4
                reg = 3  # TODO: cleanup
            except SignatureException:
                # 016
                sig = [0x95, 0xf8, 0x43, 0xc0, 0x46, 0xf6, 0x60, 0x50]
                ofs_d = FindPattern(self.data, sig) + 4

                sig = [0x95, 0xf8, 0x43, 0xc0, 0x4d, 0xf2, 0xd8, 0x60]
                ofs_s = FindPattern(self.data, sig) + 4

                pre = self.data[ofs_d:ofs_d+4]
                post = bytes(self.ks.asm('MOVW R{},#{}'.format(reg, amps_drive))[0])
                self.data[ofs_d:ofs_d+4] = post
                ret.append(["amp_max_drive", hex(ofs_d), pre.hex(), post.hex()])

        #pre, post = PatchImm(self.data, ofs, 4, val_speed, MOVW_T3_IMM)
        pre = self.data[ofs_s:ofs_s+4]
        post = bytes(self.ks.asm('MOVW R{},#{}'.format(reg, amps_speed))[0])
        self.data[ofs_s:ofs_s+4] = post
        ret.append(["amp_max_speed", hex(ofs_s), pre.hex(), post.hex()])

        return ret

    def dpc(self):
        '''
        Creator: SH
        '''
        ret = []
        sig = [0x00, 0x21, 0xa1, 0x71, 0xa2, 0xf8, 0xec, 0x10, 0x63, 0x79]
        ofs = FindPattern(self.data, sig) + 4
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('NOP')[0])
        self.data[ofs:ofs+2] = post
        self.data[ofs+2:ofs+4] = post
        post = self.data[ofs:ofs+4]
        ret.append(["dpc_nop", hex(ofs), pre.hex(), post.hex()])

        sig = [0xa4, 0xf8, 0xe2, None, 0xa4, 0xf8, 0xf0, None, 0xa4, 0xf8, 0xee, None]
        ofs = FindPattern(self.data, sig) + 4

        b = self.data[ofs+3]
        reg = 0
        if b == 0x70:
            reg = 7  # 236 / 319
        elif b == 0x50:
            reg = 5  # 242
        else:
            raise Exception(f"invalid firmware file: {hex(b)}")
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('STRH.W R{}, [R4, #0xEC]'.format(reg))[0])
        self.data[ofs:ofs+4] = post
        ret.append(["dpc_reset", hex(ofs), pre.hex(), post.hex()])

        return ret

    def shutdown_time(self, seconds):
        '''
        Creator: NandTek
        Description: Time to press power button before shutdown
        '''
        delay = int(seconds * 200)
        assert delay.bit_length() <= 12, 'bit length overflow'
        sig = [0x0a, 0x60, 0xb0, 0xf5, 0xfa, 0x7f, 0x08, 0xd9]
        ofs = FindPattern(self.data, sig) + 2
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('CMP.W R0, #{:n}'.format(delay))[0])
        self.data[ofs:ofs+4] = post
        return [("shutdown", hex(ofs), pre.hex(), post.hex())]

    def brake_light(self):
        '''
        Creator: NandTek
        Description: Alternate (improved) version,
                     instead of changing condition flags (hacky), replace code
        '''
        ret = []

        sig = [0x10, 0xbd, 0x00, 0x00, None, 0x04, 0x00, 0x20, 0x70, 0xb5]
        ofs = FindPattern(self.data, sig) + 4
        ofs_1 = self.data[ofs:ofs+4]
        ofs_1 = struct.unpack("<L", ofs_1)[0]

        sig = [None, 0x00, 0x00, 0x20, None, 0x06, 0x00, 0x20, None, 0x03, 0x00, 0x20]
        ofs = FindPattern(self.data, sig) + 0x8
        ofs_2 = self.data[ofs:ofs+4]
        ofs_2 = struct.unpack("<L", ofs_2)[0]
        adds = ofs_1 - ofs_2

        len_ = 46
        try:
            sig = [0x90, 0xf8, None, None, None, 0x28, None, 0xd1]
            ofs = FindPattern(self.data, sig) + 0x8
        except SignatureException:
            # 242
            sig = [0xa0, 0x7d, 0x40, 0x1c, 0xc0, 0xb2, 0xa0, 0x75]
            ofs = FindPattern(self.data, sig)

        # smash stuff
        pre = self.data[ofs:ofs+len_]
        nopcount = ((len_ - 4) // 2)
        post = bytes(self.ks.asm('NOP')[0] * nopcount
                     + self.ks.asm('POP.W {R4, R5, R6, PC}')[0])
        assert len(post) == len_, len(post)
        self.data[ofs:ofs+len_] = post

        # duplicate "backlight on" code
        asm = """
        adds       r5,r4,#{}
        ldrh       r1,[r5,#0]
        mov.w      r6,#0x40000000
        strh       r1,[r6,#0x34]
        adds       r1,#0x10
        strh       r1,[r5,#0]
        cmp        r1,#0x60
        ble        #0x18
        movs       r1,#0x60
        strh       r1,[r5,#0]
        """.format(adds)

        patch = bytes(self.ks.asm(asm)[0])
        self.data[ofs:ofs+len(patch)] = patch
        post = self.data[ofs:ofs+len_]
        ret.append(["blm", hex(ofs), pre.hex(), post.hex()])
        return ret

    def region_free(self, persist=False):
        '''
        Creator: NandTek
        Description: Remove all region restrictions bound to serial number
        '''
        ret = []
        sig = self.ks.asm('STRB.W R2,[R1,#0x43]')[0]
        ofs = FindPattern(self.data, sig)
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('NOP')[0])
        self.data[ofs:ofs+2] = post
        self.data[ofs+2:ofs+4] = post
        post = self.data[ofs:ofs+4]
        ret.append(["rfm1", hex(ofs), pre.hex(), post.hex()])

        # 248 / 321 (unused in 016)
        sig = self.ks.asm('STRB R2,[R1,#0x1e]')[0]
        ofs = FindPattern(self.data, sig)
        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm('NOP')[0])
        self.data[ofs:ofs+2] = post
        post = self.data[ofs:ofs+2]
        ret.append(["rfm2", hex(ofs), pre.hex(), post.hex()])

        # 016 (unused in 248 / 321)
        sig = self.ks.asm('STRB.W R2,[R1,#0x41]')[0]
        ofs = FindPattern(self.data, sig)
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('NOP')[0])
        self.data[ofs:ofs+2] = post
        self.data[ofs+2:ofs+4] = post
        post = self.data[ofs:ofs+4]
        ret.append(["rfm3", hex(ofs), pre.hex(), post.hex()])

        return ret

    def lower_light(self):
        '''
        Creator: NandTek
        Description: Lowers light intensity, for auto-light effect
        '''
        ret = []
        sig = [0x4f, 0xf0, 0x80, 0x40, 0x04, 0xf0, None, None, 0x20, 0x88]
        ofs = FindPattern(self.data, sig) + 0xa
        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm("adds r0,#1")[0])
        self.data[ofs:ofs+2] = post
        ret.append(["lower_light_step", hex(ofs), pre.hex(), post.hex()])

        ofs += 6
        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm("cmp r0,#5")[0])
        self.data[ofs:ofs+2] = post
        ret.append(["lower_light_cmp", hex(ofs), pre.hex(), post.hex()])

        ofs += 4
        pre = self.data[ofs:ofs+2]
        post = bytes(self.ks.asm("movs r0,#5")[0])
        self.data[ofs:ofs+2] = post
        ret.append(["lower_light_max", hex(ofs), pre.hex(), post.hex()])

        return ret

    def ampere_meter(self, shift=8):
        '''
        Creator: NandTek
        Description: Replace dashboard battery bars with amp meter
        '''
        ret = []

        asm = """
        ldr r1,[pc,#{}]
        ldr r0,[r{},#{}]
        asrs r0,r0,#{}
        bmi #0xc
        """
        addr_table = {
            # pre[0]: ofs1 reg ofs2
            0x80: [0xa0, 0, -0x30],  # 247
            0xa8: [0x9c, 5, -0x10],  # 319
        }

        sig = [None, 0x79, None, 0x49, 0x10, 0xb9, 0xfd, 0xf7, None, None, 0x48, 0x70]
        ofs = FindPattern(self.data, sig)
        pre = self.data[ofs:ofs+0xa]
        post = bytes(self.ks.asm(asm.format(*addr_table[pre[0]], shift))[0])
        self.data[ofs:ofs+0xa] = post
        ret.append(["ampere_meter", hex(ofs), pre.hex(), post.hex()])

        return ret

    def cc_delay(self, seconds):
        '''
        Creator: BotoX
        '''
        ret = []

        delay = int(seconds * 200)

        sig = [0xb0, 0xf8, 0xf8, 0x10, None, 0x4b, 0x4f, 0xf4, 0x7a, 0x70]
        ofs = FindPattern(self.data, sig) + 6
        pre = self.data[ofs:ofs+4]
        post = bytes(self.ks.asm('MOV.W R0,#{}'.format(delay))[0])
        self.data[ofs:ofs+4] = post
        ret.append(["cc_delay", hex(ofs), pre.hex(), post.hex()])

        return ret

    def lever_resolution(self, brake=0x73):
        '''
        Creator: BotoX
        '''
        ret = []

        if brake != 0x73:
            sig = bytes.fromhex("732800dd7320")
            ofs = FindPattern(self.data, sig)
            pre = self.data[ofs:ofs+2]
            post = bytes(self.ks.asm('cmp r0,#{}'.format(brake))[0])
            self.data[ofs:ofs+2] = post
            ret.append(["lever_res_brake1", hex(ofs), pre.hex(), post.hex()])

            ofs += 4
            pre = self.data[ofs:ofs+2]
            post = bytes(self.ks.asm('movs r0,#{}'.format(brake))[0])
            self.data[ofs:ofs+2] = post
            ret.append(["lever_res_brake2", hex(ofs), pre.hex(), post.hex()])

            ofs += 8
            pre = self.data[ofs:ofs+2]
            post = bytes(self.ks.asm('movs r2,#{}'.format(brake))[0])
            self.data[ofs:ofs+2] = post
            ret.append(["lever_res_brake3", hex(ofs), pre.hex(), post.hex()])

        return ret

    def serial_unlock(self):
        # 016: 0x3df6 -> NOP
        # 321: 0x3cc0 -> NOP
        pass


if __name__ == "__main__":
    import sys
    from zippy.zippy import Zippy

    def eprint(*args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    if len(sys.argv) != 4:
        eprint("Usage: {0} <orig-firmware.bin> <target.bin> [patches]".format(sys.argv[0]))
        exit(1)

    infile, outfile, args = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(infile, 'rb') as fp:
        data = fp.read()

    mult = 10./8.5  # new while size / old wheel size

    vlt = FirmwarePatcher(data)

    patches = {
        'dpc': lambda: vlt.dpc(),
        'sdt': lambda: vlt.shutdown_time(1),
        'mss': lambda: vlt.motor_start_speed(3),
        'wsc': lambda: vlt.wheel_speed_const(mult),
        'sld': lambda: vlt.speed_limit_drive(22),
        'sls': lambda: vlt.speed_limit_speed(27),
        'slp': lambda: vlt.speed_limit_pedo(9),
        'alp': lambda: vlt.ampere_pedo(10000),
        'ald': lambda: vlt.ampere_drive(20000),
        'als': lambda: vlt.ampere_speed(30000),
        'alm': lambda: vlt.ampere_max(10000, 30000, 55000),
        'rks': lambda: vlt.remove_kers(),
        'rab': lambda: vlt.remove_autobrake(),
        'rcm': lambda: vlt.remove_charging_mode(),
        'crc': lambda: vlt.current_raising_coeff(1000),
        'ccd': lambda: vlt.cc_delay(2),
        'rfm': lambda: vlt.region_free(),
        'llm': lambda: vlt.lower_light(),
        'blm': lambda: vlt.brake_light(),
        'amm': lambda: vlt.ampere_meter(shift=8),
        'lrb': lambda: vlt.lever_resolution(brake=0x9c),
    }

    for k in patches:
        if k not in args.split(",") and args != 'all':
            continue
        try:
            for desc, ofs, pre, post in patches[k]():
                print(desc, ofs, pre, post)
                pre_dis = [' '.join([x.mnemonic, x.op_str])
                           for x in vlt.cs.disasm(bytes.fromhex(pre), 0)]
                post_dis = [' '.join([x.mnemonic, x.op_str])
                            for x in vlt.cs.disasm(bytes.fromhex(post), 0)]
                for pd in pre_dis:
                    print("<", pd)
                for pd in post_dis:
                    print(">", pd)
        except SignatureException:
            print("SIGERR", k)

    with open(outfile, 'wb') as fp:
        if outfile.endswith(".zip"):
            fp.write(Zippy(vlt.data).zip_it("ilike".encode()))
        else:
            fp.write(vlt.data)
