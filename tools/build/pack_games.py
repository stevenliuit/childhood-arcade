# -*- coding: utf-8 -*-
"""
童年游戏厅 · 游戏数据包打包（可选分卷）
=========================================
把 sdcard 目录结构（nes/ arcade/ gba/ md/ sfc/，每个平台含
games.json + covers/ + roms/）打成一个 zip。

GitHub Release 单个附件上限 2 GiB，所以提供了 --split 参数，
把数据包按指定大小切成若干 .chunkN，并生成配套的合并脚本。

注意：实测 GitHub 一次 POST 传 500 MB 能稳定传完，超过就会被掐断
（连接重置），所以上传用的分片建议 ≤500 MB。

用法：
  python tools/build/pack_games.py
  python tools/build/pack_games.py --split 500       # 每片 500 MB
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
# CA_PLATFORMS=nes,gba 可以只打包某几个平台（调试用）
PLATFORMS = os.environ.get('CA_PLATFORMS', ','.join(PLATFORMS)).split(',')


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
    """切成 dest_base1 / dest_base2 ...（编号从 1 开始）"""
    limit = part_mb * 1024 * 1024
    idx = 1
    with open(src, 'rb') as f:
        while True:
            out = open('%s%d' % (dest_base, idx), 'wb')
            written = 0
            while written < limit:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                written += len(chunk)
            out.close()
            if written == 0:
                os.remove('%s%d' % (dest_base, idx))
                break
            idx += 1
    parts = []
    idx = 1
    while os.path.isfile('%s%d' % (dest_base, idx)):
        parts.append('%s%d' % (dest_base, idx))
        idx += 1
    return parts


MERGE_SCRIPT = '''# -*- coding: utf-8 -*-
"""把 chunkN 分片合并回完整 zip，然后解压到 /sdcard/"""
import os
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
parts = sorted(glob.glob(os.path.join(HERE, 'childhood-arcade-games-2.0.0.chunk*')),
               key=lambda p: int(p.rsplit('chunk', 1)[1]))
if not parts:
    print('没找到 childhood-arcade-games-2.0.0.chunkN 分片'); sys.exit(1)
out = os.path.join(HERE, 'childhood-arcade-games-2.0.0.zip')
print('合并 %d 个分片 -> %s' % (len(parts), out))
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
print()
print('接下来把 zip 传到手机 /sdcard/ 然后解压：')
print('  adb shell unzip -o /sdcard/childhood-arcade-games-2.0.0.zip -d /sdcard/')
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
        base = os.path.join(OUT, 'childhood-arcade-games-2.0.0.chunk')
        parts = split(dest, base, part_mb)
        with open(os.path.join(OUT, 'merge-games-data.py'), 'w', encoding='utf-8') as f:
            f.write(MERGE_SCRIPT)
        print('已切成 %d 片（每片 %d MB）：' % (len(parts), part_mb))
        for p in parts:
            print('   ', os.path.basename(p), '%.1f MB' % (os.path.getsize(p) / 1048576))
        print('配套脚本：merge-games-data.py')
