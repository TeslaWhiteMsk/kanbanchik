@echo off
title Kanbanchik
python kanbanchik.py
if errorlevel 1 (
    echo.
    echo ====== ОШИБКА ======
    echo Не удалось запустить Kanbanchik.
    echo Убедитесь, что Python 2.7 установлен и доступен в переменной PATH.
    echo.
    pause
)