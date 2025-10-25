# stock-monitor (Streamlit + GitHub Actions + Telegram)

**요약**: Streamlit Cloud 대시보드로 시각화하고, GitHub Actions가 주기적으로 monitor.py를 실행해 이동평균선(일/주 단위 200/240/365)에 닿거나 교차하면 Telegram으로 알림을 보내는 템플릿입니다. 모든 구성은 무료로 사용 가능한 서비스로만 구성되어 있습니다.

## 파일 구조
- app.py               : Streamlit 대시보드 (Daily & Weekly 차트, 교차 시 알림 표시)
- monitor.py           : GitHub Actions에서 주기적으로 실행되는 감시 스크립트 (Telegram 알림)
- requirements.txt     : 의존 패키지
- .github/workflows/...: GitHub Actions 스케줄 설정

## 배포 순서 (요약)
1. 이 레포를 GitHub에 업로드하세요.
2. GitHub Repo → Settings → Secrets → Actions 에 아래 2개를 추가하세요:
   - BOT_TOKEN  : Telegram Bot 토큰 (BotFather 발급)
   - CHAT_ID    : 수신할 Chat ID (자세한 방법은 아래 참고)
3. Streamlit Cloud에 GitHub 리포지토리를 연결해 deploy 하세요.
4. GitHub Actions 탭에서 워크플로우가 정상 동작하는지 확인하세요.

## Telegram 봇 토큰 및 CHAT_ID 발급 방법 (자세히는 README_BOT_SETUP.md 참고)
