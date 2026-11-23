## 🎮 童年游戏厅 v2.0 整合版

在官方 v2.0 基础上做的整合定制版：**976 款游戏全部中文名**、游戏和封面改放 sdcard、
街机换 FBNeo 内核、加了 CRT 扫描线着色器和街机面框。

### 📦 下载

| 文件 | 说明 |
|---|---|
| `childhood-arcade-2.0.0-integrated-universal.apk` | **主程序**（157 MB，32+64 位都有，绝大多数设备装这个）|
| `childhood-arcade-2.0.0-integrated-arm32.apk` | 仅 32 位（88 MB，老电视盒子用）|
| `childhood-arcade-2.0.0-integrated-arm64.apk` | 仅 64 位（94 MB，新设备）|
| `childhood-arcade-games-2.0.0.chunk11` ~ `.chunk31` | **游戏数据**（3.9 GB，9 个分片，见下方说明）|
| `childhood-arcade-editor-2.0.0.exe` | **游戏库编辑器**（Windows 单文件，双击即用）|
| `childhood-arcade-editor-src-2.0.0.zip` | 编辑器源码 + 全部打包脚本 + 流程文档 |
| `merge-games-data.py` | 把 9 个分片合并回完整 zip |
| `install.py` / `README-install.txt` | 一键安装脚本 / 安装说明 |
| `SHA256SUMS.txt` | 所有附件的 SHA256，下载后可校验 |

### 📥 游戏数据怎么用

GitHub 单个附件上限 2 GB，3.9 GB 的数据包切成了 9 个分片（每个 ≤500 MB，
实测这是能稳定传完的上限）：

| 分片 | 大小 | 对应原始卷 |
|---|---|---|
| `chunk11` `chunk12` `chunk13` `chunk14` | 500+500+500+400 MB | 第 1 卷 |
| `chunk21` `chunk22` `chunk23` `chunk24` | 500+500+500+400 MB | 第 2 卷 |
| `chunk31` | 161 MB | 第 3 卷 |

1. 把 **9 个分片全部下下来**，放同一个文件夹
2. 跑 `merge-games-data.py`（Windows 双击即可），会生成完整的
   `childhood-arcade-games-2.0.0.zip`
3. 把 zip 传到手机 `/sdcard/`，然后解压：

```bash
adb shell unzip -o /sdcard/childhood-arcade-games-2.0.0.zip -d /sdcard/
```

合并完的 zip 校验值：`b94d5949082a946e3df4b196ef1434afaca772236e14f04d1d752ca54df3bb83`
（`SHA256SUMS.txt` 里也有每个分片的单独校验值）。

或者用 `install.py` 一键搞定（自动解锁、自动点 OPPO 安装确认、自动同意存储权限）。

也可以手动：把 zip 拷到手机，用「解压」类应用解开到 `/sdcard/`，
最终目录应该是：

```
/sdcard/ChildhoodArcade/
├── nes/      games.json  covers/  roms/
├── arcade/   games.json  covers/  roms/   ← 含 neogeo.zip / pgm.zip 等 BIOS
├── gba/      games.json  covers/  roms/
├── md/       games.json  covers/  roms/
└── sfc/      games.json  covers/  roms/
```

游戏厅里 **设置 → 游戏资源 → 游戏目录** 可以换到别的目录。

### ✨ 这版的改动

**游戏库**
- **976 款游戏全部中文名**（原来还有 60 多个英文名，比如 `captcomm` → 上尉密令、
  `Cross Fire` → 霹雳火、`Shufflepuck Cafe` → 浮球大赛）
- 英文原名、拼音、首字母缩写都保留在「别名」里，搜 `captcomm`、`kof97` 照样搜得到
- 去掉两款跑不了的：合金弹头3 改版 `mslug3nd`（中文盗版，任何内核都无驱动）、
  热血硬派2 `pwrinst2`（MAME 格式 ROM，跟 FBNeo 对不上）
- **全库 976 款逐个实机加载实测通过**，没有装得上跑不起来的

**画面**
- CRT 着色器：关 / 扫描线 / 全开（带荫罩和暗角），设置里切
- RGNE 街机面框，竖屏游戏（打飞机）自动旋转
- FBNeo 街机内核，含 4 个金属弹头改版专用内核

**存储**
- 改成 RetroArch 风格：游戏、封面、BIOS 全在 sdcard，可以自己增删
- 每个平台一个**格式化**的 `games.json`，可以直接手改
- 封面和 ROM 不进 APK，所以 APK 只有 88~157 MB

**编辑器（Windows）**
- 预览 / 新增 / 删除 / 编辑 / 批量编辑（正则）/ 匹配规则 / BIOS 管理
- **封面体检**：扫出「JPEG 内容却叫 `.png`」的封面，一键转成标准 PNG
  （这类封面在 Windows 上预览会空白，编辑器新加了 Pillow 兜底，别的格式也能预览）
- 单文件 exe，双击即用，不需要装 Python

### 🛠 给开发者

- 源码、构建脚本、打包与发布流程都在仓库的 [`tools/`](https://github.com/stevenliuit/childhood-arcade/tree/main/tools)
- 打包不需要 Gradle，直接用 aapt2 + d8 + zipalign + apksigner
- 数据包超 2 GB 有自动分卷脚本

### ⚠️ 注意

- 安装时手机别锁屏，OPPO 的安装界面要点「继续安装」
- 第一次启动要授「读取存储」权限
- 街机如果报「当前游戏未能完成初始化」，检查 `arcade/roms/` 里有没有 `neogeo.zip` / `pgm.zip`
- 游戏 ROM 与封面资源不随源码分发，相关版权归各自权利人所有，请遵守适用授权条件
