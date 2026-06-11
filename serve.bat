@echo off
rem 설계 문서 뷰어 로컬 서버 — http://localhost:8081/docs-web/
cd /d "%~dp0"
echo 문서 뷰어: http://localhost:8081/docs-web/
python -m http.server 8081
