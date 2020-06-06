#!/bin/sh
n=0
while [ $n -lt $1 ]
do
    python examples/getTrending_v2.py --num $2
    n=$(($n + 1))
done