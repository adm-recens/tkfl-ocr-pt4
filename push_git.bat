@echo off
REM Git Push Script for TKFL OCR

cd /d c:\Users\ramst\Documents\apps\tkfl_ocr\pt5

echo ========================================
echo Git Push - TKFL OCR Application
echo ========================================
echo.

echo Step 1: Checking git status...
git status --short
echo.

echo Step 2: Adding all files...
git add .
echo Added files to staging area
echo.

echo Step 3: Creating commit...
git commit -m "Update: Learning History Page, Learning History Tracker, OCR Field Capture Analysis, and improved data transparency system [2026-01-28]"
echo.

echo Step 4: Pulling latest from remote...
git pull origin main
echo.

echo Step 5: Pushing to remote...
git push origin main
echo.

echo ========================================
echo Push Complete!
echo ========================================
echo.
pause
