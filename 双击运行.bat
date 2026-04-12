@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"

REM ===================== 基础变量 =====================
set "BASE_DIR=%~dp0"
set "TEMP_DIR=%temp%"
set "GIT_INSTALLER=%TEMP_DIR%\Git249.exe"
set "FFMPEG_ARCHIVE=%BASE_DIR%ffmpeg.7z"
set "FFMPEG_INSTALL_DIR=%ProgramFiles%\ffmpeg"
set "FFMPEG_BIN_DIR=%FFMPEG_INSTALL_DIR%\bin"
set "LOG_DIR=%BASE_DIR%logs"
set "LOG_FILE=%LOG_DIR%\install.txt"
set "SEVEN_ZIP_PATH="

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul

echo ================================== 检测 7-Zip ==================================

REM 先从 PATH 里找
where 7z >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where 7z') do (
        set "SEVEN_ZIP_PATH=%%I"
        goto :after_find_7z
    )
)

REM 再找默认安装目录
if exist "%ProgramFiles%\7-Zip\7z.exe" (
    set "SEVEN_ZIP_PATH=%ProgramFiles%\7-Zip\7z.exe"
) else if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" (
    set "SEVEN_ZIP_PATH=%ProgramFiles(x86)%\7-Zip\7z.exe"
)

:after_find_7z
if defined SEVEN_ZIP_PATH (
    echo [✓] 检测到 7-Zip: "%SEVEN_ZIP_PATH%"
) else (
    echo [!] 未检测到 7-Zip，后续将优先尝试 PowerShell 解压
)

echo.
echo ================================== 安装 Git ==================================

git --version >nul 2>&1
if errorlevel 1 (
    echo [*] 正在安装 Git...
    curl -L -o "%GIT_INSTALLER%" "https://www.modelscope.cn/models/q502892879/cudaxx/resolve/master/Git249.exe"
    if not exist "%GIT_INSTALLER%" (
        echo [×] Git 安装包下载失败
        pause
        exit /b 1
    )
    start /wait "" "%GIT_INSTALLER%" /VERYSILENT /NORESTART
) else (
    echo [✓] Git 已存在
)

echo.
echo ================================= 安装 FFMPEG ================================

set "FFMPEG_ARCHIVE=%BASE_DIR%ffmpeg-release-essentials.zip"
set "FFMPEG_INSTALL_DIR=%ProgramFiles%\ffmpeg"
set "FFMPEG_BIN_DIR=%FFMPEG_INSTALL_DIR%\bin"
set "FFMPEG_TMP_DIR=%TEMP%\ffmpeg_extract_tmp"

where ffmpeg >nul 2>&1
if not errorlevel 1 (
    echo [✓] 系统已存在 FFMPEG
    goto :exit_ffmpeg
)

if exist "%FFMPEG_BIN_DIR%\ffmpeg.exe" (
    echo [✓] 本地已存在 FFMPEG: "%FFMPEG_BIN_DIR%\ffmpeg.exe"
    goto :set_ffmpeg
)

if exist "%FFMPEG_ARCHIVE%" (
    echo [*] 检测到当前目录旧压缩包，正在删除...
    del /f /q "%FFMPEG_ARCHIVE%" >nul 2>nul
)

goto :download_ffmpeg

:download_ffmpeg
echo [*] 正在下载 FFMPEG...
curl -L --fail --retry 3 --retry-delay 2 -o "%FFMPEG_ARCHIVE%" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
if errorlevel 1 (
    echo [×] FFMPEG 下载失败，网络连接被中断
    if exist "%FFMPEG_ARCHIVE%" del /f /q "%FFMPEG_ARCHIVE%" >nul 2>nul
    pause
    exit /b 1
)

if not exist "%FFMPEG_ARCHIVE%" (
    echo [×] FFMPEG 下载失败，未生成压缩包
    pause
    exit /b 1
)

for %%A in ("%FFMPEG_ARCHIVE%") do set "FFMPEG_SIZE=%%~zA"
if not defined FFMPEG_SIZE (
    echo [×] 无法获取压缩包大小
    if exist "%FFMPEG_ARCHIVE%" del /f /q "%FFMPEG_ARCHIVE%" >nul 2>nul
    pause
    exit /b 1
)

if %FFMPEG_SIZE% LSS 10000000 (
    echo [×] 下载的压缩包异常，疑似未下载完整
    if exist "%FFMPEG_ARCHIVE%" del /f /q "%FFMPEG_ARCHIVE%" >nul 2>nul
    pause
    exit /b 1
)

goto :install_ffmpeg

:install_ffmpeg
echo [*] 正在解压 FFMPEG...

if exist "%FFMPEG_TMP_DIR%" rmdir /s /q "%FFMPEG_TMP_DIR%"
mkdir "%FFMPEG_TMP_DIR%" >nul 2>nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"Expand-Archive -LiteralPath '%FFMPEG_ARCHIVE%' -DestinationPath '%FFMPEG_TMP_DIR%' -Force"

if errorlevel 1 (
    echo [×] FFMPEG 解压失败
    pause
    exit /b 1
)

for /f "delims=" %%I in ('dir /s /b "%FFMPEG_TMP_DIR%\ffmpeg.exe"') do (
    set "FOUND_FFMPEG_EXE=%%I"
    goto :found_ffmpeg
)

echo [×] 解压完成，但未找到 ffmpeg.exe
pause
exit /b 1

:found_ffmpeg
for %%I in ("%FOUND_FFMPEG_EXE%") do set "FOUND_BIN_DIR=%%~dpI"
for %%I in ("%FOUND_BIN_DIR%..") do set "FOUND_ROOT_DIR=%%~fI"

if exist "%FFMPEG_INSTALL_DIR%" rmdir /s /q "%FFMPEG_INSTALL_DIR%"
mkdir "%FFMPEG_INSTALL_DIR%" >nul 2>nul

xcopy "%FOUND_ROOT_DIR%\*" "%FFMPEG_INSTALL_DIR%\" /e /i /h /y >nul
if errorlevel 1 (
    echo [×] 复制 FFMPEG 文件失败
    pause
    exit /b 1
)

if not exist "%FFMPEG_BIN_DIR%\ffmpeg.exe" (
    echo [×] 安装完成后仍未找到 "%FFMPEG_BIN_DIR%\ffmpeg.exe"
    pause
    exit /b 1
)

goto :set_ffmpeg

:set_ffmpeg
echo [*] 正在写入 FFMPEG 环境变量...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ffmpegBin = '%FFMPEG_BIN_DIR%';" ^
"$machinePath = [Environment]::GetEnvironmentVariable('Path','Machine');" ^
"if ([string]::IsNullOrWhiteSpace($machinePath)) { $machinePath = '' };" ^
"if ($machinePath -notlike ('*' + $ffmpegBin + '*')) {" ^
"    [Environment]::SetEnvironmentVariable('Path', ($machinePath.TrimEnd(';') + ';' + $ffmpegBin), 'Machine');" ^
"    Write-Host '[✓] 成功添加至系统 PATH:' $ffmpegBin;" ^
"} else {" ^
"    Write-Host '[✓] PATH 已包含 ffmpeg 路径';" ^
"}"

echo [✓] FFMPEG 安装完成

:exit_ffmpeg
echo.
echo ================================ 启动服务 =====================================

set "PORT=8777"

echo Cleaning port %PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT%') do (
    if "%%a" NEQ "0" (
        echo Killing PID %%a...
        taskkill /f /pid %%a >nul 2>&1
    )
)

timeout /t 1 /nobreak >nul

echo Starting server...
start "AI Canvas Server" cmd /k "venv\python.exe server.py"

timeout /t 2 /nobreak >nul
echo Opening browser...
start http://localhost:%PORT%/

exit /b 0