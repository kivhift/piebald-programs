#!/usr/bin/env python3

def _bytes(x):
    try:
        return memoryview(x)
    except TypeError:
        return bytearray(x)

def gen_table(poly, width):
    MSb_mask = 1 << (width - 1)
    LUT_mask = (1 << width) - 1
    table = [0] * 256
    crc = MSb_mask
    i = 1
    while i < 256:
        if crc & MSb_mask:
            crc <<= 1
            crc ^= poly
        else:
            crc <<= 1

        for j in range(i):
            table[i + j] = LUT_mask & (crc ^ table[j])

        i <<= 1

    return table

def reflect(x, width):
    rx = i = 0
    while x and i < width:
        rx <<= 1
        rx |= x & 1
        x >>= 1
        i += 1
    if i < width:
        rx <<= width - i

    return rx

def reflect_u8(x):
    x =    ((x & 0xaa) >> 1) | ((x & 0x55) << 1)
    x =    ((x & 0xcc) >> 2) | ((x & 0x33) << 2)
    return ((x & 0xf0) >> 4) | ((x & 0x0f) << 4)

def LUT_CRC(poly, width, data
        , xor_in = 0, xor_out = 0, reflect_in = False, reflect_out = False):
    '''Calculate the CRC using a LUT for widths >|8'''
    if width < 8 or 0 != (width & 7):
        raise ValueError(f'Width should be >8 and divisible by 8: {width}')
    data = _bytes(data)
    T = gen_table(poly, width)
    crc_mask = (1 << width) - 1
    width_rshift = width - 8
    in_xform = reflect_u8 if reflect_in else lambda x: x
    out_xform = reflect if reflect_out else lambda x, w: x

    crc = xor_in
    for byte in data:
        crc = (crc << 8) ^ T[((crc >> width_rshift) ^ in_xform(byte)) & 0xff]
        crc &= crc_mask

    return out_xform(crc, width) ^ xor_out

def CRC(poly, width, data
        , xor_in = 0, xor_out = 0, reflect_in = False, reflect_out = False):
    '''Calculate the CRC for widths >0'''
    data = _bytes(data)
    pop_mask = 1 << width
    crc_mask = pop_mask - 1
    in_xform = reflect_u8 if reflect_in else lambda x: x
    out_xform = reflect if reflect_out else lambda x, w: x

    bits_til_xor_in = width
    crc = 0
    for byte in data:
        byte = in_xform(byte)
        bit = 0x80
        while bit:
            crc <<= 1
            if bit & byte:
                crc |= 1
            if crc & pop_mask:
                crc ^= poly
            if bits_til_xor_in:
                bits_til_xor_in -= 1
                if 0 == bits_til_xor_in:
                    crc ^= xor_in
            crc &= crc_mask
            bit >>= 1
    # bit augmentation
    for _ in range(width):
        crc <<= 1
        if crc & pop_mask:
            crc ^= poly
        crc &= crc_mask

    return out_xform(crc, width) ^ xor_out

def main():
    import argparse

    parser = argparse.ArgumentParser(description = 'Compute CRCs over data'
        ' supplied via the command line, files or stdin')
    _a = parser.add_argument
    _a('-p', '--poly', required = True
        , help = 'Polynomial to use')
    _a('-w', '--width', required = True
        , help = 'Width of the CRC in bits')
    _a('-x', '--xor-in', default = '0'
        , help = 'The input XOR value')
    _a('-X', '--xor-out', default = '0'
        , help = 'The output XOR value')
    _a('-r', '--reflect-input', action = 'store_true'
        , help = 'Reflect the input')
    _a('-R', '--reflect-output', action = 'store_true'
        , help = 'Reflect the output')
    _a('-i', '--input'
        , help = 'File to use as input')
    _a('--hex'
        , help = 'Hexadecimal string of data')
    _a('--str'
        , help = 'String of data (encoded using locale\'s encoding)')
    args = parser.parse_args()

    P = int(args.poly, 0)
    W = int(args.width, 0)
    xi = int(args.xor_in, 0)
    xo = int(args.xor_out, 0)
    ri = args.reflect_input
    ro = args.reflect_output

    fn = LUT_CRC if W >= 8 and 0 == (W % 8) else CRC

    if args.input is not None:
        from mmap import mmap, ACCESS_READ
        with open(args.input, 'rb') as inf, mmap(
                inf.fileno(), 0, access = ACCESS_READ) as mm:
            crc = fn(P, W, mm, xi, xo, ri, ro)
    elif args.hex is not None:
        from binascii import unhexlify
        crc = fn(P, W, unhexlify(args.hex), xi, xo, ri, ro)
    elif args.str is not None:
        from locale import getpreferredencoding
        crc = fn(P, W, args.str.encode(getpreferredencoding()), xi, xo, ri, ro)
    else:
        import sys
        from functools import partial
        from io import DEFAULT_BUFFER_SIZE
        inf = sys.stdin.buffer
        crc = xi
        for chunk in iter(partial(inf.read, DEFAULT_BUFFER_SIZE), b''):
            crc = fn(P, W, chunk, crc, reflect_in = ri)
        crc = (reflect(crc, W) if ro else crc) ^ xo

    print(f'{crc:x}')

if '__main__' == __name__:
    main()
