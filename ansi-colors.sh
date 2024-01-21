#!/bin/bash
#
# Adapted from: https://tldp.org/HOWTO/Bash-Prompt-HOWTO/x329.html
#
# You can specify the display text via the first argument. It will be truncated
# to the first three characters.

set -eu -o pipefail

echo "Synopsis: \"\e[(1;)?3[0-7]m\e[4[0-7]m TEXT \e[0m\""

if [ ! -t 1 ]; then
    echo "
 0 = black
 1 = red
 2 = green
 3 = yellow
 4 = blue
 5 = magenta
 6 = cyan
 7 = white
"
    exit 0
fi

declare T=${1:-Hey}
if [ ${#T} -gt 3 ]; then
    T=${T:0:3}
elif [ ${#T} -lt 3 ]; then
    declare blk='   '
    T="${blk:0:3-${#T}}$T"
    unset blk
fi
readonly T

echo -en "\n            "
declare -ra BGs=(40m 41m 42m 43m 44m 45m 46m 47m)
for bg in ${BGs[*]}; do
    echo -n "  $bg "
done
echo

for fg in '    m' '   1m' '  30m' '1;30m' '  31m' '1;31m' '  32m' \
          '1;32m' '  33m' '1;33m' '  34m' '1;34m' '  35m' '1;35m' \
          '  36m' '1;36m' '  37m' '1;37m'; do
    echo -n " $fg "
    fg=${fg// /}
    echo -en "\e[$fg $T \e[0m"
    for bg in ${BGs[*]}; do
        echo -en " \e[$fg\e[$bg $T \e[0m"
    done
    echo
done
