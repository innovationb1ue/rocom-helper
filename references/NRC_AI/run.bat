@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo === Step 1: Check Python ===
where python 2>&1
python --version 2>&1

echo === Step 2: Test Import ===
python -u -c "print('Python works!')" 2>&1

echo === Step 3: Test sys.path ===
python -u -c "import sys; sys.path.insert(0, r'.'); print('Path OK'); from src.models import BattleState; print('Import OK')" 2>&1

echo === Step 4: Run Battle ===
python -u -c "import sys; sys.path.insert(0, r'.'); from src.main import run_battle; run_battle(simulations=50, verbose=True)" 2>&1

echo === All Done ===
pause
