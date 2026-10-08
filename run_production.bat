@echo off
echo =====================================================
echo  Starting Travel Guide Production App (Waitress WSGI)
echo  URL: http://127.0.0.1:5000
echo  Health: http://127.0.0.1:5000/api/health
echo  Press Ctrl+C to stop the server
echo =====================================================
.\.venv\Scripts\python.exe wsgi.py
pause
