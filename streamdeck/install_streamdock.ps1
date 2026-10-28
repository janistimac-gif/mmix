# Namesti mmix ikone v SOOMFON Stream Controller (program Stream Dock).
#
# Zagon iz mape projekta:
#     powershell -ExecutionPolicy Bypass -File streamdeck\install_streamdock.ps1
#
# Skripta sama zahteva skrbniske pravice, ker je program v Program Files.
# Ce je Stream Controller zagnan, ga zapri in znova zazeni, da se paket prikaze.

$ErrorActionPreference = 'Stop'

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Host "Za pisanje v Program Files so potrebne skrbniske pravice - odpiram UAC ..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $PSCommandPath)
    ) -Wait
    exit
}

$source = Join-Path $PSScriptRoot 'streamdock\mmix.sdIconPack'
if (-not (Test-Path $source)) {
    throw "Manjka $source. Najprej pozeni: python make_streamdeck_icons.py"
}

$roots = @()
if ($env:ProgramFiles) { $roots += (Join-Path $env:ProgramFiles 'Stream Controller') }
if (${env:ProgramFiles(x86)}) { $roots += (Join-Path ${env:ProgramFiles(x86)} 'Stream Controller') }
$install = $roots | Where-Object { Test-Path (Join-Path $_ 'icons') } | Select-Object -First 1
if (-not $install) {
    throw "Mape Stream Controller ni bilo mogoce najti. Kopiraj paket rocno v mapo icons."
}

$dest = Join-Path (Join-Path $install 'icons') 'mmix.sdIconPack'
try {
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    Copy-Item $source $dest -Recurse -Force
} catch {
    throw "Namestitev ni uspela: $($_.Exception.Message)"
}

# Aplikacija bere tudi uporabnisko mapo; ce je paket se tam, bi se prikazal dvakrat.
$userDest = Join-Path (Join-Path $env:APPDATA 'HotSpot\StreamDock\icons') 'mmix.sdIconPack'
if (Test-Path $userDest) {
    Remove-Item $userDest -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Odstranjen dvojnik: $userDest"
}

$running = Get-Process -Name 'Stream Controller' -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "Namestjeno: $dest"
if ($running) {
    Write-Host "Stream Controller je zagnan."
    Write-Host "Zapri ga (Exit) in znova zazeni, da se paket mmix prikaze v knjiznici ikon."
} else {
    Write-Host "Zdaj zazeni Stream Controller in odpri knjiznico ikon."
}
