#!/usr/bin/env python3
#
# SPDX-License-Identifier: MIT
#
# Copyright 2026 Joshua Hughes <kivhift@gmail.com>

'''Given f-stop, shutter speed and ISO, compute the equivalent EV at ISO 100.'''

import argparse
import math


def log2(x):
    return math.log(x) / math.log(2)


def exposure_value(f_stop, t, iso):
    return log2((f_stop**2.0) / t) - log2(iso / 100)


arg_parser = argparse.ArgumentParser(description='Compute EV', epilog=__doc__)
_a = arg_parser.add_argument
_a('-f', '--f-stop', required=True, type=float, help='f/N')
_a('-t', '--time', required=True, help='t')
_a('-i', '--iso', type=float, required=False, default=100, help='S')
args = arg_parser.parse_args()

if '/' in args.time:
    num, denom = map(float, args.time.split('/'))
    t = num / denom
else:
    t = float(args.time)

ev = exposure_value(args.f_stop, t, args.iso)
print(f'EV_100: {ev:.3f}')
