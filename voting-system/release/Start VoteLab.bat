@echo off
setlocal
title VoteLab
"%~dp0runtime\python.exe" -B "%~dp0app\run_votelab.py"
if errorlevel 1 (
    echo.
    echo VoteLab could not start. See READ ME FIRST.txt.
    pause
    exit /b 1
)
