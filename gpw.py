#!/usr/bin/env python3

import secrets
import string

_default_pw_size = 20
_default_pw_chars = string.digits + string.ascii_letters + string.punctuation


def generate_password(sz=None, chars=None):
    '''Generate a random password using `sz` characters from `chars`.'''

    return ''.join(
        secrets.SystemRandom().choices(
            chars or _default_pw_chars,
            k=sz or _default_pw_size,
        )
    )


def generate_readable_password(sz=None):
    '''Generate a readable password via :func:`generate_password`.'''

    return generate_password(
        sz=sz,
        chars=(
            '0123456789'
            'abcdefghijkmnopqrstuvwxyz'
            'ABCDEFGHJKLMNPQRSTUVWXYZ'
            '~@#$%^&*-_=+\\<>/?'
        ),
    )


def generate_left_hand_password(sz=None):
    '''Generate a left-handed password via :func:`generate_password`.'''

    return generate_password(
        sz=sz,
        chars='`123456qwertasdfgzxcvb~!@#$%^QWERTASDFGZXCVB',
    )


if '__main__' == __name__:
    import argparse

    gp = dict(
        generic=generate_password,
        readable=generate_readable_password,
        lefthand=generate_left_hand_password,
    )

    parser = argparse.ArgumentParser(
        description='Generate random passwords',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _a = parser.add_argument
    _a('-s', '--size', type=int, default=_default_pw_size, help='Password size')
    _a('-t', '--type', choices=gp.keys(), default='generic', help='Password type')
    args = parser.parse_args()

    sz = args.size
    if sz < 1:
        raise SystemExit(f'Password size too small: {sz}')

    f = gp[args.type]
    for _ in range(20):
        print(f(sz), f(sz))
