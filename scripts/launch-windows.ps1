param(
    [ValidateRange(8500, 8599)]
    [int]$Port = 8501,
    [switch]$SkipBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$dataPath = Join-Path $projectRoot "data"
$pidPath = Join-Path $dataPath "quati.pid"
$watchdogPath = Join-Path $dataPath "quati-watchdog.pid"
$shutdownRequestPath = Join-Path $dataPath "shutdown.request"
$logPath = Join-Path $dataPath "runtime.log"
$errorLogPath = Join-Path $dataPath "runtime-error.log"
$healthUrl = "http://127.0.0.1:$Port/_stcore/health"
$appUrl = "http://127.0.0.1:$Port/"
$appProcessId = 0
$manageLifecycle = $false

function Show-ErrorMessage {
    param([Parameter(Mandatory)][string]$Text)
    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        "Q.U.A.T.I.",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
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

function Test-OwnWatchdog {
    param([Parameter(Mandatory)][int]$ProcessId)

    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" `
        -ErrorAction SilentlyContinue
    if ($null -eq $processInfo -or [string]::IsNullOrWhiteSpace($processInfo.CommandLine)) {
        return $false
    }
    return (
        $processInfo.CommandLine.IndexOf($projectRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $processInfo.CommandLine.IndexOf("launch-windows.ps1", [StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Read-ControlProcessId {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return 0
    }
    $value = (Get-Content -LiteralPath $Path -Raw).Trim()
    if ($value -notmatch "^[0-9]+$") {
        return 0
    }
    return [int]$value
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

function Get-ClientConnectionCount {
    return @(
        Get-NetTCPConnection -State Established -LocalPort $Port -ErrorAction SilentlyContinue |
            Where-Object RemoteAddress -in @("127.0.0.1", "::1")
    ).Count
}

try {
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        $installer = Join-Path $projectRoot "scripts\install-windows.ps1"
        $installProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $installer
        ) -WindowStyle Normal -Wait -PassThru
        if ($installProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            throw "A instalação não foi concluída. Abra iniciar.cmd para tentar novamente."
        }
    }

    if (Test-Path -LiteralPath $dataPath) {
        $dataItem = Get-Item -LiteralPath $dataPath -Force
        if (($dataItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "A pasta data é um link e não pode ser usada com segurança."
        }
    }
    foreach ($localFile in @(
        $pidPath, $watchdogPath, $shutdownRequestPath, $logPath, $errorLogPath
    )) {
        if (Test-Path -LiteralPath $localFile) {
            $item = Get-Item -LiteralPath $localFile -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Um arquivo local de controle é um link e não pode ser usado com segurança."
            }
        }
    }

    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        $ownerPid = [int]$listeners[0].OwningProcess
        $appProcessId = Resolve-OwnProcessId -ProcessId $ownerPid
        if ($appProcessId -le 0) {
            throw "A porta local $Port está ocupada por outro programa. Feche-o antes de iniciar o Q.U.A.T.I."
        }
        Set-Content -LiteralPath $pidPath -Value $appProcessId -Encoding ascii
    } else {
        New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
        $env:QUATI_SHUTDOWN_REQUEST = $shutdownRequestPath
        $arguments = @(
            "-m", "streamlit", "run", "app.py",
            "--server.address", "127.0.0.1",
            "--server.port", $Port,
            "--server.headless", "true",
            "--server.enableXsrfProtection", "true",
            "--server.enableCORS", "true",
            "--server.maxUploadSize", "10",
            "--client.showErrorDetails", "none"
        )
        $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments `
            -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $logPath -RedirectStandardError $errorLogPath
        $appProcessId = $process.Id
        Set-Content -LiteralPath $pidPath -Value $appProcessId -Encoding ascii
    }

    $existingWatchdogId = Read-ControlProcessId -Path $watchdogPath
    if ($existingWatchdogId -gt 0 -and $existingWatchdogId -ne $PID -and
        (Test-OwnWatchdog -ProcessId $existingWatchdogId)) {
        $manageLifecycle = $false
    } else {
        $manageLifecycle = $true
        Set-Content -LiteralPath $watchdogPath -Value $PID -Encoding ascii
        Remove-Item -LiteralPath $shutdownRequestPath -Force -ErrorAction SilentlyContinue
    }

    $ready = $false
    foreach ($attempt in 1..30) {
        Start-Sleep -Milliseconds 500
        if (-not (Test-OwnProcess -ProcessId $appProcessId)) {
            throw "A aplicação encerrou durante a inicialização. Abra iniciar.cmd para reparar a instalação."
        }
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            continue
        }
    }

    if (-not $ready) {
        throw "A aplicação não respondeu no tempo esperado. Abra iniciar.cmd para reparar a instalação."
    }

    # Aguarda a conexão curta do próprio health check desaparecer antes de
    # começar a contar abas reais do navegador.
    foreach ($attempt in 1..10) {
        if ((Get-ClientConnectionCount) -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $SkipBrowser) {
        Start-Process $appUrl
    }

    if (-not $manageLifecycle) {
        exit 0
    }

    $clientWasSeen = $false
    $idleStartedAt = $null
    $connectionDeadline = (Get-Date).AddSeconds(90)
    while (Test-OwnProcess -ProcessId $appProcessId) {
        if (Test-Path -LiteralPath $shutdownRequestPath -PathType Leaf) {
            break
        }
        $clientCount = Get-ClientConnectionCount
        if ($clientCount -gt 0) {
            $clientWasSeen = $true
            $idleStartedAt = $null
        } elseif ($clientWasSeen) {
            if ($null -eq $idleStartedAt) {
                $idleStartedAt = Get-Date
            } elseif (((Get-Date) - $idleStartedAt).TotalSeconds -ge 10) {
                break
            }
        } elseif ((Get-Date) -ge $connectionDeadline) {
            throw "Nenhuma aba se conectou ao Q.U.A.T.I."
        }
        Start-Sleep -Milliseconds 500
    }
} catch {
    Show-ErrorMessage -Text $_.Exception.Message
    exit 1
} finally {
    if ($manageLifecycle -and $appProcessId -gt 0) {
        Stop-AppProcessTree -ProcessId $appProcessId
    }
    if ($manageLifecycle) {
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $watchdogPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $shutdownRequestPath -Force -ErrorAction SilentlyContinue
    }
}
