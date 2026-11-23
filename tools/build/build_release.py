# -*- coding: utf-8 -*-
"""
童年游戏厅 · 发布目录整理 + 校验值
==================================
把 _out/ 里的产物整理成一个「发布目录」，并生成 SHA256SUMS.txt，
方便直接传到 GitHub Release。

用法：
  python tools/build/build_release.py
"""
import os
import sys
import json
import shutil
import zipfile
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))

# 环境变量覆盖：CA_GAMES_DIR / CA_OUTPUT_DIR / CA_WORK_DIR ...（大写，下划线）
for _k, _v in os.environ.items():
    if _k.startswith('CA_'):
        CFG[_k[3:].lower()] = _v


def P(p):
    return p if os.path.isabs(p) else os.path.normpath(
        os.path.join(CFG['repo_root'], p))


OUT = P(CFG['output_dir'])
STAGE = os.path.join(OUT, 'release')
VERSION = CFG['version_name']

# 发布附件名（英文，和上游 release 风格一致）
ASSETS = {
    '童年游戏厅-v2.0-整合版-通用.apk': 'childhood-arcade-%s-integrated-universal.apk' % VERSION,
    '童年游戏厅-v2.0-整合版-arm32.apk': 'childhood-arcade-%s-integrated-arm32.apk' % VERSION,
    '童年游戏厅-v2.0-整合版-arm64.apk': 'childhood-arcade-%s-integrated-arm64.apk' % VERSION,
    '童年游戏厅游戏库编辑器.exe': 'childhood-arcade-editor-%s.exe' % VERSION,
}


def sha256(path, buf=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    picked = []
    for src_name, dst_name in ASSETS.items():
        src = os.path.join(OUT, src_name)
        if not os.path.isfile(src):
            print('跳过（不存在）:', src_name)
            continue
        dst = os.path.join(STAGE, dst_name)
        shutil.copyfile(src, dst)
        picked.append(dst)
        print('%-56s %8.1f MB' % (dst_name, os.path.getsize(dst) / 1048576))
    # 数据包：分卷优先（有 .partN 就不再放整包，整包会超 2GiB 上限）
    parts = sorted(f for f in os.listdir(OUT) if '.part' in f and f.startswith('游戏数据包'))
    if parts:
        for f in parts:
            dst = os.path.join(STAGE, f)
            shutil.copyfile(os.path.join(OUT, f), dst)
            picked.append(dst)
            print('%-56s %8.1f MB' % (f, os.path.getsize(dst) / 1048576))
    else:
        for f in sorted(os.listdir(OUT)):
            if f.startswith('游戏数据包') and f.endswith('.zip'):
                dst = os.path.join(STAGE, f)
                shutil.copyfile(os.path.join(OUT, f), dst)
                picked.append(dst)
                print('%-56s %8.1f MB' % (f, os.path.getsize(dst) / 1048576))
    for extra in ('合并数据包.py',):
        src = os.path.join(OUT, extra)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(STAGE, extra))
            picked.append(os.path.join(STAGE, extra))
    # 安装脚本 + 说明
    inst = os.path.join(CFG['repo_root'], 'tools', 'install')
    if os.path.isdir(inst):
        for f in sorted(os.listdir(inst)):
            src = os.path.join(inst, f)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(STAGE, f))
                picked.append(os.path.join(STAGE, f))
    # 编辑器源码 + 构建脚本（小体积，一并给出去）
    srczip = os.path.join(STAGE, 'childhood-arcade-editor-src-%s.zip' % VERSION)
    with zipfile.ZipFile(srczip, 'w', zipfile.ZIP_DEFLATED) as z:
        for sub in ('editor', 'build', 'install', 'docs'):
            d = os.path.join(CFG['repo_root'], 'tools', sub)
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, os.path.join(CFG['repo_root'], 'tools'))
                    z.write(full, 'childhood-arcade-tools/' + rel.replace(os.sep, '/'))
    picked.append(srczip)
    print('%-56s %8.1f MB' % (os.path.basename(srczip), os.path.getsize(srczip) / 1048576))

    # SHA256SUMS
    sums = []
    for p in sorted(picked):
        sums.append('%s  %s' % (sha256(p), os.path.basename(p)))
    with open(os.path.join(STAGE, 'SHA256SUMS.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(sums) + '\n')
    print('\n发布目录:', STAGE)
    print('共 %d 个附件，校验值已写入 SHA256SUMS.txt' % len(picked))


if __name__ == '__main__':
    main()
