#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2020-2023 Joshua Hughes <kivhift@gmail.com>

import hashlib

from os.path import getsize
from mmap import mmap, ACCESS_READ


def get_file_hash(path, *, algo='md5'):
    if 0 == getsize(path):
        return f'{hashlib.new(algo).hexdigest()} *{path}'
    else:
        with open(path, "rb") as f, mmap(f.fileno(), 0, access=ACCESS_READ) as mm:
            return f'{hashlib.new(algo, memoryview(mm)).hexdigest()} *{path}'


if '__main__' == __name__:
    import argparse
    from os import walk
    from os.path import exists, isfile, isdir, join

    parser = argparse.ArgumentParser(
        description='Hash a file',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            'The available algorithms are: '
            f'{", ".join(sorted(hashlib.algorithms_available))}'
        ),
    )
    _a = parser.add_argument
    _a('files', metavar='FILE', nargs='*', help='Input file')
    _a(
        '-a',
        '--algo',
        metavar='ALGO',
        choices=hashlib.algorithms_available,
        default='md5',
        help='Hash algorithm to use',
    )
    _a('-w', '--walk', action='store_true', help='Walk directories')
    _a('-z', '--zero-skip', action='store_true', help='Skip empty files')

    args = parser.parse_args()

    def file_ok(path):
        return not (args.zero_skip and (0 == getsize(path)))

    for path in args.files:
        if not exists(path):
            raise SystemExit(f'"{path}" does not exist')
        if isfile(path) and file_ok(path):
            print(get_file_hash(path, algo=args.algo))
            continue
        if isdir(path):
            if not args.walk:
                raise SystemExit(f'"{path}" is a directory')
            for root, _, files in walk(path):
                for file in files:
                    joined_path = join(root, file)
                    if file_ok(joined_path):
                        print(get_file_hash(join(root, file), algo=args.algo))
