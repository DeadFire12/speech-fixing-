@echo off
cd /d %~dp0
title Lily Self Test
py Lily.py --selftest %*
echo.
pause
