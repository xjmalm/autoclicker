# 商店提交文案模板

以下内容按 Partner Center 的表单顺序整理，可直接改写后粘贴。英文部分建议保留，
认证团队以英文审核为主。

## 基本信息

- 产品名称：鼠标连点器（或你预留的正式名称）
- 类别：实用工具和工具 → 生产力
- 支持的设备：PC（Windows 10 2004 / build 19041 及以上）
- 定价：免费

## 简短介绍（用于描述开头）

鼠标连点器，按 F9 开始或停止自动点击。支持左中右键、单击双击、固定坐标、
每秒最多 100 次以及按次数或时长自动停止，全部离线运行。

## 详细描述

鼠标连点器是一个轻量的 Windows 自动点击工具，使用系统原生输入接口实现，
不需要安装运行库，也不联网。

主要功能：

- 鼠标按键：左键、右键、中键
- 点击方式：单击、双击
- 点击位置：跟随鼠标光标，或使用 F8 捕获的固定坐标
- 点击速度：每秒 100 次、每秒 10 次、每秒 1 次，或自定义毫秒间隔
- 停止条件：一直执行、执行固定次数、执行固定时长
- 全局快捷键：F8 捕获坐标，F9 开始或停止，F10 强制停止
- 自动保存配置，下次启动沿用上次设置

使用说明：

1. 选择鼠标按键、点击方式、点击位置和速度。
2. 选择“指定坐标”时，可点击“捕获当前坐标”或按 F8 自动填入当前鼠标位置。
3. 点击“开始”或按 F9 开始，再次点击“停止”或按 F9 停止。
4. 出现异常时按 F10 强制停止。

已知限制：

- 本应用以普通用户权限运行，无法点击以管理员权限运行的程序。
- 自定义间隔最低 1 毫秒，间隔过小会占用较多 CPU。

## 产品功能（最多 20 条）

- 全局热键 F9 一键开始停止
- F8 捕获当前鼠标坐标
- F10 强制停止
- 支持左键、右键、中键
- 支持单击与双击
- 每秒 100 次高速连点
- 自定义毫秒级间隔
- 按次数或时长自动停止
- 设置自动保存
- 完全离线运行，不收集任何数据

## 搜索关键词（最多 7 个）

连点器、自动点击、鼠标点击、自动化、auto clicker、快捷键、效率工具

## 系统要求

- 操作系统：Windows 10 版本 2004（内部版本 19041）或更高版本
- 体系结构：x64
- 内存：不适用（应用体积小于 50 MB）
- 其他：无需联网

## 支持信息

- 支持联系邮箱：<填写你的邮箱>
- 支持页面：<填写 GitHub 仓库或主页地址>
- 隐私政策 URL：<填写一页说明“本应用不收集任何数据”的页面地址>

## 受限能力说明（Submission options 页）

清单声明了 `runFullTrust`，粘贴以下英文说明：

> This is a full-trust desktop application packaged as MSIX. It needs the
> runFullTrust capability for two reasons: (1) it registers global hotkeys with
> RegisterHotKey so the user can start and stop clicking while another
> application has focus, and (2) it simulates mouse input with SendInput, which
> is the core feature of the product. The app does not read user documents, does
> not access the network, does not collect any personal data, and always runs
> with the standard user token (asInvoker).

## 认证备注（Notes for certification）

粘贴以下英文说明，帮助测试人员快速验证功能：

> No account or network connection is required. Launch AutoClicker.exe, leave
> the defaults (left button, single click, follow cursor, 1 click per second),
> then press F9 to start and F9 again to stop. Press F8 to capture the current
> cursor position into the fixed-coordinate fields, and F10 to force stop. The
> window stays open after clicking starts; the click counter is shown in the
> status bar at the bottom.
>
> The product simulates mouse clicks by design; this is a general-purpose
> automation utility, not a game or a game modification. It runs only from user
> input, never starts automatically, and never modifies other applications.
