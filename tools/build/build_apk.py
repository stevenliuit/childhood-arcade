# -*- coding: utf-8 -*-
"""
童年游戏厅 · APK 打包（多 ABI 变体）
=====================================
用 Android SDK 的 aapt2 / d8 / zipalign / apksigner 直接打，
不需要 Gradle，也不需要 Android Studio。

前置：
  1. tools/build/config.json 里配好本机路径
  2. 环境变量 ARCADE_KS_PASS = keystore 密码
  3. work_dir/tc/ 里放齐 android.jar / aapt2.exe / zipalign.exe / apksigner.jar / d8.jar
  4. work_dir/ 里放好各 ABI 的原生内核包（base-arm32.apk / base-arm64.apk）
  5. work_dir/catalog.merged.js  = 5 个平台 games.json 合并后的目录
     work_dir/deployment-resources.json = 部署校验清单

用法：
  python tools/build/build_apk.py
"""
import os
import sys
import json
import shutil
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'config.json'), encoding='utf-8'))

# 环境变量覆盖：CA_GAMES_DIR / CA_OUTPUT_DIR / CA_WORK_DIR ...（大写，下划线）
for _k, _v in os.environ.items():
    if _k.startswith('CA_'):
        CFG[_k[3:].lower()] = _v


def P(p):
    """把 config 里的相对路径解析成绝对路径（相对仓库根）。"""
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(CFG['repo_root'], p))


WORK = P(CFG['work_dir'])
TC = P(CFG['toolchain']['android_jar']).rsplit(os.sep, 1)[0]
JDK = CFG['jdk']
SRC = P(CFG['source_dir'])
ASSETS = os.path.join(WORK, 'assets')
RES_ZIP = os.path.join(WORK, 'resources.zip')
BASE_OUT = os.path.join(WORK, 'base2.apk')
DEX = os.path.join(WORK, 'dex', 'classes.dex')
OUT = P(CFG['output_dir'])

VARIANTS = {
    'universal': ['armeabi-v7a', 'arm64-v8a'],
    'arm32': ['armeabi-v7a'],
    'arm64': ['arm64-v8a'],
}
APK_NAMES = {
    'universal': '童年游戏厅-v2.0-整合版-通用.apk',
    'arm32': '童年游戏厅-v2.0-整合版-arm32.apk',
    'arm64': '童年游戏厅-v2.0-整合版-arm64.apk',
}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print('FAIL:', ' '.join(cmd))
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit(1)


def prepare_assets():
    shutil.rmtree(ASSETS, ignore_errors=True)
    shutil.copytree(os.path.join(SRC, 'assets'), ASSETS)
    cat = P(CFG['catalog_merged'])
    res = P(CFG['deployment_resources'])
    if os.path.isfile(cat):
        shutil.copyfile(cat, os.path.join(ASSETS, 'catalog.js'))
    if os.path.isfile(res):
        shutil.copyfile(res, os.path.join(ASSETS, 'deployment-resources.json'))
    # 封面和 ROM 全部放 sdcard，APK 里不带
    shutil.rmtree(os.path.join(ASSETS, 'art'), ignore_errors=True)
    shutil.rmtree(os.path.join(ASSETS, 'roms'), ignore_errors=True)
    # 面框留在 APK 里
    bez = P(CFG['bezels_from_apk'])
    if os.path.isfile(bez):
        bezdir = os.path.join(ASSETS, 'bezels')
        os.makedirs(bezdir, exist_ok=True)
        with zipfile.ZipFile(bez) as z:
            for n in z.namelist():
                if n.startswith('assets/bezels/'):
                    with open(os.path.join(bezdir, n.split('/')[-1]), 'wb') as f:
                        f.write(z.read(n))


def build_dex():
    """javac + d8：把 Java 源码编成 classes.dex"""
    classes = os.path.join(WORK, 'classes')
    shutil.rmtree(classes, ignore_errors=True)
    os.makedirs(classes)
    srcs = []
    jdir = os.path.join(SRC, 'java')
    for root, _, files in os.walk(jdir):
        for f in files:
            if f.endswith('.java'):
                srcs.append(os.path.join(root, f))
    jna = os.path.join(CFG['repo_root'], 'source', 'app', 'libs', 'jna-5.13.0.jar')
    cp = [P(CFG['toolchain']['android_jar'])]
    if os.path.isfile(jna):
        cp.append(jna)
    run([os.path.join(JDK, 'javac.exe'), '-encoding', 'UTF-8', '-source', '8', '-target', '8',
         '-bootclasspath', cp[0], '-cp', os.pathsep.join(cp), '-d', classes] + srcs)
    jar = os.path.join(WORK, 'classes.jar')
    if os.path.isfile(jar):
        os.remove(jar)
    run([os.path.join(JDK, 'jar.exe'), 'cf', jar, '-C', classes, '.'])
    dexdir = os.path.join(WORK, 'dex')
    shutil.rmtree(dexdir, ignore_errors=True)
    os.makedirs(dexdir)
    cmd = [os.path.join(JDK, 'java.exe'), '-cp', P(CFG['toolchain']['d8']),
           'com.android.tools.r8.D8', '--lib', P(CFG['toolchain']['android_jar']),
           '--min-api', '21', '--output', dexdir, jar]
    if os.path.isfile(jna):
        cmd.append(jna)
    run(cmd)


def build(variant):
    abis = VARIANTS[variant]
    unsigned = os.path.join(WORK, 'unsigned_%s.apk' % variant)
    aligned = os.path.join(WORK, 'aligned_%s.apk' % variant)
    out = os.path.join(OUT, APK_NAMES[variant])
    with zipfile.ZipFile(unsigned, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zipfile.ZipFile(BASE_OUT).infolist():
            if item.filename.startswith('META-INF/'):
                continue
            zout.writestr(item, zipfile.ZipFile(BASE_OUT).read(item.filename))
        zout.write(DEX, 'classes.dex')
        for abi in abis:
            base = zipfile.ZipFile(os.path.join(WORK, CFG['native_libs'][abi]))
            for n in base.namelist():
                if n.startswith('lib/%s/' % abi) and n.endswith('.so'):
                    if CFG.get('drop_libarcade') and n.endswith('/libarcade.so'):
                        continue      # 不用��� fba2012 内核
                    zout.writestr(n, base.read(n))
            base.close()
    run([P(CFG['toolchain']['zipalign']), '-f', '-p', '4', unsigned, aligned])
    pw = os.environ.get('ARCADE_KS_PASS', '')
    if not pw:
        raise SystemExit('请先设置环境变量 ARCADE_KS_PASS = keystore 密码')
    run([os.path.join(JDK, 'java.exe'), '-jar', P(CFG['toolchain']['apksigner']), 'sign',
         '--ks', P(CFG['keystore']), '--ks-key-alias', CFG['keystore_alias'],
         '--ks-pass', 'pass:' + pw, '--key-pass', 'pass:' + pw, '--out', out, aligned])
    print('%-10s -> %s (%.1f MB)' % (variant, os.path.basename(out),
                                     os.path.getsize(out) / 1048576))


if __name__ == '__main__':
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    print('准备资源...')
    prepare_assets()
    res_ascii = os.path.join(WORK, 'res')
    shutil.rmtree(res_ascii, ignore_errors=True)
    shutil.copytree(os.path.join(SRC, 'res'), res_ascii)
    man_ascii = os.path.join(WORK, 'AndroidManifest.xml')
    shutil.copyfile(os.path.join(SRC, 'AndroidManifest.xml'), man_ascii)
    run([P(CFG['toolchain']['aapt2']), 'compile', '--dir', res_ascii, '-o', RES_ZIP])
    run([P(CFG['toolchain']['aapt2']), 'link', '-o', BASE_OUT,
         '-I', P(CFG['toolchain']['android_jar']), '--manifest', man_ascii,
         '-A', ASSETS, RES_ZIP, '--auto-add-overlay'])
    print('aapt2 link 完成')
    print('编译 dex...')
    build_dex()
    for v in VARIANTS:
        build(v)
    print('全部变体打包完成 ->', OUT)
