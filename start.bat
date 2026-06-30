@echo off
echo =========================================
echo Demarrage du serveur AmbiPlex...
echo =========================================
cd /d "%~dp0"

:: Activation de l'environnement virtuel et lancement en arriere-plan
call venv\Scripts\activate.bat
start "AmbiPlex Web UI" python web.py

echo.
echo Serveur lance avec succes !
echo Rendez-vous sur http://localhost:5777
echo (Cette fenetre se fermera automatiquement)
timeout /t 3 >nul
exit
