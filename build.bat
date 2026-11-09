@echo off
setlocal
cd /d "%~dp0"
title Membuat SortirFileKuliah.exe

echo ============================================
echo  Membuat SortirFileKuliah.exe
echo ============================================
echo.

if not exist "sortir_kuliah.py" goto nofile

rem --- Cari Python yang benar-benar bisa dijalankan ---
set "PY="
py --version >nul 2>nul
if not errorlevel 1 set "PY=py"
if defined PY goto foundpy

python --version >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto foundpy

for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if defined PY goto foundpy

goto nopython

:foundpy
echo Python yang dipakai: %PY%
"%PY%" --version
echo.

rem --- Pastikan tkinter (untuk tampilan popup) tersedia ---
"%PY%" -c "import tkinter" >nul 2>nul
if errorlevel 1 goto notk

rem --- Hapus hasil build lama supaya tidak tertukar ---
if exist "dist\SortirFileKuliah.exe" del /q "dist\SortirFileKuliah.exe"

echo [1/2] Memasang library yang dibutuhkan. Butuh internet...
"%PY%" -m pip install watchdog pystray pillow pyinstaller
if errorlevel 1 goto failed
echo.

echo [2/2] Membuat file .exe. Tunggu beberapa menit...
"%PY%" -m PyInstaller --noconsole --onefile --name SortirFileKuliah sortir_kuliah.py
if errorlevel 1 goto failed

if not exist "dist\SortirFileKuliah.exe" goto failed

echo.
echo ============================================
echo  BERHASIL
echo  File ada di: %~dp0dist\SortirFileKuliah.exe
echo ============================================
goto end

:nofile
echo GAGAL: file sortir_kuliah.py tidak ditemukan.
echo Taruh build.bat dan sortir_kuliah.py di folder yang SAMA.
goto end

:nopython
echo GAGAL: Python tidak ditemukan di komputer ini.
echo.
echo Pilihan:
echo  1. Jalankan build.bat ini di laptop yang sudah terpasang Python,
echo     lalu kirim file SortirFileKuliah.exe ke teman. Teman tidak perlu Python.
echo  2. Atau pasang Python dari https://www.python.org/downloads/
echo     Saat instalasi, CENTANG "Add python.exe to PATH" dan biarkan
echo     opsi "tcl/tk and IDLE" tetap tercentang. Lalu jalankan build.bat lagi.
goto end

:notk
echo GAGAL: Python ini tidak punya tkinter, padahal dibutuhkan untuk popup.
echo Jalankan ulang installer Python, pilih Modify, lalu pastikan
echo opsi "tcl/tk and IDLE" tercentang. Setelah itu jalankan build.bat lagi.
goto end

:failed
echo.
echo ============================================
echo  GAGAL membuat file .exe
echo ============================================
echo Baca pesan error berwarna di atas. Jika tidak jelas, foto atau
echo salin seluruh teks di jendela ini dan kirim ke pembuat aplikasi.

:end
echo.
pause
endlocal