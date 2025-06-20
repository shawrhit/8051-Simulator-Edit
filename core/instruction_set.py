from core.util import decompose_byte, twos_complement, tohex


class Instructions:
    def __init__(self, op) -> None:
        self.op = op
        self._jump_flag = False
        self._jump_instructions = op._jump_instructions
        self._base = 16
        self.flags = self.op.super_memory.PSW
        pass

    def _is_jump_opcode(self, opcode) -> bool:
        opcode = opcode.upper()
        if opcode not in self._jump_instructions:
            return False
        return True

    def _next_addr(self, addr) -> str:
        return format(int(str(addr), 16) + 1, "#06x")

    def _check_carry(self, data_1, data_2, og2, add=True, _AC=True, _CY=True) -> None:
        """
        Method to check both `CY` and `AC` self.flags.

        `aux_data` are the LSB of the two data to be added
        For example: for `0x11` and `0xae`, `aux_data=["0x1", "0xe"]`
        """
        decomposed_data_1 = decompose_byte(data_1, nibble=True)
        decomposed_data_2 = decompose_byte(data_2, nibble=True)
        carry_data, aux_data = list(zip(decomposed_data_1, decomposed_data_2))

        if _AC:
            self.flags.AC = False
            if (int(aux_data[0], 16) + int(aux_data[1], 16)) >= 16:
                print("AUX FLAG")
                self.flags.AC = True

        if not _CY:
            return

        if not add:
            self.flags.CY = False
            if int(str(data_1), 16) < int(str(og2), 16):
                print("CARRY FLAG-")
                self.flags.CY = True
        return

    def _check_parity(self, data_bin: str) -> None:
        self.flags.P = False
        _count_1s = data_bin.count("1")
        if not _count_1s % 2:
            self.flags.P = True
            print("PARITY")
        return

    def _check_overflow(self, data_bin: str) -> None:
        self.flags.OV = False
        if int(data_bin[0]):
            self.flags.OV = True
            print("SIGN")
        return

    def _check_flags(self, data_bin, _P=True, _OV=True) -> bool:
        if _P:
            self._check_parity(data_bin)
        if _OV:
            self._check_overflow(data_bin)
        return True

    def _check_flags_and_compute(self, data_1, data_2, add=True, _AC=True, _CY=True, _P=True, _OV=True):
        og2 = data_2
        if not add:
            data_2 = twos_complement(str(data_2))

        result = int(str(data_1), 16) + int(str(data_2), 16)
        if result > 255:
            if _CY:
                self.flags.CY = True
                print("CARRY FLAG+")
            result -= 256
        result_hex = format(result, "#04x")
        data_bin = format(result, "08b")

        self._check_carry(data_1, data_2, og2, add=add, _AC=_AC, _CY=_CY)
        self._check_flags(data_bin, _P=_P, _OV=_OV)
        return result_hex

    def _resolve_addressing_mode(self, addr, data=None) -> tuple:
        if addr[0] == "@":  # Register indirect
            addr = self.op.memory_read(addr[1:])

        if data:
            if data[0] == "@":  # Register indirect
                data = self.op.memory_read(data[1:])
            elif data[0] == "#":  # Immediate addressing
                data = data[1:]
            else:
                data = self.op.memory_read(data)
        return addr, data

    def mov(self, addr, data) -> bool:
        addr, data = self._resolve_addressing_mode(addr, data)
        return self.op.memory_write(addr, data)

    def add(self, addr, data) -> bool:
        addr, data_1 = self._resolve_addressing_mode(addr, data)
        data_2 = self.op.memory_read(addr)
        result_hex = self._check_flags_and_compute(data_1, data_2)
        return self.op.memory_write(addr, result_hex)

    def subb(self, addr, data) -> bool:
        addr, data_2 = self._resolve_addressing_mode(addr, data)
        data_1 = self.op.memory_read(addr)
        if self.flags.CY:
            self.flags.CY = False
            data_2 += 1
        result_hex = self._check_flags_and_compute(data_1, data_2, add=False)
        return self.op.memory_write(addr, result_hex)

    def anl(self, addr_1, addr_2) -> bool:
        addr_1, _ = self._resolve_addressing_mode(addr_1)
        addr_2, _ = self._resolve_addressing_mode(addr_2)

        data_1 = int(self.op.memory_read(addr_1))
        data_2 = int(self.op.memory_read(addr_2))
        result = format(data_1 & data_2, "#04x")
        self.op.memory_write(addr_1, result)
        return self._check_flags(format(int(result, self._base), "08b"))

    def orl(self, addr_1, addr_2) -> bool:
        addr_1, _ = self._resolve_addressing_mode(addr_1)
        addr_2, _ = self._resolve_addressing_mode(addr_2)

        data_1 = int(self.op.memory_read(addr_1))
        data_2 = int(self.op.memory_read(addr_2))
        result = format(data_1 | data_2, "#04x")
        self.op.memory_write(addr_1, result)
        return self._check_flags(format(int(result, self._base), "08b"))

    def inc(self, addr) -> bool:
        addr, _ = self._resolve_addressing_mode(addr)
        data = self.op.memory_read(addr)
        return self.op.memory_write(addr, data + 1)

    def dec(self, addr) -> bool:
        addr, _ = self._resolve_addressing_mode(addr)
        print(f"addr: {addr}")
        data = self.op.memory_read(addr)
        data_to_write = self._check_flags_and_compute(
            data, "0x01", add=False, _CY=False, _AC=False, _P=False, _OV=False
        )
        return self.op.memory_write(addr, data_to_write)

    def rl(self, addr) -> bool:
        """Rotate left without carry"""
        addr, _ = self._resolve_addressing_mode(addr)
        data = self.op.memory_read(addr)
        data_bin = list(format(int(str(data), 16), "08b"))
        rolled_data_bin = []

        for i in range(0, len(data_bin[:-1])):
            rolled_data_bin.append(data_bin[i + 1])

        rolled_data_bin.insert(8, str(int(data_bin[0])))
        rolled_data_bin = "".join(rolled_data_bin)
        data_new = format(int(rolled_data_bin, 2), "#02x")
        return self.op.memory_write("A", data_new)

    def rr(self, addr) -> bool:
        """Rotate right without carry"""
        addr, _ = self._resolve_addressing_mode(addr)
        data = self.op.memory_read(addr)
        data_bin = list(format(int(str(data), 16), "08b"))
        rolled_data_bin = []
        rolled_data_bin.insert(0, str(int(data_bin[7])))
        for i in range(0, len(data_bin[:-1])):
            rolled_data_bin.append(data_bin[i])

        rolled_data_bin = "".join(rolled_data_bin)
        data_new = format(int(rolled_data_bin, 2), "#02x")
        return self.op.memory_write("A", data_new)

    def da(self, addr: str) -> bool:
        """Converts the hex data into its BCD equivalent."""
        addr, _ = self._resolve_addressing_mode(addr)
        data = self.op.memory_read(addr)
        data_decimal = int(str(data), 16)
        return self.op.memory_write(addr, f"0x{data_decimal}")

    def org(self, addr) -> bool:
        """Database directive origin"""
        return self.op.super_memory.PC(addr)

    def setb(self, bit: str) -> bool:
        """Set a bit to true"""
        return self.op.bit_write(bit, True)

    def clr(self, bit: str) -> bool:
        """Clears a bit"""
        return self.op.bit_write(bit, False)

    def cpl(self, bit: str) -> bool:
        """Complements a bit"""
        _data = self.op.bit_read(bit)
        return self.op.bit_write(bit, not _data)

    def push(self, addr: str) -> bool:
        """Pushes the content of the memory location to the stack."""
        data = self.op.memory_read(addr)
        return self.op.super_memory.SP.write(data)

    def pop(self, addr: str) -> bool:
        """Pop the stack as the content of the memory location."""
        data = self.op.super_memory.SP.read()
        return self.op.memory_write(addr, data)

    def jz(self, label, *args, **kwargs) -> bool:
        """Jump if accumulator is zero"""
        bounce_to_label = kwargs.get("bounce_to_label")
        print(self.op.memory_read("A"))
        if int(self.op.memory_read("A")) == 0:
            return bounce_to_label(label)
        return True

    def jnz(self, label, *args, **kwargs) -> bool:
        """Jump if accumulator is not zero"""
        bounce_to_label = kwargs.get("bounce_to_label")
        print(self.op.memory_read("A"))
        if int(self.op.memory_read("A")) != 0:
            return bounce_to_label(label)
        return True

    def jc(self, label, *args, **kwargs) -> bool:
        """Jump if carry"""
        bounce_to_label = kwargs.get("bounce_to_label")
        print(self.op.flags.CY)
        if self.op.flags.CY:
            return bounce_to_label(label)
        return True

    def jnc(self, label, *args, **kwargs) -> bool:
        """Jump if no carry"""
        bounce_to_label = kwargs.get("bounce_to_label")
        print(self.op.flags.CY)
        if not self.op.flags.CY:
            return bounce_to_label(label)
        return True

    def djnz(self, addr, label, *args, **kwargs) -> bool:
        """Jump if accumulator is not zero"""
        bounce_to_label = kwargs.get("bounce_to_label")
        if label == "offset":
            label = addr
            addr = "A"
        data = self.op.memory_read(addr)

        result = int(str(data), 16) - 1
        self.op.memory_write(addr, hex(result))
        if int(self.op.memory_read(addr)) != 0:
            return bounce_to_label(label)
        return True

    def cjne(self, addr, addr2, label, *args, **kwargs) -> bool:
        """Compare and jump if not equal"""
        bounce_to_label = kwargs.get("bounce_to_label")
        data_1 = self.op.memory_read(addr)
        addr2, _ = self._resolve_addressing_mode(addr2)
        data_2 = self.op.memory_read(addr2)
        if int(data_1) != int(data_2):
            if int(data_1) < int(data_2):
                self.flags.CY = True
            # Jump if not equal
            return bounce_to_label(label)
        self.flags.CY = False
        return True

    def jb(self, addr, label, *args, **kwargs) -> bool:
        """Jump if bit is true"""
        raise NotImplemented
        bounce_to_label = kwargs.get("bounce_to_label")
        data = self.op.memory_read(addr)
        if data:
            return bounce_to_label(label)
        return True

    def jnb(self, addr, label, *args, **kwargs) -> bool:
        """Jump if bit is false"""
        raise NotImplemented
        bounce_to_label = kwargs.get("bounce_to_label")
        data = self.op.memory_read(addr)
        if data:
            return bounce_to_label(label)
        return True

    def mul(self, addr_1="A", addr_2="B") -> bool:
        # addr_1, _ = self._resolve_addressing_mode(addr_1)
        # addr_2, _ = self._resolve_addressing_mode(addr_2)
        addr_1 = "A"
        addr_2 = "B"
        # Fetch register objects
        reg1 = self.op._get_register(addr_1)
        reg2 = self.op._get_register(addr_2)

        # Read values (assuming they return integers, not hex strings)
        data_1 = reg1.read()
        data_2 = reg2.read()

        # Perform 8-bit × 8-bit multiplication
        result = int(data_1) * int(data_2)
        print(result)

        result_low = result & 0xFF
        result_high = (result >> 8) & 0xFF
        result_low = tohex(str(hex(result_low)))
        result_high = tohex(str(hex(result_high)))

        # Write results back to A and B
        self.op.memory_write("0xE0", result_low)
        self.op.memory_write("0xF0", result_high)

        # CY is always cleared for MUL
        self.flags.CY = False

        # OV (overflow) is set if upper byte (B) is non-zero
        self.flags.OV = bool(result_high)

        print(f"MUL {addr_1}, {addr_2} => {data_1} × {data_2} = {result} (A={result_low}, B={result_high})")
        return True

    pass
