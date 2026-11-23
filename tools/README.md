# 工具与打包流程

| 目录 | 内容 |
|---|---|
| [`editor/`](editor/) | 游戏库编辑器源码 —— Windows 桌面端，打包成单文件 exe，双击即用 |
| [`build/`](build/) | 打包脚本：`build_apk.py` / `pack_games.py` / `build_editor.py` / `build_release.py` / `build_all.py` + `config.json` |
| [`install/`](install/) | 一键安装脚本 `安装.py` + 面向用户的 `安装说明.txt` |
| [`docs/`](docs/) | [打包流程](docs/打包流程.md) · [发布流程](docs/发布流程.md) |

## 快速上手

```powershell
# 1. 改配置（路径、工具链位置）
notepad tools\build\config.json

# 2. 密钥密码走环境变量，不进仓库
$env:ARCADE_KS_PASS = "你的keystore密码"

# 3. 一键打包
python tools\build\build_all.py --split 1900

# 4. 产物在 _out\release\，算好的 SHA256SUMS.txt 一起
```

## 编辑器

Windows 端管理 `/sdcard/ChildhoodArcade/` 游戏目录的工具：

- 预览（封面 + 完整资料）、新增、删除、编辑、批量编辑（正则）
- 匹配规则：精确 / 忽略大小写 / 去扩展名 / 模糊 / 正则 / 按哈希
- BIOS 管理：查看各平台 BIOS、校验值、引用数，一键批量改用
- **封面体检**：扫出「JPEG 内容却叫 `.png`」的封面，一键转成标准 PNG

命令行：

```bash
童年游戏厅游戏库编辑器.exe                 # 双击打开，自己选目录
童年游戏厅游戏库编辑器.exe <游戏目录>      # 直接打开指定目录
童年游戏厅游戏库编辑器.exe --selftest <目录>  # 无头自检，不开窗口
```

## 许可

编辑器源码随本仓库分发。游戏 ROM 与封面资源不在仓库里，
只作为 Release 附件提供，相关版权归各自权利人所有。
