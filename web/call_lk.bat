@echo off
REM Load user PATH from registry
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "UserPath=%%b"
set "PATH=%UserPath%;%PATH%"

REM Call lk with all arguments
lk %*

