# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 构建配置（onedir，供 MSIX 打包使用）。

用法：
    python -m PyInstaller --noconfirm --clean FigAutoClicker.spec

产物：
    dist\\FigAutoClicker\\FigAutoClicker.exe 以及同目录的 _internal 依赖目录

几点说明：

- 商店版必须用 onedir。MSIX 安装后的程序目录是只读且被系统锁定的，
  onefile 每次启动都要先往临时目录解压，既慢又更容易被杀毒软件拦截。
- upx 关闭。UPX 压缩会明显提高杀毒软件误报概率，得不偿失。
- manifest 指向 packaging/app.manifest，声明以普通用户权限运行并开启
  高 DPI 感知，与商店包的运行方式保持一致。
- 版本号取自 autoclicker.py 的 __version__，并写入 exe 的版本资源；MSIX 的四段
  包版本由 packaging/build_msix.ps1 从同一个值派生，两处不会各写一份。

只想生成免安装的单文件版本时，可以不使用本 spec，直接执行：
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name FigAutoClicker --icon app.ico autoclicker.py
"""

import re
from pathlib import Path

# SPECPATH 是 PyInstaller 提供的 spec 所在目录，用它拼绝对路径，这样在任何工作目录下
# 执行都不会因为相对路径找不到文件。
SPEC_DIR = Path(SPECPATH)
SOURCE_FILE = SPEC_DIR / 'autoclicker.py'


def read_app_version() -> str:
    """从源码读取 __version__，避免版本号在多处维护。"""
    text = SOURCE_FILE.read_text(encoding='utf-8')
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit('在 autoclicker.py 中找不到 __version__ 定义')
    version = match.group(1)
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise SystemExit(f'__version__ 必须是三段数字，当前为：{version}')
    return version


APP_VERSION = read_app_version()
# 四段式版本号：前三段与用户可见版本一致，第四段固定为 0（商店保留字段）。
PACKAGE_VERSION = APP_VERSION + '.0'

# 生成 exe 的 Windows 版本资源，资源管理器「属性 → 详细信息」读的就是这里。
VERSION_FILE = SPEC_DIR / 'build' / 'version_info.txt'
VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
VERSION_FILE.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({APP_VERSION.replace('.', ', ')}, 0),
    prodvers=({APP_VERSION.replace('.', ', ')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [StringStruct('CompanyName', '闲人老马'),
         StringStruct('FileDescription', '鼠标连点器'),
         StringStruct('FileVersion', '{PACKAGE_VERSION}'),
         StringStruct('InternalName', 'FigAutoClicker'),
         StringStruct('LegalCopyright', 'Copyright (C) 2026 闲人老马. MIT License.'),
         StringStruct('OriginalFilename', 'FigAutoClicker.exe'),
         StringStruct('ProductName', 'FigAutoClicker'),
         StringStruct('ProductVersion', '{APP_VERSION}')])
      ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
""",
    encoding='utf-8',
)

a = Analysis(
    [str(SOURCE_FILE)],
    pathex=[],
    binaries=[],
    datas=[(str(SPEC_DIR / 'app.ico'), '.')],
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
    name='FigAutoClicker',
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
    icon=[str(SPEC_DIR / 'app.ico')],
    manifest=str(SPEC_DIR / 'packaging' / 'app.manifest'),
    version=str(VERSION_FILE),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FigAutoClicker',
)
