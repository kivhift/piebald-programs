#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2026 Joshua Hughes <kivhift@gmail.com>

import fileinput as fi

from binascii import crc_hqx as crc16

file_seen = False
N = 1
crc = 0
with fi.input(mode='rb') as f:
    for line in f:
        if fi.isfirstline():
            if file_seen:
                print(f'{N >> 3}\n')

            print(f'-- {fi.filename()} --')
            N = 1
            crc = 0

        crc = crc16(line, crc)
        print(f'{crc:04x},{crc16(line, 0):04x} ', end='')

        if 0 == (N & 7):
            print((N >> 3) - 1)

        N += 1
        file_seen = True

if 1 != (N & 7):
    print(N >> 3)
