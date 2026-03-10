from collections.abc import Iterable
from typing import Optional, Union


class CodeCave:
    """
    Manages a contiguous region of ROM used as a code cave.

    Tracks the current write cursor so multiple callers can
    append assembled payloads one after another without
    manually managing addresses.

    Usage:
        cave = CodeCave(patcher, start=0x8006898, end=0x80068D6)
        addr = cave.write(assembled_bytes)   # returns address where bytes were written
        cave.pad()                           # fill remainder with NOPs
        print(cave.remaining)               # bytes still free
        print(cave.cursor)                  # next free address
    """

    NOP_SIZE = 2  # Thumb NOP is always 2 bytes

    def __init__(self, patcher, start: int, end: int):
        """
        Args:
            patcher : the ROM patcher object (exposes .asm() and patch_rom())
            start   : first byte address of the cave (inclusive)
            end     : first byte address past the cave (exclusive)
        """
        self._patcher   = patcher
        self._start     = start
        self._end       = end
        self._cursor    = start

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def cursor(self) -> int:
        """Address where the next write will land."""
        return self._cursor

    @property
    def remaining(self) -> int:
        """How many bytes are still free in the cave."""
        return self._end - self._cursor

    @property
    def capacity(self) -> int:
        """Total size of the cave in bytes."""
        return self._end - self._start

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def write(self, assembled_bytes: bytes, result: list) -> int:
        """
        Append pre-assembled bytes at the current cursor.

        Returns the address at which the bytes were written so
        callers can compute relative branch offsets if needed.

        Raises ValueError if the payload would overflow the cave.
        """
        if len(assembled_bytes) > self.remaining:
            raise ValueError(
                f"CodeCave overflow: tried to write {len(assembled_bytes)} bytes "
                f"but only {self.remaining} remain "
                f"(cursor=0x{self._cursor:08X}, end=0x{self._end:08X})"
            )
        write_addr   = self._cursor
        self._cursor += len(assembled_bytes)
        self._patcher.patch_rom(result, write_addr, assembled_bytes)
        return write_addr

    def write_asm(self, asm_src: str, result: list, expected_size: Optional[Union[list, int]] = None) -> int:
        """
        Assemble *asm_src* and append it to the cave.

        Convenience wrapper around write() — source strings may use
        the placeholder ``{PC}`` which will be substituted with the
        current cursor value before assembly, useful for PC-relative
        branches.

        Returns the address at which the first byte was written.
        """
        src = asm_src.replace("{PC}", hex(self._cursor))
        assembled = self._patcher.asm(src)
        if expected_size is not None:
            if isinstance(expected_size, Iterable):
                if len(assembled) not in expected_size:
                    raise ValueError(f'Expected {expected_size}-byte Thumb instruction')
            elif len(assembled) != expected_size:
                raise ValueError(f'Expected {expected_size}-byte Thumb instruction')
        return self.write(assembled, result)

    def pad(self, result: list) -> None:
        """Fill the remaining cave bytes with Thumb NOPs."""
        nop_count = self.remaining // self.NOP_SIZE
        if nop_count:
            nop_padding = self._patcher.asm("nop") * nop_count
            self.write(nop_padding, result)
