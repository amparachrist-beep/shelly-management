@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d C:\Users\HP\PycharmProjects\Shelly-management\backend

echo ========================================
echo Synchronisation Shelly - %date% %time%
echo ========================================

call C:\Users\HP\miniconda3\Scripts\activate.bat geo

python manage.py sync_shelly_consommations >> logs\shelly_sync.log 2>&1

echo ========================================
echo Synchronisation terminee a %time%
echo ========================================