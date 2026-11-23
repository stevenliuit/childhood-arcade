# -*- coding: utf-8 -*-
"""
童年游戏厅 · 游戏库编辑器（Windows 桌面版）打包
================================================
把 tools/editor/游戏库编辑器.py 打成单文件 exe，双击即用，不需要装 Python。

依赖：pip install pyinstaller pillow
（pillow 用来预览 JPEG 等 Tk 读不了的封面；没有它编辑器也能用，只是预览不了非 PNG）

用法：
  python tools/build/build_editor.py
"""
import os
import sys
import json
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))

# 环境变量覆盖：CA_GAMES_DIR / CA_OUTPUT_DIR / CA_WORK_DIR ...（大写，下划线）
for _k, _v in os.environ.items():
    if _k.startswith('CA_'):
        CFG[_k[3:].lower()] = _v


def P(p):
    return p if os.path.isabs(p) else os.path.normpath(
        os.path.join(CFG['repo_root'], p))


def main():
    src = P(CFG['editor_source'])
    out = P(CFG['output_dir'])
    icon = P(CFG.get('editor_icon', ''))
    verfile = P(CFG.get('editor_version_file', ''))
    if not os.path.isfile(src):
        raise SystemExit('找不到编辑器源码: ' + src)
    os.makedirs(out, exist_ok=True)
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--noconsole',
           '--name', '童年游戏厅游戏库编辑器',
           '--hidden-import', 'PIL', '--hidden-import', 'PIL.Image',
           '--collect-submodules', 'PIL',
           '--distpath', out,
           '--workpath', os.path.join(P(CFG['work_dir']), 'pyi-editor'),
           '--specpath', os.path.join(P(CFG['work_dir']), 'pyi-editor')]
    if os.path.isfile(icon):
        cmd += ['--icon', icon]
    if os.path.isfile(verfile):
        cmd += ['--version-file', verfile]
    cmd.append(src)
    print(' '.join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit('PyInstaller 失败')
    exe = os.path.join(out, '童年游戏厅游戏库编辑器.exe')
    print('完成: %s (%.1f MB)' % (exe, os.path.getsize(exe) / 1048576))


if __name__ == '__main__':
    main()
