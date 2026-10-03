# 鼠标连点器

一个 Windows 桌面鼠标连点器，使用 Python + Tkinter + ctypes 开发，调用 Windows 原生 API，无需安装第三方 Python 包。

## 功能

- 鼠标按键：左键、右键、中键
- 点击方式：单击、双击
- 点击位置：鼠标光标所在位置、指定坐标
- 点击速度：每秒 100 次、每秒 10 次、每秒 1 次、自定义毫秒间隔
- 重复方式：一直执行、重复次数、执行时长
- 全局快捷键：F8 捕获坐标，F9 开始/停止，F10 强制停止
- 配置自动保存到 `%APPDATA%\AutoClicker\settings.json`

## 运行

确保 Python 3.10+ 已安装，且包含 Tkinter。然后在项目目录执行：

```powershell
python .\autoclicker.py
```

也可以双击 `run.bat`。

## 打包成 Windows 应用程序

推荐使用 PyInstaller，本项目没有第三方依赖，打包过程比较简单。

### 安装 PyInstaller

```powershell
python -m pip install pyinstaller
```

### 打包成单个 exe

在项目目录执行：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AutoClicker autoclicker.py
```

参数说明：

- `--onefile`：打包成单个 exe
- `--windowed`：启动时不显示黑色命令行窗口
- `--name AutoClicker`：输出文件名为 `AutoClicker.exe`
- `--clean`：清理旧的临时文件

打包完成后，可执行文件位于：

```text
dist\AutoClicker.exe
```

### 打包成文件夹版

如果希望启动更快，或减少杀毒软件误报，可以不使用 `--onefile`：

```powershell
python -m PyInstaller --noconfirm --clean --windowed --name AutoClicker autoclicker.py
```

输出目录为：

```text
dist\AutoClicker\
```

### 添加程序图标

准备一个 `.ico` 文件，例如 `app.ico`，然后执行：

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AutoClicker --icon app.ico autoclicker.py
```

建议 `.ico` 包含 `256x256` 尺寸，以便在 Windows 桌面上清晰显示。

项目已附带 `app.ico`，可直接用于上面的命令。如果想重新生成图标，可执行：

```powershell
python .\make_icon.py
```

### 打包后注意事项

- 配置仍保存到 `%APPDATA%\AutoClicker\settings.json`。
- 单文件版第一次启动会稍慢，因为需要先解压临时文件。
- 如果要点击以管理员身份运行的程序，请右键 `AutoClicker.exe` 并选择“以管理员身份运行”。
- 如果杀毒软件误报，可改用文件夹版或添加信任。

## 使用说明

1. 选择鼠标按键、点击方式、点击位置和速度。
2. 如果选择“指定坐标”，可点击“捕获当前坐标”或按 F8 自动填入当前鼠标位置。
3. 点击“开始”或按 F9 开始，再次点击“停止”或按 F9 停止。
4. 如果出现异常，按 F10 可强制停止。

## 注意事项

- 如果想点击以管理员身份运行的程序，本工具也需要以管理员身份运行。
- 自定义间隔最低支持 1 毫秒；过低间隔会占用较多 CPU。
- 双击模式会先在两次点击之间等待约 30 毫秒，因此实际“动作次数/秒”会低于极高频率设置。
- 如果 F8/F9/F10 已被其他程序占用，状态栏会提示注册失败。

## 核心实现

- `SendInput`：模拟鼠标输入
- `SetCursorPos` / `GetCursorPos`：移动或读取鼠标位置
- `RegisterHotKey`：注册全局快捷键
- `timeBeginPeriod(1)` / `timeEndPeriod(1)`：提高定时精度
- 独立后台线程执行点击任务，避免阻塞界面

## License

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.