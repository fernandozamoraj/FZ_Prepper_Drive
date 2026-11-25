@echo off
rem regenerate-all.bat (offline prepper kit v1.12.0): rebuild the whole kit from the internet on Windows.
rem Needs ~200 GB free disk (NTFS or exFAT), 24+ GB RAM for the map/routing builds, and many hours.
rem Safe to stop and re-run: finished steps are skipped and downloads resume.
cd /d "%~dp0"
call kit.bat setup || goto fail
call kit.bat download || goto fail
call kit.bat build-all || goto fail
echo All done. Copy it to a USB drive with: make-drive.bat E:\
pause
exit /b 0
:fail
echo A step failed; see the messages above. Run regenerate-all.bat again to continue where it stopped.
pause
exit /b 1
