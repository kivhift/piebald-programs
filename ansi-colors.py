#!/usr/bin/env python3
#
# Adapted from: https://tldp.org/HOWTO/Bash-Prompt-HOWTO/x329.html
#
# It turns out that Win10 terminals finally caught up with the 60s/70s. If you
# set a DWORD to 1 at HKCU/Console/VirtualTerminalLevel then
# subsequently-opened terminals will understand (a subset of) ANSI escapes.

E = '\x1b['
T = 'Hey'
BGs = tuple(f'{i}m' for i in range(40, 48))
FGs = ['m', '1m']
for i in range(30, 38):
    FGs.extend(f'{i}m 1;{i}m'.split())

print('Synopsis (\\e = \\x1b): \e[(1;)?3[0-7]m\e[4[0-7]m TEXT \e[m')
print(f'\n            {"".join(f"  {bg} " for bg in BGs)}')
for fg in FGs:
    print(
        f'{fg:>6} {E}{fg} {T} {E}m'
        f'{"".join(f" {E}{fg}{E}{bg} {T} {E}m" for bg in BGs)}'
    )

hints = dict(Bol=1, Dim=2, Ita=3, Und=4, Slo=5, Rap=6, Rev=7, Hid=8, Cro=9)
print(f'\n{" ".join(f"{n}={E}{n}m{h}{E}m" for h, n in hints.items())}')
