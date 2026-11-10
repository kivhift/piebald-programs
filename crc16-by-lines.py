#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2026 Joshua Hughes <kivhift@gmail.com>

'''
Use this script to make it easier to reproduce a file on another system when
retyping it to do so. With a visual representation of the file along with the
output of this script, you can more-easily determine where differences in the
reproduced files are. Scan the left-hand column to see where the running CRCs
do not match and then backtrack from there to find the line in question.
'''

import argparse
import sys

from binascii import crc_hqx as crc16


def output_crc16s(f_in):
    crc = 0
    n = -1
    print(f'-- {f_in.name} --')
    for line in f_in:
        crc = crc16(line, crc)
        print(f'{crc:04x},{crc16(line, 0):04x} ', end='')
        n += 1
        if 7 == (n & 7):
            print(n >> 3)
    if (n > -1) and (7 != (n & 7)):
        print(n >> 3)


arg_parser = argparse.ArgumentParser(
    description='calculate a running and by-line crc16', epilog=__doc__
)
_a = arg_parser.add_argument
_a('files', nargs='*')
args = arg_parser.parse_args()

if not args.files:
    output_crc16s(sys.stdin.buffer)
else:
    for file in args.files:
        with open(file, 'rb') as f_in:
            output_crc16s(f_in)
