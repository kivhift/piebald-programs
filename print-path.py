#!/usr/bin/env python3

import argparse
import os
import sys

parser = argparse.ArgumentParser(
    description='Print $PATH(-like) environment variable(s)',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    epilog='A question mark indicates that the specific part does not exist.',
)
_a = parser.add_argument
_a(
    'paths',
    metavar='PATHLIKE',
    nargs='*',
    default=['PATH'],
    help='$PATH-like environment variable to print',
)
args = parser.parse_args()

env = os.environ
sep = os.pathsep
for path in args.paths:
    if path not in env:
        print(f' ** {path} not in environment, skipping...', file=sys.stderr)
        continue

    print(f'${path} =')
    for part in env[path].split(sep):
        # Decorate with separator to make it easier to see empty parts. Prepend
        # a question mark if the specified part does not exist.
        print(f' {" " if os.path.exists(part) else "?"}{sep} {part}')
