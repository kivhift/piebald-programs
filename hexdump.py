#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2020-2023 Joshua Hughes <kivhift@gmail.com>

import sys

_hex_tt = None
_prn_tt = None
def hexdump(buffer, outfile=None, start_address=0, bare=False):
    global _hex_tt, _prn_tt
    if _hex_tt is None:
        _hex_tt = [None] * 256
        for i in range(len(_hex_tt)):
            _hex_tt[i] = f'{i:02x}'
    if _prn_tt is None:
        dot = '.'
        _prn_tt = [dot] * 256
        for i in range(32, 127):
            _prn_tt[i] = chr(i)

    buffer = memoryview(buffer)
    outfile = outfile or sys.stdout

    sz = len(buffer)
    fmt = (
        '{1:23s} {2:23s}' if bare else
        f'{{:0{len(hex(start_address + sz)) - 2}x}}  {{:23s}}  {{:23s}}  |{{}}|'
    )
    chunk_sz = 16
    chunk_half_sz = chunk_sz >> 1
    last_chunk = memoryview(b'')
    skipped = False
    for offset in range(0, sz, chunk_sz):
        chunk = memoryview(buffer[offset : min(offset + chunk_sz, sz)])
        if (chunk == last_chunk) and not bare:
            skipped = True
            continue
        if skipped:
            print('*', file = outfile)
            skipped = False
        print(fmt.format(offset + start_address
            , ' '.join(_hex_tt[b] for b in chunk[:chunk_half_sz])
            , ' '.join(_hex_tt[b] for b in chunk[chunk_half_sz:])
            , ''.join(_prn_tt[b] for b in chunk))
            , file = outfile)
        last_chunk = chunk
    if skipped:
        print('*', file = outfile)
    if not bare:
        print(f'{sz:x}', file = outfile)

def main():
    import argparse
    import mmap

    any_int = lambda x: 0 if x is None else int(x, 0)

    parser = argparse.ArgumentParser(description = 'Hexdump a file')
    _a = parser.add_argument
    _a('infile')
    _a('-s', '--skip', help='How many bytes to skip')
    _a('-n', '--number', help='How many bytes to dump')
    _a('-b', '--bare', action='store_true', help='Output bare hexdump')
    args = parser.parse_args()

    skip = any_int(args.skip)
    number = any_int(args.number)
    with open(args.infile, 'rb') as inf, mmap.mmap(
            inf.fileno(), 0, access = mmap.ACCESS_READ) as mm:
        start = max(0, len(mm) + skip) if skip < 0 else skip
        count = len(mm) + number if number <= 0 else number
        if count <= 0:
            raise SystemExit('Invalid calculated count: {count}')

        hexdump(mm[start : start + count], start_address=start, bare=args.bare)

if '__main__' == __name__:
    main()
