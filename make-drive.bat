@echo off
rem make-drive.bat (offline prepper kit v1.14.1): copy the kit to a USB drive that runs on Windows AND Mac.
rem Usage: make-drive.bat E:\ [--no-libraries]    The drive must be exFAT (FAT32 cannot hold the big files).
rem Safe to re-run: only changed files are copied. Puts the double-click launchers at the top of the drive.
if "%~1"=="" (echo Usage: make-drive.bat E:\ [--no-libraries] & exit /b 1)
call "%~dp0kit.bat" make-drive %*
