Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$uvVersion = "0.11.32"

function Show-Message {
    param(
        [Parameter(Mandatory)]
        [string]$Text,
        [string]$Title = "Q.U.A.T.I.",
        [System.Windows.Forms.MessageBoxIcon]$Icon = [System.Windows.Forms.MessageBoxIcon]::Information
    )

    [System.Windows.Forms.MessageBox]::Show(
        $Text,
        $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        $Icon
    ) | Out-Null
}

function Resolve-Uv {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe"),
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

function Invoke-Uv {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    & $script:uvPath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Uma etapa do instalador falhou. Código: $LASTEXITCODE"
    }
}

$confirmation = [System.Windows.Forms.MessageBox]::Show(
    "O instalador baixará o gerenciador uv $uvVersion (se necessário), Python 3.12, as bibliotecas verificadas no arquivo uv.lock e o Chromium usado pelo Q.U.A.T.I.`n`nTudo será instalado para o usuário atual. Deseja continuar?",
    "Instalar Q.U.A.T.I.",
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
)
if ($confirmation -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 0
}

try {
    Set-Location -LiteralPath $projectRoot
    $requiredFiles = @(
        "iniciar.cmd",
        "pyproject.toml",
        "uv.lock",
        "app.py",
        "scripts\launch-windows.ps1",
        "src\quati\assets\quati-icon.ico"
    )
    foreach ($relativePath in $requiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relativePath) -PathType Leaf)) {
            throw "O download está incompleto: $relativePath não foi encontrado. Extraia novamente todo o ZIP do projeto."
        }
    }

    $driveRoot = [IO.Path]::GetPathRoot($projectRoot)
    $drive = [IO.DriveInfo]::new($driveRoot)
    if ($drive.IsReady -and $drive.AvailableFreeSpace -lt 2GB) {
        throw "Separe pelo menos 2 GB livres para Python, bibliotecas e Chromium."
    }

    $stopper = Join-Path $projectRoot "scripts\stop-windows.ps1"
    if (Test-Path -LiteralPath (Join-Path $projectRoot "data\quati.pid") -PathType Leaf) {
        $stopProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $stopper, "-Quiet"
        ) -WindowStyle Hidden -Wait -PassThru
        if ($stopProcess.ExitCode -ne 0) {
            throw "Não foi possível encerrar a versão anterior do Q.U.A.T.I."
        }
    }
    $script:uvPath = Resolve-Uv

    if ($null -eq $script:uvPath) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($null -eq $winget) {
            throw "O Instalador de Aplicativos do Windows precisa estar atualizado. Abra a Microsoft Store, procure por 'Instalador de Aplicativos', atualize-o e execute este instalador novamente."
        }

        Write-Host "1/5 Instalando o gerenciador de ambiente..."
        & $winget.Source install --id astral-sh.uv --version $uvVersion -e --source winget --scope user --accept-source-agreements --accept-package-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) {
            throw "Não foi possível instalar o uv pelo Instalador de Aplicativos do Windows."
        }

        $script:uvPath = Resolve-Uv
        if ($null -eq $script:uvPath) {
            throw "O uv foi instalado, mas o executável não foi localizado. Reinicie o Windows e tente novamente."
        }
    } else {
        Write-Host "1/5 Gerenciador de ambiente encontrado."
    }

    Write-Host "2/5 Instalando Python 3.12..."
    Invoke-Uv -Arguments @("python", "install", "3.12")

    Write-Host "3/5 Instalando as bibliotecas verificadas..."
    Invoke-Uv -Arguments @("sync", "--python", "3.12", "--frozen")

    Write-Host "4/5 Instalando o Chromium..."
    Invoke-Uv -Arguments @("run", "playwright", "install", "chromium")

    Write-Host "5/5 Validando a aplicação..."
    Invoke-Uv -Arguments @("run", "streamlit", "version")

    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Q.U.A.T.I.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $projectRoot "iniciar.cmd"
    $shortcut.WorkingDirectory = $projectRoot
    $iconPath = Join-Path $projectRoot "src\quati\assets\quati-icon.ico"
    if (Test-Path -LiteralPath $iconPath -PathType Leaf) {
        $shortcut.IconLocation = "$iconPath,0"
    }
    $shortcut.Description = "Abrir o Q.U.A.T.I."
    $shortcut.Save()

    $startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Q.U.A.T.I"
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
    $menuShortcut = $shell.CreateShortcut((Join-Path $startMenu "Q.U.A.T.I.lnk"))
    $menuShortcut.TargetPath = Join-Path $projectRoot "iniciar.cmd"
    $menuShortcut.WorkingDirectory = $projectRoot
    if (Test-Path -LiteralPath $iconPath -PathType Leaf) {
        $menuShortcut.IconLocation = "$iconPath,0"
    }
    $menuShortcut.Description = "Abrir o Q.U.A.T.I."
    $menuShortcut.Save()
    $obsoleteStopShortcut = Join-Path $startMenu "Encerrar Q.U.A.T.I.lnk"
    if (Test-Path -LiteralPath $obsoleteStopShortcut -PathType Leaf) {
        Remove-Item -LiteralPath $obsoleteStopShortcut -Force
    }

    Show-Message -Text "Instalação concluída. Use o atalho Q.U.A.T.I. criado na Área de Trabalho. O serviço local encerra automaticamente quando todas as abas do app são fechadas." -Title "Q.U.A.T.I. pronto"
} catch {
    Show-Message -Text $_.Exception.Message -Title "Falha na instalação" -Icon ([System.Windows.Forms.MessageBoxIcon]::Error)
    Write-Error $_
    exit 1
}
