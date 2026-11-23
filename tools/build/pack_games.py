# -*- coding: utf-8 -*-
"""
童年游戏厅 · 游戏数据包打包（可选分卷）
=========================================
把 sdcard 目录结构（nes/ arcade/ gba/ md/ sfc/，每个平台含
games.json + covers/ + roms/）打成一个 zip。

GitHub Release 单个附件上限 2 GiB，所以提供了 --split 参数，
把数据包按指定大小切成若干 .partN，并生成配套的合并脚本。

用法：
  python tools/build/pack_games.py
  python tools/build/pack_games.py --split 1900      # 每卷 1900 MB
"""
import os
import sys
import json
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))

# 环境变量覆盖：CA_GAMES_DIR / CA_OUTPUT_DIR / CA_WORK_DIR ...（大写，下划线）
for _k, _v in os.environ.items():
    if _k.startswith('CA_'):
        CFG[_k[3:].lower()] = _v


def P(p):
    return p if os.path.isabs(p) else os.path.normpath(
        os.path.join(CFG['repo_root'], p))


GAMES = P(CFG['games_dir'])
OUT = P(CFG['output_dir'])
ROOT = 'ChildhoodArcade'
PLATFORMS = ['nes', 'arcade', 'gba', 'md', 'sfc']
NAME = '游戏数据包-v2.0.zip'


def build_zip(dest):
    if os.path.isfile(dest):
        os.remove(dest)
    n = 0
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in PLATFORMS:
            base = os.path.join(GAMES, p)
            if not os.path.isdir(base):
                continue
            for dirpath, _, filenames in os.walk(base):
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, GAMES).replace(os.sep, '/')
                    z.write(full, ROOT + '/' + rel)
                    n += 1
    return n


def split(src, dest_base, part_mb):
    limit = part_mb * 1024 * 1024
    idx = 1
    cur = open('%s.part%d' % (dest_base, idx), 'wb')
    written = 0
    with open(src, 'rb') as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            while chunk:
                room = limit - written
                take = min(room, len(chunk))
                cur.write(chunk[:take])
                written += take
                chunk = chunk[take:]
                if written >= limit:
                    cur.close()
                    idx += 1
                    cur = open('%s.part%d' % (dest_base, idx), 'wb')
                    written = 0
    cur.close()
    parts = []
    idx = 1
    while os.path.isfile('%s.part%d' % (dest_base, idx)):
        parts.append('%s.part%d' % (dest_base, idx))
        idx += 1
    return parts


MERGE_SCRIPT = '''# -*- coding: utf-8 -*-
"""把 .partN 分卷合并回完整 zip，然后解压到 /sdcard/"""
import os
import sys
import glob
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
parts = sorted(glob.glob(os.path.join(HERE, '*.part*')),
               key=lambda p: int(p.rsplit('.part', 1)[1]))
if not parts:
    print('没找到 .partN 分卷'); sys.exit(1)
out = os.path.join(HERE, '游戏数据包-v2.0.zip')
print('合并 %d 个分卷 -> %s' % (len(parts), out))
with open(out, 'wb') as w:
    for p in parts:
        print('  +', os.path.basename(p))
        with open(p, 'rb') as r:
            while True:
                b = r.read(8 * 1024 * 1024)
                if not b:
                    break
                w.write(b)
print('完成，大小 %.1f MB' % (os.path.getsize(out) / 1048576))
print('解压到手机：把 zip 传到 /sdcard/ 然后 unzip -o 名字.zip -d /sdcard/')
'''


if __name__ == '__main__':
    part_mb = None
    if '--split' in sys.argv:
        part_mb = int(sys.argv[sys.argv.index('--split') + 1])
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, NAME)
    n = build_zip(dest)
    print('写入 %d 个文件 -> %s (%.1f MB)' % (n, dest, os.path.getsize(dest) / 1048576))
    if part_mb:
        base = os.path.join(OUT, '游戏数据包-v2.0')
        parts = split(dest, base, part_mb)
        with open(os.path.join(OUT, '合并数据包.py'), 'w', encoding='utf-8') as f:
            f.write(MERGE_SCRIPT)
        print('已切成 %d 卷（每卷 %d MB）：' % (len(parts), part_mb))
        for p in parts:
            print('   ', os.path.basename(p), '%.1f MB' % (os.path.getsize(p) / 1048576))
        print('配套脚本：合并数据包.py')
