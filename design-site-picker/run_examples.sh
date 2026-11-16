#!/bin/bash
# 复跑三个例子并记录耗时
cd "$(dirname "$0")"
run(){ d=$1; shift; s=$(python3 -c 'import time;print(time.time())'); python3 pick_sites.py examples/$d/输入清单.csv --out examples/$d/output --check "$@" > examples/$d/run.log 2>&1; e=$(python3 -c 'import time;print(time.time())'); python3 -c "print('$d 墙钟 %.1f 秒'%($e-$s))" | tee examples/$d/耗时.txt; }
run 01 --type 落地页 --stuck "首屏配色老是不协调，标题字体也不会搭"
run 02 --type 产品界面 --stuck "后台表格和按钮样式不统一，想要一套组件规范和图标"
run 03 --type 运营图 --stuck "公众号封面要配图素材，还要找能装进手机的展示样机"
