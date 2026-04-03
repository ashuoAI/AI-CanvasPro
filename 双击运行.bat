@echo off
chcp 65001 >nul
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
start "AI Canvas Server" cmd /c "venv\python.exe server.py"

:: Give the server a moment to boot up, then open browser
timeout /t 2 /nobreak >nul
echo Opening browser...
start http://localhost:%PORT%/

:: Exit the launcher
exit
