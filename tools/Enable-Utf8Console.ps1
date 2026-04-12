[CmdletBinding()]
param()

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

try {
    [Console]::InputEncoding = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
} catch {
    # Some hosts do not allow resetting console encodings; keep the script safe.
}

$global:OutputEncoding = $utf8NoBom
$PSDefaultParameterValues["*:Encoding"] = "utf8"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

try {
    chcp 65001 > $null
} catch {
    # Ignore hosts without chcp.
}

Write-Host "[UTF8] Console session initialized."
Write-Host "[UTF8] PowerShell default text encoding: utf8"
Write-Host "[UTF8] Python output encoding: utf-8"
Write-Host "[UTF8] You can now run Chinese logs and encoding guards in this session."
