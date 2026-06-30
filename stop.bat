@echo off
echo =========================================
echo Arret du serveur Ambilight Sync...
echo =========================================

:: Cherche le processus qui ecoute sur le port 5777 et le force a s'arreter
FOR /F "tokens=5" %%T IN ('netstat -ano ^| findstr :5777') DO (
    echo Fermeture du PID %%T...
    taskkill /PID %%T /F >nul 2>&1
)

echo.
echo Serveur arrete.
timeout /t 3 >nul
exit
