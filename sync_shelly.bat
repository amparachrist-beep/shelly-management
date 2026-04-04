@echo off
echo ========================================
echo Synchronisation Shelly - %date% %time%
echo ========================================

cd /d C:\Users\HP\PycharmProjects\Shelly-management\backend

call C:\Users\HP\miniconda3\envs\geo\Scripts\activate

python manage.py sync_shelly_consommations >> logs\shelly_sync.log 2>&1

echo.
echo Synchronisation terminée à %time%
echo ========================================