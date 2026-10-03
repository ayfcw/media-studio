# 自媒体智能体平台 · 一键启动（幂等：已在运行的服务自动跳过）
$ErrorActionPreference = "Continue"
$root = "C:\Users\24688\dev"
function Test-Port($p) { return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }

# 1. Docker + DTK 采集栈
$docker = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
if(Test-Port 8000){
    Write-Output "[1/5] DTK 采集栈已在运行，跳过"
} else {
    Write-Output "[1/5] 启动 Docker + DTK 采集栈..."
    if(-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)){
        Start-Process "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
        for($i=0; $i -lt 30; $i++){ Start-Sleep 5; & $docker info *>$null; if($LASTEXITCODE -eq 0){ break } }
    }
    & $docker start dtk-postgres-1 dtk-redis-1 dtk-worker-1 dtk-api-1 2>$null | Out-Null
}

# 2. MoneyPrinterTurbo 成片引擎 :8090
if(Test-Port 8090){ Write-Output "[2/5] 成片引擎已在运行，跳过" }
else {
    Write-Output "[2/5] 启动 MoneyPrinterTurbo..."
    Start-Process -WindowStyle Hidden -WorkingDirectory "$root\MoneyPrinterTurbo" `
        -FilePath "$root\MoneyPrinterTurbo\.venv\Scripts\python.exe" -ArgumentList "main.py"
}

# 3. media-studio 三件套
if((Test-Port 8100) -and (Test-Port 8200) -and (Test-Port 8300)){
    Write-Output "[3/5] 分析引擎/网关/MCP 已在运行，跳过"
} else {
    Write-Output "[3/5] 启动 AI 分析引擎 / 编排网关 / MCP..."
    if(-not (Test-Port 8100)){
        Start-Process -WindowStyle Hidden -WorkingDirectory "$root\media-studio" `
            -FilePath "$root\media-studio\.venv\Scripts\uvicorn.exe" `
            -ArgumentList "studio.analytics.app:app","--host","127.0.0.1","--port","8100"
    }
    if(-not (Test-Port 8200)){
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "$root\media-studio\.venv\Scripts\uvicorn.exe"
        $psi.Arguments = "studio.gateway.app:app --host 127.0.0.1 --port 8200"
        $psi.WorkingDirectory = "$root\media-studio"
        $psi.EnvironmentVariables["MPT_URL"] = "http://127.0.0.1:8090"
        $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
        [System.Diagnostics.Process]::Start($psi) | Out-Null
    }
    if(-not (Test-Port 8300)){
        $psi2 = New-Object System.Diagnostics.ProcessStartInfo
        $psi2.FileName = "$root\media-studio\.venv\Scripts\python.exe"
        $psi2.Arguments = "-m studio.mcp.server"
        $psi2.WorkingDirectory = "$root\media-studio"
        $psi2.EnvironmentVariables["STUDIO_MCP_HTTP"] = "1"
        $psi2.EnvironmentVariables["STUDIO_MCP_PORT"] = "8300"
        $psi2.UseShellExecute = $false; $psi2.CreateNoWindow = $true
        [System.Diagnostics.Process]::Start($psi2) | Out-Null
    }
}

# 4.5 知识库 AnythingLLM（可选，:3001）
if(Test-Port 3001){ Write-Output "[4.5/5] 知识库已在运行，跳过" }
else {
    Write-Output "[4.5/5] 启动知识库（AnythingLLM）..."
    & $docker start anythingllm 2>$null | Out-Null
}

# 5. 前端 :5173
if(Test-Port 5173){ Write-Output "[4/5] 前端已在运行，跳过" }
else {
    Write-Output "[4/5] 启动前端..."
    Start-Process -WindowStyle Hidden -WorkingDirectory "$root\media-studio\frontend" `
        -FilePath "cmd.exe" -ArgumentList "/c","npm run dev"
}

# 5. 健康检查
if((Test-Port 8200) -and (Test-Port 5173)){
    Write-Output "[5/5] 平台就绪 ✓  入口: http://127.0.0.1:5173"
} else {
    Write-Output "[5/5] 首次启动约需 40 秒，稍候访问 http://127.0.0.1:5173"
}
