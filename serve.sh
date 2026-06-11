#!/usr/bin/env sh
# 설계 문서 뷰어 로컬 서버 — http://localhost:8081/docs-web/
cd "$(dirname "$0")"
echo "문서 뷰어: http://localhost:8081/docs-web/"
python3 -m http.server 8081
