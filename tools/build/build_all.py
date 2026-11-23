# -*- coding: utf-8 -*-
"""
童年游戏厅 · 一键打包流程
=========================
依次执行：
  1. build_apk.py      编译 3 个 ABI 变体的 APK
  2. pack_games.py     打游戏数据包（可选分卷）
  3. build_editor.py   打 Windows 编辑器 exe
  4. build_release.py  整理发布目录 + 算 SHA256

用法：
  python tools/build/build_all.py
  python tools/build/build_all.py --split 1900     # 数据包分卷（GitHub 单附件 2GiB 上限）
"""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, *args):
    print('\n' + '=' * 60)
    print('>>', script, ' '.join(args))
    print('=' * 60)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)] + list(args))
    if r.returncode != 0:
        raise SystemExit('%s 失败' % script)


if __name__ == '__main__':
    split = []
    if '--split' in sys.argv:
        split = ['--split', sys.argv[sys.argv.index('--split') + 1]]
    run('build_apk.py')
    run('pack_games.py', *split)
    run('build_editor.py')
    run('build_release.py')
    print('\n全部完成，产物在 _out/ 目录')
