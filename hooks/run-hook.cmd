: << 'CMDBLOCK'
@echo off
REM Polyglot wrapper: cmd.exe runs the batch block below, and bash reads the
REM whole thing as a quoted heredoc it never executes, then falls through to the
REM Unix section at the bottom. One file, both platforms, no extension games.
REM
REM Why this exists rather than calling the hook script directly: invoking it
REM needs a bash, and "shell": "bash" in hooks.json only helps where the harness
REM honours it and bash is already on PATH. Here the batch block goes looking.
REM
REM Why the hook scripts have no .sh extension: Claude Code's Windows handling
REM prepends bash to any command containing .sh, which would wrap this wrapper.
REM
REM Technique and structure from obra/superpowers, which solves the same problem
REM the same way. Adapted, not copied wholesale.
REM
REM Usage: run-hook.cmd <script-name> [args...]

if "%~1"=="" (
    echo run-hook.cmd: missing script name >&2
    exit /b 1
)

set "HOOK_DIR=%~dp0"

REM Git for Windows, standard locations first
if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    "C:\Program Files (x86)\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

REM Anything else that put a bash on PATH -- MSYS2, Cygwin, a custom install
where bash >nul 2>nul
if %ERRORLEVEL% equ 0 (
    bash "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

REM No bash anywhere. Exit 0 on purpose: a machine that cannot run the hook
REM should still get the nine skills, just without the companion rule injected.
REM Failing here would turn a missing convenience into a broken install.
exit /b 0
CMDBLOCK

# Unix falls through to here, the heredoc above having consumed the batch block.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$1"
shift
exec bash "${SCRIPT_DIR}/${SCRIPT_NAME}" "$@"
