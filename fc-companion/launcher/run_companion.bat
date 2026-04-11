@echo off
setlocal

REM Save padronizado (Botafogo). Para outro save, altere esta linha ou defina antes no sistema.
set "FC_COMPANION_LOCKED_SAVE=CmMgrC20260409141102584"

cd /d "%~dp0"
python run_companion.py

endlocal

