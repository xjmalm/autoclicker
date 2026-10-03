<#
.SYNOPSIS
    构建可提交到 Microsoft Store 的 MSIX 安装包。

.DESCRIPTION
    流程：PyInstaller(onedir) -> 生成图标资源 -> 组装打包目录 -> makeappx 打包。
    产物：dist\msix\AutoClicker_<版本>_<架构>.msix，可直接上传到 Partner Center。

.PARAMETER Python
    构建用的 Python 解释器路径，默认自动探测。

.PARAMETER MakeAppx
    makeappx.exe 路径，默认从 PATH 或 Windows SDK 自动探测。

.PARAMETER OutputDir
    MSIX 输出目录，默认 dist\msix。

.PARAMETER SkipAppBuild
    跳过 PyInstaller，直接复用已有的 dist\AutoClicker。

.PARAMETER SkipAssets
    跳过图标生成，直接使用 packaging\assets 中已有的文件。

.PARAMETER RequireIdentity
    store-identity.json 仍是占位符时直接报错，正式提交前建议加上。

.PARAMETER SelfSign
    用自签名证书签名，便于本机 Add-AppxPackage 验证（商店包不需要）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\packaging\build_msix.ps1 -RequireIdentity

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\packaging\build_msix.ps1 -SkipAppBuild -SelfSign
#>
[CmdletBinding()]
param(
    [string]$Python,
    [string]$MakeAppx,
    [string]$OutputDir,
    [switch]$SkipAppBuild,
    [switch]$SkipAssets,
    [switch]$RequireIdentity,
    [switch]$SelfSign
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PackagingDir = $PSScriptRoot
$BundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Fail([string]$Text) {
    Write-Host ""
    Write-Host "错误：$Text" -ForegroundColor Red
    exit 1
}

function Get-Prop($Object, [string]$Name) {
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return '' }
    return [string]$property.Value
}

function ConvertTo-XmlText([string]$Text) {
    return $Text.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;').Replace('"', '&quot;')
}

function Get-PeArchitecture([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $reader = [System.IO.BinaryReader]::new($stream)
        $stream.Position = 0x3C
        $peOffset = $reader.ReadInt32()
        $stream.Position = $peOffset + 4
        $machine = $reader.ReadUInt16()
    }
    finally {
        $stream.Dispose()
    }
    switch ($machine) {
        0x8664 { return 'x64' }
        0x014c { return 'x86' }
        0xAA64 { return 'arm64' }
        default { Fail ("无法识别的可执行文件架构（0x{0:X4}），请检查 Python 是否为 64 位。" -f $machine) }
    }
}

function Resolve-SdkTool([string]$Name, [string]$Hint) {
    if ($Hint) {
        if (Test-Path -LiteralPath $Hint) { return $Hint }
        Fail "指定的 $Name 不存在：$Hint"
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $kitRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    if (Test-Path -LiteralPath $kitRoot) {
        $found = Get-ChildItem -Path (Join-Path $kitRoot "*\x64\$Name") -ErrorAction SilentlyContinue |
            Sort-Object -Property FullName -Descending |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    Fail "未找到 $Name，请安装 Windows SDK，或改用对应参数指定路径。"
}

# ---------------------------------------------------------------- 商店身份配置

Write-Step "读取商店身份配置"
$identityPath = Join-Path $PackagingDir 'store-identity.json'
if (-not (Test-Path -LiteralPath $identityPath)) { Fail "缺少文件：$identityPath" }
$identity = Get-Content -LiteralPath $identityPath -Raw -Encoding UTF8 | ConvertFrom-Json

$fields = [ordered]@{
    identityName         = (Get-Prop $identity 'identityName')
    publisher            = (Get-Prop $identity 'publisher')
    publisherDisplayName = (Get-Prop $identity 'publisherDisplayName')
    displayName          = (Get-Prop $identity 'displayName')
    description          = (Get-Prop $identity 'description')
    version              = (Get-Prop $identity 'version')
}

$fallback = @{
    identityName         = 'AutoClicker.Dev'
    publisher            = 'CN=00000000-0000-0000-0000-000000000000'
    publisherDisplayName = 'AutoClicker Dev'
    displayName          = '鼠标连点器'
    description          = '鼠标连点器'
    version              = '1.0.0.0'
}

$pending = @()
foreach ($key in @($fields.Keys)) {
    $value = $fields[$key]
    if ([string]::IsNullOrWhiteSpace($value) -or $value -match 'TO_FILL' -or $value -match '<.*>') {
        $pending += $key
        $fields[$key] = $fallback[$key]
    }
}

if ($pending.Count -gt 0) {
    if ($RequireIdentity) {
        Fail ("store-identity.json 仍是占位符：{0}。请先在 Partner Center 预留应用名称，把身份信息填好。" -f ($pending -join '、'))
    }
    Write-Host "警告：以下字段仍是占位符，将使用开发用默认值。这样打出的包只能本机测试，不能提交商店：" -ForegroundColor Yellow
    Write-Host ("  " + ($pending -join '、')) -ForegroundColor Yellow
}

if ($fields.version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    Fail "version 必须是四段数字（例如 1.0.0.0），当前为：$($fields.version)"
}
if ($fields.publisher -notmatch '^CN=') {
    Fail "publisher 必须以 CN= 开头，请直接复制 Partner Center 上的值。"
}

# ---------------------------------------------------------------- Python 与打包

Write-Step "准备构建环境"
$pythonExe = $Python
if (-not $pythonExe) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $pythonExe = $command.Source }
}
if (-not $pythonExe -and (Test-Path -LiteralPath $BundledPython)) { $pythonExe = $BundledPython }
if (-not $pythonExe) { Fail "未找到 Python，请用 -Python 指定解释器路径。" }
if (-not (Test-Path -LiteralPath $pythonExe)) { Fail "Python 不存在：$pythonExe" }
Write-Host "Python：$pythonExe"

if (-not $SkipAppBuild) {
    Write-Step "PyInstaller 打包（onedir）"
    & $pythonExe -m PyInstaller --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Fail "该 Python 未安装 PyInstaller，请执行：`"$pythonExe`" -m pip install pyinstaller"
    }
    Push-Location $RepoRoot
    try {
        & $pythonExe -m PyInstaller --noconfirm --clean AutoClicker.spec
        if ($LASTEXITCODE -ne 0) { Fail "PyInstaller 构建失败。" }
    }
    finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------- 图标资源

Write-Step "准备图标资源"
$assetsDir = Join-Path $PackagingDir 'assets'
$requiredAssets = @('StoreLogo.png', 'Square44x44Logo.png', 'Square150x150Logo.png', 'Wide310x150Logo.png')

if (-not $SkipAssets) {
    $assetPython = $null
    foreach ($candidate in @($pythonExe, $BundledPython)) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        & $candidate -c "import PIL" *> $null
        if ($LASTEXITCODE -eq 0) {
            $assetPython = $candidate
            break
        }
    }
    if ($assetPython) {
        & $assetPython (Join-Path $PackagingDir 'make_msix_assets.py')
        if ($LASTEXITCODE -ne 0) { Fail "生成图标资源失败。" }
    }
    else {
        Write-Host "警告：未找到带 Pillow 的 Python，跳过图标生成，改用已有资源。" -ForegroundColor Yellow
    }
}

foreach ($asset in $requiredAssets) {
    if (-not (Test-Path -LiteralPath (Join-Path $assetsDir $asset))) {
        Fail "缺少图标资源 $assetsDir\$asset，请先运行 packaging\make_msix_assets.py。"
    }
}

# ---------------------------------------------------------------- 组装打包目录

Write-Step "组装打包目录"
$appDir = Join-Path $RepoRoot 'dist\AutoClicker'
$appExe = Join-Path $appDir 'AutoClicker.exe'
if (-not (Test-Path -LiteralPath $appExe)) {
    Fail "未找到 $appExe。请先执行 PyInstaller 打包，或去掉 -SkipAppBuild 参数。"
}
$arch = Get-PeArchitecture $appExe
Write-Host "程序架构：$arch"

$msixBuildDir = Join-Path $RepoRoot 'build\msix'
$layoutDir = Join-Path $msixBuildDir 'layout'
$resolvedRoot = [System.IO.Path]::GetFullPath($RepoRoot)
$resolvedBuild = [System.IO.Path]::GetFullPath($msixBuildDir)
if (-not $resolvedBuild.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Fail "构建目录不在仓库内，已中止：$resolvedBuild"
}
if (Test-Path -LiteralPath $resolvedBuild) {
    Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
}
New-Item -ItemType Directory -Path $layoutDir -Force | Out-Null

Copy-Item -Path (Join-Path $appDir '*') -Destination $layoutDir -Recurse -Force
$layoutAssets = Join-Path $layoutDir 'Assets'
New-Item -ItemType Directory -Path $layoutAssets -Force | Out-Null
Copy-Item -Path (Join-Path $assetsDir '*') -Destination $layoutAssets -Recurse -Force

$template = Get-Content -LiteralPath (Join-Path $PackagingDir 'AppxManifest.xml') -Raw -Encoding UTF8
$tokens = @{
    '{{IDENTITY_NAME}}'          = (ConvertTo-XmlText $fields.identityName)
    '{{PUBLISHER}}'              = (ConvertTo-XmlText $fields.publisher)
    '{{PUBLISHER_DISPLAY_NAME}}' = (ConvertTo-XmlText $fields.publisherDisplayName)
    '{{DISPLAY_NAME}}'           = (ConvertTo-XmlText $fields.displayName)
    '{{DESCRIPTION}}'            = (ConvertTo-XmlText $fields.description)
    '{{VERSION}}'                = $fields.version
    '{{ARCH}}'                   = $arch
}
foreach ($token in @($tokens.Keys)) {
    $template = $template.Replace($token, $tokens[$token])
}

$manifestPath = Join-Path $layoutDir 'AppxManifest.xml'
[System.IO.File]::WriteAllText($manifestPath, $template, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "已生成清单：$manifestPath"

# ---------------------------------------------------------------- 打包 MSIX

Write-Step "生成资源索引（resources.pri）"
$makepriExe = Resolve-SdkTool 'makepri.exe' $null
$priConfigPath = Join-Path $msixBuildDir 'priconfig.xml'
$priPath = Join-Path $layoutDir 'resources.pri'
& $makepriExe createconfig /cf $priConfigPath /dq lang-zh-CN /o | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "makepri createconfig 失败。" }
# 默认配置会按缩放级别额外拆出 resources.scale-*.pri，那些文件属于独立资源包，
# 放进主包会导致 makeappx 打包失败。这里只保留语言维度，让各倍率图标全部进入主资源索引。
$priConfigText = Get-Content -LiteralPath $priConfigPath -Raw
$priConfigText = [regex]::Replace($priConfigText, '\s*<autoResourcePackage qualifier="(Scale|DXFeatureLevel)"\s*/>', '')
[System.IO.File]::WriteAllText($priConfigPath, $priConfigText, (New-Object System.Text.UTF8Encoding($false)))
& $makepriExe new /pr $layoutDir /cf $priConfigPath /of $priPath /o | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "makepri 生成 resources.pri 失败。" }
if (-not (Test-Path -LiteralPath $priPath)) { Fail "未生成 resources.pri。" }
Write-Host "已生成：$priPath"

Write-Step "调用 makeappx 打包"
$makeappxExe = Resolve-SdkTool 'makeappx.exe' $MakeAppx
Write-Host "makeappx：$makeappxExe"
$outputDirectory = if ($OutputDir) { $OutputDir } else { Join-Path $RepoRoot 'dist\msix' }
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$packagePath = Join-Path $outputDirectory ("AutoClicker_{0}_{1}.msix" -f $fields.version, $arch)

& $makeappxExe pack /d $layoutDir /p $packagePath /o
if ($LASTEXITCODE -ne 0) { Fail "makeappx 打包失败，请查看上面的错误信息。" }

if ($SelfSign) {
    Write-Step "自签名（仅用于本机测试）"
    $signtoolExe = Resolve-SdkTool 'signtool.exe' $null
    $subject = 'CN=AutoClicker Dev'
    $cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq $subject } | Select-Object -First 1
    if (-not $cert) {
        Write-Host "创建自签名证书：$subject"
        $cert = New-SelfSignedCertificate -Type Custom -Subject $subject -FriendlyName 'AutoClicker MSIX Dev' `
            -KeyUsage DigitalSignature -CertStoreLocation 'Cert:\CurrentUser\My' `
            -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3')
    }
    & $signtoolExe sign /fd SHA256 /sha1 $cert.Thumbprint $packagePath
    if ($LASTEXITCODE -ne 0) { Fail "签名失败。" }
    $cerPath = Join-Path $outputDirectory 'AutoClicker-Dev.cer'
    Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null
    Write-Host "自签名证书已导出：$cerPath"
    Write-Host "本机安装测试前，请先把该证书导入『受信任人』证书存储。"
}

# ---------------------------------------------------------------- 结果

$packageItem = Get-Item -LiteralPath $packagePath
Write-Host ""
Write-Host "打包完成" -ForegroundColor Green
Write-Host ("  包文件：{0}" -f $packageItem.FullName)
Write-Host ("  大小：{0:N2} MB" -f ($packageItem.Length / 1MB))
Write-Host ("  架构：{0}" -f $arch)

if ($pending.Count -gt 0) {
    Write-Host ""
    Write-Host "注意：当前包使用开发用占位身份，只能本机测试。" -ForegroundColor Yellow
    Write-Host "      请在 Partner Center 预留名称后更新 packaging\store-identity.json 并重新打包。" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "下一步："
Write-Host "  1. Partner Center → Apps and games → 新建产品，预留应用名称"
Write-Host "  2. 把『查看应用身份详细信息』中的值填入 packaging\store-identity.json"
Write-Host "  3. 重新运行本脚本（建议加 -RequireIdentity）"
Write-Host "  4. 在提交的『包』页上传上面这个 .msix"
Write-Host "  5. 在『Submission options』页说明 runFullTrust 的用途，参考 packaging\store-listing.md"
