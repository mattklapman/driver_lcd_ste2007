# Micropython STE2007 96x68 display driver
# inherits from framebuf with overriding

# TODO: issue with rotate(180): command sent, display not rotating
# TODO: issue with contrast & reg_ratio: changing values, display is not changing
# TODO: remove debug print()

"""
BSD 2-Clause License

Copyright (c) 2024, mattklapman

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from micropython import const
import framebuf
import time # needed for reset delay

# Constants: display registers
STE2007_DISPLAY_OFF = const(0xAE)
STE2007_DISPLAY_ON = const(0xAF)
STE2007_DISPLAY_NORMAL = const(0xA6)
STE2007_DISPLAY_INVERSE = const(0xA7)
STE2007_DISPLAY_ALL_PIXELS_NORMAL = const(0xA4)
STE2007_DISPLAY_ALL_PIXELS_ON = const(0xA5)
STE2007_SET_PAGE_ADDRESS = const(0xB0) # B0 to B8; lower 4-bits: Y3, Y2, Y1, Y0
STE2007_SET_COL_ADDRESS_MSB = const(0x10) # 0 to 5F; lower 3-bits: X6, X5, X4
STE2007_SET_COL_ADDRESS_LSB = const(0x00) # lower 4-bits: X3, X2, X1, X0
STE2007_SET_START_LINE = const(0x40) # lower 6-bits: S5, S4, S3, S2, S1, S0
STE2007_SEG_DIRECTION_NORMAL = const(0xA0)
STE2007_SEG_DIRECTION_REVERSE = const(0xA1)
STE2007_COM_DIRECTION_NORMAL = const(0xC0)
STE2007_COM_DIRECTION_REVERSE = const(0xC8)
STE2007_READ_ID = const(0xDB)
#STE2007_READ_ID_DATA = const()
STE2007_POWER_CONTROL_OFF = const(0x28) # 0x2F = ON, all other bits = OFF; lower 3-bits: VB, VR, VF
STE2007_POWER_CONTROL_ON = const(0x2F)
STE2007_V0R = const(0x20) # lower 3-bits: RR2, RR1, RR0 corresponding to volts: 3, 4.28, 5.56, 6.84, 8.12 (default), 9.40, 10.68, 11.96
STE2007_EV = const(0x80) # | 0x10 (default); lower 5-bits: EV4, EV3, EV2, EV1, EV0
STE2007_RESET = const(0xE2)
STE2007_NOP = const(0xE3)
STE2007_V0P = const(0xE1) # immediately follow this command with data byte: 0 (default), +1, ... +127 (0x7F), 0 (0x80), -1, -2, ... -127 (0xFF)
STE2007_THERMAL_COMP = const(0x38) # immediately follow this command with data byte: lower 3-bits: TC (PPM): 0, -300, -600, -900, -1070, -1200, -1500, -1800
STE2007_CHARGE_PUMP_MULT = const(0x3D) # immediately follow this command with data byte: lower 2-bits: CP1, CP0: 5x, 4x, 3x, not used
STE2007_REFRESH_RATE = const(0xEF) # immediately follow this command with data byte: lower 2-bits: RR1, RR0: 80Hz, 75Hz, 70Hz, 65Hz
STE2007_SET_BIAS_RATIO = const(0x30) # lower 3-bits: BR2, BR1, BR0: 1/10, 1/9, 1/8, 1/7, 1/6, 1/5, 1/4, unused
STE2007_NLINE_INVERSION = const(0xAD) # immediately follow this command with data byte: lower 6-bits: F1, NL4, NL3, NL2, NL1, NL0
STE2007_NUM_OF_LINES = const(0xD0) # lower 3-bits: M2, M1, M0: 68 (default), 65, 49, 33, 33 Partial Display, 25 PD, 17 PD, 9 PD
STE2007_IMAGE_LOCATION = const(0xAC) # immediately follow this command with data byte: lower 3-bits: IL2, IL1, IL0: Lines: 0, 8, 16, 24, 32, 48, 56, 64
STE2007_ICON_MODE_ON = const(0xFD)
STE2007_ICON_MODE_OFF = const(0xFC)
#STE2007_TEST_MODE1 = const(0xA9) # do not use
#STE2007_TEST_MODE2 = const(0xAA) # do not use
#STE2007_TEST_MODE3 = const(0xAB) # do not use
#STE2007_TEST_MODE4 = const(0xA8) # do not use
#STE2007_TEST_MODE5 = const(0xFF) # do not use
#STE2007_TEST_MODE6 = const(0xFC) # do not use
#STE2007_TEST_MODE7 = const(0xFE) # do not use
#STE2007_TEST_MODE8 = const(0xFD) # do not use

class STE2007(framebuf.FrameBuffer):
    def __init__(self, spi, cs=None, rs=None, rotation: int=0, inverse: boolean=False, contrast=0x10, regulation_ratio=0x04) -> None:
        # override framebuf parent
        self._data = bytearray(9) # used to send bytes with DC bit
        #self._xoffset = (0x00 if rotation == 0 else 0x00) # rotation by 180 needs a column offset
        self.spi = spi
        if cs != None:
            self.cs = cs
            cs.init(cs.OUT, value=1)
        if rs != None:
            self.rs = rs
            rs.init(rs.OUT, value=0)

        self.buffer = bytearray(96*72//8)
        super().__init__(self.buffer, 96, 72, framebuf.MONO_VLSB)
        self.fill(0) # clear buffer
        self.reset()
        self.show() # clear DDRAM pages 0~8
        self.init(rotation, inverse, contrast, regulation_ratio)
        #self.rotate(rotation)
        #self.invert(inverse)

    def reset(self) -> None:
        # hardware reset if available
        if self.rs != None:
            self.rs.value(0)
            time.sleep_us(5+1) # >5us
            self.rs.value(1)
            time.sleep_us(5+1) # >5us
        # software reset
        self._write_command([STE2007_RESET])

    def init(self, rotation=0, inverse=False, contrast=0x10, regulation_ratio=0x04) -> None:
        # required after a reset
        init_commands = [
            STE2007_V0R | (regulation_ratio & 0x07), # V0 = RR X [ 1 – (63 – EV) / 162 ] X 2.1
            STE2007_EV | (contrast & 0x1F), # see above
            STE2007_DISPLAY_ALL_PIXELS_NORMAL, # Power Saver off sequence (1 command)
            STE2007_POWER_CONTROL_ON,

            (STE2007_SEG_DIRECTION_REVERSE if rotation == 180 else STE2007_SEG_DIRECTION_NORMAL), # SEG direction
            (STE2007_COM_DIRECTION_REVERSE if rotation == 180 else STE2007_COM_DIRECTION_NORMAL), # COM direction
            (STE2007_DISPLAY_INVERSE if inverse else STE2007_DISPLAY_NORMAL), # invert display
            STE2007_SET_START_LINE | 0x00,
            #STE2007_DISPLAY_ALL_PIXELS_NORMAL,
            STE2007_DISPLAY_ON
        ]
        #print('[{}]'.format(', '.join(hex(x) for x in init_commands)))
        self._write_command(init_commands)

    def contrast(self, contrast=0x10) -> None:
        self._write_command([STE2007_EV | (contrast & 0x1F)])
        
    def invert(self, inverse: boolean=False) -> None:
        if inverse == False:
            self._write_command([STE2007_DISPLAY_NORMAL])
        else:
            self._write_command([STE2007_DISPLAY_INVERSE])

    def rotate(self, rotation=0) -> None:
        # orientation can be 0 or 180
        if rotation == 0:
            self._write_command([STE2007_SEG_DIRECTION_NORMAL, STE2007_COM_DIRECTION_NORMAL]) 
            #self._xoffset = 0x00
        elif rotation == 180:
            self._write_command([STE2007_SEG_DIRECTION_REVERSE, STE2007_COM_DIRECTION_REVERSE])
            #self._xoffset = 0x00

    def sleep(self, on: boolean=True) -> None:
        # enable/disable low power mode (turns off visible display)
        # keeps display RAM & register settings
        # From datasheet:
        #   stops internal oscillation circuit;
        #   stops the built-in power circuits;
        #   stops the LCD driving circuits and keeps the common and segment outputs at VSS.
        #   After exiting Power Save mode, the settings will return to be as they were before.
        if on:
            self._write_command([STE2007_DISPLAY_OFF, STE2007_DISPLAY_ALL_PIXELS_ON])
            #time.sleep_ms(250) # can physically remove power after 250ms to POWER OFF
        else:
            self._write_command([STE2007_DISPLAY_ALL_PIXELS_NORMAL])       

    def show(self) -> None:
        # override framebuf parent
        #self._write_command([STE2007_SET_START_LINE | 0x00, STE2007_SET_PAGE_ADDRESS | 0x00, STE2007_SET_COL_ADDRESS_MSB | 0x00, STE2007_SET_COL_ADDRESS_LSB | self._xoffset])
        self._write_command([STE2007_SET_START_LINE | 0x00, STE2007_SET_PAGE_ADDRESS | 0x00, STE2007_SET_COL_ADDRESS_MSB | 0x00, STE2007_SET_COL_ADDRESS_LSB])
        self._write(1, self.buffer)
        self._write_command([STE2007_DISPLAY_ON])

    def _write_command(self, cmd: int) -> None:
        self._write(0, bytearray(cmd))

    def _write(self, dc, val: bytearray) -> None:
        # send 9 bytes for every 1 to 8 bytes to include D/C bit and fit in mod 8
        # fill empty bytes with NOPs
        print()
        print(dc, len(val), ":", end='')
        if dc == 0:
            print('[{}]'.format(', '.join(hex(x) for x in val)))
            for x in range(0, len(val)):
                print(f'{val[x]:08b}, ', end='')
            print()

        for c in range (0, len(val), 8):
            chunk = val[c:c+8]
            l = len(chunk)
            data = bytearray(9)
            for i in range(8):
                if i >= l:
                    chunk.append(STE2007_NOP)
                if dc:
                    data[i] |= (1 << (7-i))
                if i == 7:
                    # no byte split
                    data[i+1] = chunk[i]
                else:
                    # split byte
                    data[i]   |=  chunk[i] >> (i+1)
                    data[i+1] |= (chunk[i] << (7-i)) & 0xFF
            # send chunk
            if dc == 0:
                for x in range(0, len(data)):
                    print(f'{data[x]:08b}, ', end='')
                print()
            self.cs.value(0)
            self.spi.write(data)
            self.cs.value(1)
