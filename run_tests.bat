@echo off
cd /d %~dp0
title Lily Tests
py -m unittest discover -s tests -t . -v
echo.
pause
