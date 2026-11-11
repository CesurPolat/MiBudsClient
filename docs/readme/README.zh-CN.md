[English](../../README.md) · [Türkçe](README.tr.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md) · [Русский](README.ru.md) · **简体中文**

<div align="center">

<img src="../../assets/icon.png" alt="MiBudsClient 图标" width="88">

# MiBudsClient

**在电脑上管理你的小米和 Redmi 耳机。**

集中查看电量、切换低延迟、调整音效和触控操作。<br>
使用 Python 和 Flet 开发，适用于 Windows 和 Linux。

[**下载**](https://github.com/CesurPolat/MiBudsClient/releases) · [快速开始](#快速开始) · [从源码运行](#从源码运行) · [反馈问题](https://github.com/CesurPolat/MiBudsClient/issues)

<img src="../MiBudsClientPreview.png" alt="MiBudsClient 桌面界面预览" width="720">

</div>

## 功能

| 功能 | 说明 |
| --- | --- |
| 噪声控制 | 根据设备目录提供 ANC、通透和型号对应的等级选项。各型号的硬件兼容性仍待验证。 |
| 电量监测 | 分别显示左右耳机和充电盒的电量、充电状态，并支持手动刷新。 |
| 低延迟 | 手动关闭、开启游戏模式，或根据当前应用自动切换。 |
| 音效预设 | 读取并切换耳机提供的 EQ 预设。 |
| 触控操作 | 分别读取和修改左右耳机的单击、双击、三击与长按操作。 |
| 桌面通知 | 连接、断开及入盒和出盒通知；有数据时附带电量和设备图片。 |
| 系统托盘 | 后台运行、恢复窗口，并从托盘切换低延迟模式。 |
| 日常使用 | 自动尝试连接、开机启动、保存偏好设置和检查更新。 |
| 多语言 | 24 种语言、27 个区域选项，即时切换，并支持阿拉伯语从右向左布局。 |

## 兼容性

**MiBudsClient 面向多款 Xiaomi 和 Redmi 耳机开发。** 在 Windows 上，应用会尝试连接目录中识别到的设备，并根据各型号的功能列表与选项启用已实现的控件，不需要单独的型号审批名单。

- **已实现功能：** 电量、ANC/通透、EQ 预设、支持的触控手势和低延迟。选项取决于型号，电量取决于设备实际返回的数据。
- **Windows：** 动态发现 RFCOMM 通道；MIUI SPP（FD2D）使用命令认证，XiaoAI/标准 SPP 使用原始认证。
- **Linux：** 通过 BlueZ SDP 记录按完整服务 UUID 动态发现 RFCOMM 通道，并根据服务选择认证方式。只有在无法解析任何服务通道时，Redmi Buds 6 Play 才使用通道 6 回退。硬件兼容性仍取决于设备和固件。
- **硬件依据：** Redmi Buds 6 Play 是项目的参考设备，已有电量/低延迟使用记录以及下方注明日期的 EQ/手势检查。这不代表所有型号都已验证；ANC/通透和原始认证仍需实机确认。

名称、VID/PID、图片和能力数据来自[设备目录](../../assets/device_catalog.json)。识别到型号并不保证协议会话可用。控件按目录提供，操作能否完成还取决于连接和设备响应。固件和地区版本可能存在差异。

自定义 EQ 推迟到后续版本，目前连同自定义预设一起隐藏。目录中的其他功能不会自动变成应用控件。

自动游戏模式：GNOME 46 Wayland 会自动配置，如有提示请重新登录。KDE Plasma 6 需要支持 `kwinscript` 的 `kdotool`，Sway 需要 `swaymsg`，Hyprland 需要 `hyprctl`。这三个新后端尚未经过实际桌面会话验证。X11 不需要扩展。[详情](../wayland.md)。

本 README 描述当前源码，旧的发行包可能不包含这些更新。技术详情：[设备能力](../device-capabilities.md)、[命令认证](../command-auth.md)、[原始认证](../raw-auth.md)（英文）。

MiBudsClient 是独立社区项目，与小米没有隶属关系。

## 快速开始

1. 在电脑蓝牙设置中配对并连接耳机。
2. 从 [Releases](https://github.com/CesurPolat/MiBudsClient/releases) 下载当前平台的安装包，或[从源码运行](#从源码运行)。
3. 启动应用。它会查找已连接且在目录中的设备，并自动尝试建立蓝牙控制连接。
4. 连接后查看电量及该型号可用的控件。在**设置**中管理支持的手势、EQ、噪声控制、开机启动和语言。

配对由操作系统负责；应用需要已有的蓝牙连接。同时只运行一个实例，再次启动会将已有窗口置于前台。使用托盘菜单的退出命令可完全关闭程序。

按 **F12** 查看运行日志。在 Linux 上，请先聚焦 MiBudsClient，再打开内置控制台；可选择、复制或清空日志。再次按 F12 关闭。Windows 仍使用独立控制台窗口。控制台关闭时仍会收集日志。

## 使用说明

### 低延迟模式

- **关闭：** 标准模式。
- **开启：** 手动启用低延迟。
- **自动：** 全屏应用启用低延迟。**包含**可在应用非全屏时也启用，**排除**会跳过该应用。

**等待应用关闭**会保持低延迟，直到匹配的应用退出。Windows 和 Linux 的规则分别保存。

### 均衡器

打开**设置 → 均衡器**读取当前音效，并选择该型号目录中列出的预设。更改后等待设备确认，再重新读取以验证结果。

**自定义 EQ 计划在后续版本提供。** 即使目录中存在，自定义预设和频段编辑器目前仍隐藏。

已于 **2026-10-27** 在 Redmi Buds 6 Play 上验证预设切换；这不代表其他型号已通过实机验证。历史实现和验证说明见 [EQ 技术笔记](../equalizer.md)（英文）。

### 触控手势

打开**设置 → 手势**读取操作分配。左右耳机选项独立，可选操作来自该型号的准确目录记录。修改立即发送，只有重新读取并验证后才显示已保存。分配保存在耳机中。当前不包含 ANC 模式循环编辑。

已于 **2026-10-26** 验证读取分配和将原有值写回。改为其他功能后实际触发手势，仍需人工验证。

### 通知与语言

通知会在有数据时显示电量。入盒和出盒通过充电标志推断，并非读取独立的充电盒或佩戴传感器。断开时显示最后已知电量。

点击通知可恢复窗口；Linux 通知服务必须支持默认操作。系统通知声音会被抑制。应用会在充电状态变化时播放自己的旋律，并在每次运行期间首次成功连接耳机时播放一次连接旋律。

在**设置 → 语言**选择系统语言或指定语言。选择会被保存，并立即应用于界面、托盘及之后的通知。不支持的系统语言会回退到英语。

可用语言：阿拉伯语、中文（简体、台湾、香港）、荷兰语、英语、爱沙尼亚语、芬兰语、法语、德语、印地语、匈牙利语、印度尼西亚语、意大利语、日语、韩语、马来语、波兰语、葡萄牙语（巴西和葡萄牙）、俄语、西班牙语、瑞典语、泰语、土耳其语、乌克兰语和越南语。

## 从源码运行

需要带有 `venv` 和 `pip` 的 Python、蓝牙适配器及已通过系统连接的耳机。

```sh
git clone https://github.com/CesurPolat/MiBudsClient.git
cd MiBudsClient
```

**Windows — PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

**Linux**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Linux 需要 BlueZ 的 `bluetoothctl` 进行发现，并需要 PyGObject（`gi`）搭配 AppIndicator3 或 GTK 提供托盘支持。X11 全屏检测还需要 `xprop`、`xwininfo` 和 `xrandr`。这些是系统依赖；`requirements.txt` 仅安装 Python 软件包。

动态 RFCOMM 服务发现还需要 BlueZ 的 `sdptool`，部分发行版将其单独打包。

## 故障排查

| 问题 | 检查方法 |
| --- | --- |
| 找不到耳机 | 开启蓝牙，在系统设置中确认连接后重试。 |
| 连接超时 | 耳机保持开机并靠近电脑。关闭电脑蓝牙，等待 10 秒再打开。必要时将两只耳机放入盒中，合盖 5 秒，再取出重试。 |
| 无电量读数 | 连接后检查电量。缺失数据视为未知。 |
| 手势或 EQ 失败 | 关闭并重新打开分区以读取设备状态。 |
| 无自定义 EQ | 本版本已推迟并隐藏自定义 EQ；型号支持的预设仍可使用。 |
| Linux 自动模式无效 | 自动游戏模式：GNOME 46 Wayland 会自动配置，如有提示请重新登录。KDE Plasma 6 需要支持 `kwinscript` 的 `kdotool`，Sway 需要 `swaymsg`，Hyprland 需要 `hyprctl`。这三个新后端尚未经过实际桌面会话验证。X11 不需要扩展。[详情](../wayland.md)。 |
| Linux 通知点击无效 | 检查默认操作支持，或从托盘打开窗口。 |

[反馈问题](https://github.com/CesurPolat/MiBudsClient/issues)时，请提供应用版本、系统和桌面会话、型号、复现步骤及错误详情。

## 开发

`main.py` 负责启动和连接组件。`controllers/` 包含蓝牙、设备状态、低延迟及设置逻辑；`ui/` 包含 Flet 界面、托盘和通知；`utils/` 包含平台辅助工具。资源在 `assets/`，测试在 `tests/`，文档在 `docs/`。

在开发环境中，从仓库根目录运行：

```sh
python -m unittest discover -s tests
```

测试协议变更时，请记录具体型号、固件、操作系统、连接方式和测试功能。模拟数据包不能证明硬件兼容性；实机报告是证据，而不是按型号启用功能的门槛。修改设备行为或打包前请阅读 [AGENTS.md](../../AGENTS.md)。

界面翻译位于 `assets/locales/`。键名、占位符和小米资源导入见[本地化指南](../localization.md)（英文）。功能或安装变化时，应将 `docs/readme/` 与英文 README 同步更新。

### 构建可执行文件

确保当前环境可使用 Flet CLI，然后在目标平台运行：

**Windows — PowerShell**

```powershell
flet pack main.py --icon assets\icon.ico --add-data "assets:assets" --name "MiBudsClient"
```

**Linux**

```sh
flet pack main.py --icon assets/icon.ico --add-data "assets:assets" --name "MiBudsClient" --hidden-import optparse
```

界面资源必须放在 `assets/` 下才能打包。发布前用耳机验证可执行文件；再次启动应激活已有窗口，第二个实例应静默退出。

## 许可证

MiBudsClient 使用 [GNU 通用公共许可证 v3.0](../../LICENSE)。
