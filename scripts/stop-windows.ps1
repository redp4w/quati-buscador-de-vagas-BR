param(
    [ValidateRange(8500, 8599)]
    [int]$Port = 8501,
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidPath = Join-Path $projectRoot "data\quati.pid"
$watchdogPath = Join-Path $projectRoot "data\quati-watchdog.pid"
$shutdownRequestPath = Join-Path $projectRoot "data\shutdown.request"

function Show-Message {
    param(
        [Parameter(Mandatory)][string]$Text,
        [System.Windows.Forms.MessageBoxIcon]$Icon = [System.Windows.Forms.MessageBoxIcon]::Information
    )
    if ($Quiet) {
        Write-Output $Text
        return
    }
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        "Q.U.A.T.I.",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        $Icon
    ) | Out-Null
}

function Test-OwnProcess {
    param([Parameter(Mandatory)][int]$ProcessId)

    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $processInfo -or [string]::IsNullOrWhiteSpace($processInfo.CommandLine)) {
        return $false
    }
    $commandLine = $processInfo.CommandLine
    return (
        $commandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine.IndexOf("streamlit", [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine.IndexOf("app.py", [StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Resolve-OwnProcessId {
    param([Parameter(Mandatory)][int]$ProcessId)

    $visited = [System.Collections.Generic.HashSet[int]]::new()
    $currentId = $ProcessId
    foreach ($depth in 1..12) {
        if ($currentId -le 0 -or -not $visited.Add($currentId)) {
            break
        }
        if (Test-OwnProcess -ProcessId $currentId) {
            return $currentId
        }
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $currentId" `
            -ErrorAction SilentlyContinue
        if ($null -eq $processInfo) {
            break
        }
        $currentId = [int]$processInfo.ParentProcessId
    }
    return 0
}

function Stop-AppProcessTree {
    param([Parameter(Mandatory)][int]$ProcessId)

    if (-not (Test-OwnProcess -ProcessId $ProcessId)) {
        return
    }
    $processTable = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $pending = [System.Collections.Generic.Stack[int]]::new()
    $ordered = [System.Collections.Generic.List[int]]::new()
    $pending.Push($ProcessId)
    while ($pending.Count -gt 0) {
        $currentId = $pending.Pop()
        $ordered.Add($currentId)
        foreach ($child in @($processTable | Where-Object ParentProcessId -eq $currentId)) {
            $pending.Push([int]$child.ProcessId)
        }
    }
    $processIds = $ordered.ToArray()
    [array]::Reverse($processIds)
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

try {
    $candidateIds = @()
    $dataPath = Split-Path -Parent $pidPath
    if (Test-Path -LiteralPath $dataPath) {
        $dataItem = Get-Item -LiteralPath $dataPath -Force
        if (($dataItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "A pasta data é um link e não será acessada."
        }
    }
    if (Test-Path -LiteralPath $pidPath -PathType Leaf) {
        $pidItem = Get-Item -LiteralPath $pidPath -Force
        if (($pidItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "O arquivo de controle é um link e não será acessado."
        }
        $storedPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
        if ($storedPid -match "^[0-9]+$") {
            $candidateIds += [int]$storedPid
        }
    }
    $candidateIds += @(
        Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess
    )

    $stopped = $false
    foreach ($candidateId in ($candidateIds | Select-Object -Unique)) {
        $resolvedId = Resolve-OwnProcessId -ProcessId ([int]$candidateId)
        if ($resolvedId -gt 0) {
            Stop-AppProcessTree -ProcessId $resolvedId
            $stopped = $true
        }
    }

    foreach ($controlPath in @($pidPath, $watchdogPath, $shutdownRequestPath)) {
        Remove-Item -LiteralPath $controlPath -Force -ErrorAction SilentlyContinue
    }

    if ($stopped) {
        Show-Message -Text "Q.U.A.T.I. encerrado."
    } else {
        Show-Message -Text "O Q.U.A.T.I. já estava encerrado."
    }
} catch {
    Show-Message -Text $_.Exception.Message -Icon ([System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}
