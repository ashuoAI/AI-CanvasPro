@echo off
chcp 65001 >nul

REM ===================== 自动检测并安装 7-Zip =====================
for %%I in (7z.exe) do set "SEVEN_ZIP_PATH=%%~$PATH:I"
if not defined SEVEN_ZIP_PATH (
    if exist "%ProgramFiles%\7-Zip\7z.exe" (
        set "SEVEN_ZIP_PATH=%ProgramFiles%\7-Zip\7z.exe"
    ) else if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" (
        set "SEVEN_ZIP_PATH=%ProgramFiles(x86)%\7-Zip\7z.exe"
    )
)

:: 如果没找到，自动下载安装
if not defined SEVEN_ZIP_PATH (
    echo %GREEN%正在安装 7-Zip 解压工具...%RESET%
    curl -L -o "%temp%\7z-installer.exe" "https://www.modelscope.cn/models/q502892879/cudaxx/resolve/master/7z2201-x64.exe"
    start /wait "" "%temp%\7z-installer.exe" /S /NOCANCEL /NORESTART

    :: 再次查找
    for %%I in (7z.exe) do set "SEVEN_ZIP_PATH=%%~$PATH:I"
    if not defined SEVEN_ZIP_PATH (
        if exist "%ProgramFiles%\7-Zip\7z.exe" set "SEVEN_ZIP_PATH=%ProgramFiles%\7-Zip\7z.exe"
        if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" set "SEVEN_ZIP_PATH=%ProgramFiles(x86)%\7-Zip\7z.exe"
    )

    :: 最终检查
    if not defined SEVEN_ZIP_PATH (
        echo %RED%安装7-Zip失败。请手动在系统程序里删除7-Zip后再重试脚本%RESET%
        pause
        exit /b 1
    )
)

echo [32m----------------------------------安装git--------------------------------------[0m
REM 检查 git 是否已经安装
git --version > NUL 2>&1
if %errorlevel% NEQ 0 (
    echo [32m正在安装 Git...[0m
    curl -L -o %GIT_INSTALLER% https://www.modelscope.cn/models/q502892879/cudaxx/resolve/master/Git249.exe
	:: 安装
	start /wait "" "%GIT_INSTALLER%" /VERYSILENT /NORESTART   
) else (
    echo [✓]-Git 已存在
)
cd /d "%~dp0"

echo [32m----------------------------------安装FFMPEG-----------------------------------[0m
:: 检查是否已经安装了 ffmpeg
where ffmpeg >nul 2>&1
if %errorlevel% NEQ 0 (
    :: 只有在文件不存在时才下载
    if not exist "%CD%\ffmpeg\bin\ffmpeg.exe" (
        if exist "ffmpeg.7z" (
            goto install_ffmpeg
        ) else (
            goto download_ffmpeg
        )
    ) else (
        goto set_ffmpeg
    ) 
) else (
    echo [✓]-FFMPEG 已存在
    goto exit_ffmpeg
)
:download_ffmpeg
echo [32m正在下载 FFMPEG...[0m
curl -L -o ffmpeg.7z https://www.modelscope.cn/models/q502892879/cudaxx/resolve/master/ffmpeg.7z

:install_ffmpeg 到programfils目录
echo [32m解压 ffmpeg...[0m
"%SEVEN_ZIP_PATH%" x ffmpeg.7z -o"%ProgramFiles%" -y >> "%installPath%\logs\install.txt" 2>&1

:set_ffmpeg
powershell -Command "if ($env:Path -notlike '*%ProgramFiles%\ffmpeg\bin') { $ffmpegBin = '%ProgramFiles%\ffmpeg\bin'; [Environment]::SetEnvironmentVariable('PATH', [Environment]::GetEnvironmentVariable('PATH','Machine') + ';'+$ffmpegBin, 'Machine'); Write-Host '成功添加至 PATH: ' $ffmpegBin } else { Write-Host 'PATH 已包含 ffmpeg 路径' }"

:exit_ffmpeg

:: Configure your port here (e.g. 8000, 5000)
set PORT=8777

:: Kill process occupying the port
echo Cleaning port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT%') do (
    if "%%a" NEQ "0" (
        echo Killing PID %%a...
        taskkill /f /pid %%a >nul 2>&1
    )
)

:: Wait for a second to let port be truly freed
timeout /t 1 /nobreak >nul

:: Start the Python script in the same window
echo Starting server...
start "AI Canvas Server" cmd /k "venv\python.exe server.py"

:: Give the server a moment to boot up, then open browser
timeout /t 2 /nobreak >nul
echo Opening browser...
start http://localhost:%PORT%/

:: Exit the launcher
exit
