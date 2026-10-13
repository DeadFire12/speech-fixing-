@echo off
cd /d %~dp0
title Lily Python 3.8 Check
py tools\check_py38.py
echo.
pause
