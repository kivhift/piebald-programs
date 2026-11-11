#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2026 Joshua Hughes <kivhift@gmail.com>

desc = '''
    NUL SOH STX ETX EOT ENQ ACK BEL  BS TAB  LF  VT FF CR SO SI
    DLE DC1 DC2 DC3 DC4 NAK SYN ETB CAN  EM SUB ESC FS GS RS US
     SP
'''

print(' ASCII '.center(66, '~'))
print(' |  ', '   '.join(f'{i:x}' for i in range(16)))
print(f'-+{"-" * 64}', end='')

for i, t in enumerate(desc.split()):
    if 0 == (i & 0xF):
        print(f'\n{i >> 4}', end='|')
    print(f' {t:>3s}', end='')

for i in range(0x21, 0x7F):
    if 0 == (i & 0xF):
        print(f'\n{i >> 4}', end='|')
    print(f' {chr(i):>3s}', end='')

print(' DEL')
