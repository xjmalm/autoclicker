# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 构建配置（onedir，供 MSIX 打包使用）。

用法：
    python -m PyInstaller --noconfirm --clean AutoClicker.spec

产物：
    dist\\AutoClicker\\AutoClicker.exe 以及同目录的 _internal 依赖目录

几点说明：

- 商店版必须用 onedir。MSIX 安装后的程序目录是只读且被系统锁定的，
  onefile 每次启动都要先往临时目录解压，既慢又更容易被杀毒软件拦截。
- upx 关闭。UPX 压缩会明显提高杀毒软件误报概率，得不偿失。
- manifest 指向 packaging/app.manifest，声明以普通用户权限运行并开启
  高 DPI 感知，与商店包的运行方式保持一致。

只想生成免安装的单文件版本时，可以不使用本 spec，直接执行：
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name AutoClicker --icon app.ico autoclicker.py
"""

a = Analysis(
    ['autoclicker.py'],
    pathex=[],
    binaries=[],
    datas=[('app.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoClicker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
    manifest='packaging/app.manifest',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AutoClicker',
)
