# -*- coding: utf-8 -*-
"""
童年游戏厅 v2.0 - 一键安装脚本（Windows）
用法：把本文件夹整个发给别人，对方电脑装了 Python 后，双击/命令行运行本脚本即可。

会做的事：
  1. 解锁屏幕、保持常亮
  2. 用自带的 adb 安装「童年游戏厅 v2.0」APK（自动确认 OPPO/ColorOS 的安装弹窗）
  3. 把游戏数据包传到手机并解压到 /sdcard/ChildhoodArcade/
  4. 启动游戏厅（自动同意「读取存储」权限弹窗）

数据说明（RetroArch 风格目录）：
  /sdcard/ChildhoodArcade/
      games.json      游戏清单
      covers/         封面图
      nes/roms/       红白机
      arcade/roms/    街机
      gba/roms/       GBA
      md/roms/        MD
      sfc/roms/       SFC

设备要求：Android 6.0+，支持 32 位 ARM（armeabi-v7a），已开启 USB 调试。
"""
import os, re, sys, time, shutil, subprocess, threading

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.join(HERE, "童年游戏厅-v2.0-整合版-通用.apk")
PACK = os.path.join(HERE, "游戏数据包-v2.0.zip")
ADB = os.path.join(HERE, "platform-tools", "adb.exe")
PKG = "org.childhood.arcade"
ROOT = "/sdcard/ChildhoodArcade"
REMOTE_ZIP = "/sdcard/Download/arcade-games.zip"

CONFIRM_WORDS = ("继续安装", "继续", "安装", "允许", "确定", "确认")
ALLOW_WORDS = ("允许", "始终允许", "仅在使用中允许")


def find_adb():
    if os.path.isfile(ADB):
        return ADB
    return shutil.which("adb") or "adb"


def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.stdout, r.stderr, r.returncode


def sh(adb, serial, cmd, timeout=180):
    out, _, _ = run([adb, "-s", serial, "shell", cmd], timeout=timeout)
    return out


def ui_items(adb, serial):
    """Return [(text, x_center, y_center)] for on-screen text nodes."""
    sh(adb, serial, "uiautomator dump /sdcard/_ui.xml", timeout=60)
    xml = sh(adb, serial, "cat /sdcard/_ui.xml", timeout=60)
    out = []
    for m in re.finditer(r'text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        t = m.group(1)
        if t.strip():
            x1, y1, x2, y2 = map(int, m.groups()[1:])
            out.append((t, (x1 + x2) // 2, (y1 + y2) // 2))
    return out


def tap_words(adb, serial, words, rounds=40, pause=1.5):
    """Poll the screen and tap the first button whose text contains one of words."""
    for _ in range(rounds):
        try:
            items = ui_items(adb, serial)
        except Exception:
            items = []
        for t, x, y in items:
            if any(w in t for w in words):
                run([adb, "-s", serial, "shell", "input", "tap", str(x), str(y)])
                time.sleep(pause)
                return True
        time.sleep(pause)
    return False


def adb_devices(adb):
    out, _, _ = run([adb, "devices"])
    devs = []
    for line in out.splitlines()[1:]:
        m = re.match(r"(\S+)\s+device", line)
        if m:
            devs.append(m.group(1))
    return devs


def install_apk(adb, serial, apk):
    """adb install while auto-confirming the OPPO/ColorOS installer sheet."""
    box = {}

    def worker():
        try:
            out, err, _ = run([adb, "-s", serial, "install", "-r", apk], timeout=1800)
            box["out"] = out + err
        except Exception as exc:
            box["out"] = str(exc)

    th = threading.Thread(target=worker)
    th.start()
    deadline = time.time() + 900
    while th.is_alive() and time.time() < deadline:
        tap_words(adb, serial, CONFIRM_WORDS, rounds=1, pause=0.6)
        time.sleep(1.5)
    th.join()
    return box.get("out", "")


def main():
    adb = find_adb()
    print("=" * 52)
    print("童年游戏厅 v2.0  一键安装")
    print("=" * 52)

    out, err, code = run([adb, "version"])
    if code != 0:
        print("[错误] 找不到 adb，请保持本目录的 platform-tools 完整")
        input("按回车退出...")
        return

    for f in (APK, PACK):
        if not os.path.isfile(f):
            print("[错误] 缺少文件:", os.path.basename(f))
            input("按回车退出...")
            return

    print("\n[1/5] 正在检测设备（请确保平板已开 USB 调试并连接）...")
    devs = adb_devices(adb)
    if not devs:
        print("[错误] 没有检测到设备。请检查：")
        print("  1) 平板已开启「开发者选项 → USB 调试」")
        print("  2) 数据线已连接，平板弹出的授权框点了「允许」")
        ip = input("请输入设备 IP（形如 192.168.1.100），直接回车重试 USB: ").strip()
        if ip:
            run([adb, "connect", ip])
            time.sleep(2)
            devs = adb_devices(adb)
        if not devs:
            print("[错误] 仍然没有设备，请检查连接后重试")
            input("按回车退出...")
            return
    serial = devs[0]
    print("   检测到设备:", serial)

    print("\n[2/5] 正在解锁屏幕并保持常亮...")
    sh(adb, serial, "input keyevent 26")
    sh(adb, serial, "wm dismiss-keyguard")
    sh(adb, serial, "svc power stayon true")

    print("\n[3/5] 正在安装游戏厅 APK（约 88MB）...")
    print("   若弹出系统安装确认框，脚本会自动点「继续安装」")
    text = install_apk(adb, serial, APK)
    if "Success" not in text:
        print("[错误] APK 安装失败:\n", text[-600:])
        input("按回车退出...")
        return
    print("   APK 安装完成")

    print("\n[4/5] 正在传输游戏数据包（约 3.8GB，需要几分钟）...")
    print("   数据会存到 /sdcard/ChildhoodArcade/，不占手机内部存储")
    sh(adb, serial, "mkdir -p /sdcard/Download")
    out, err, code = run([adb, "-s", serial, "push", PACK, REMOTE_ZIP], timeout=3600)
    if code != 0:
        print("[错误] 数据包传输失败:\n", (out + err)[-600:])
        input("按回车退出...")
        return
    print("   传输完成，开始在手机上解压（约 1-3 分钟）...")
    sh(adb, serial, "rm -rf " + ROOT, timeout=600)
    sh(adb, serial, "unzip -o -q " + REMOTE_ZIP + " -d /sdcard/", timeout=1800)
    sh(adb, serial, "rm -f " + REMOTE_ZIP, timeout=600)
    n = sh(adb, serial, "ls " + ROOT + "/ | tr '\\n' ' '")
    if not n.strip():
        print("[错误] 解压失败，请检查手机存储空间")
        input("按回车退出...")
        return
    print("   解压完成，目录内容:", n.strip())

    print("\n[5/5] 正在启动游戏厅...")
    run([adb, "-s", serial, "shell", "am", "start", "-n", PKG + "/.MainActivity"])
    time.sleep(3)
    print("   若弹出「读取存储」权限框，脚本会自动点「允许」")
    tap_words(adb, serial, ALLOW_WORDS, rounds=12, pause=1.5)

    print("\n" + "=" * 52)
    print("安装完成！")
    print("游戏目录: /sdcard/ChildhoodArcade/（可在 设置 → 游戏资源 里切换）")
    print("=" * 52)
    try:
        input("按回车退出...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
