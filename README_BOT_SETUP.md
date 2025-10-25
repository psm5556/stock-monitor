# Telegram 봇 생성 및 CHAT_ID 확인 (자세한 단계)

아래 절차에 따라 Telegram 봇을 만들고, BOT_TOKEN과 CHAT_ID를 얻으세요.

## 1) BotFather로 봇 생성 (BOT_TOKEN 발급)
1. Telegram 앱(모바일 또는 데스크톱)에서 `@BotFather` 를 검색하여 대화창을 엽니다.
2. `/newbot` 명령을 보냅니다.
3. 봇의 이름(표시명)을 입력합니다. (예: MyStockAlertBot)
4. 봇의 사용자명(username)을 입력합니다. (예: mystock_alert_bot) — 반드시 `_bot` 또는 `bot` 등 고유한 이름이어야 합니다.
5. 생성이 완료되면 BotFather가 **HTTP API 토큰**(BOT_TOKEN)을 제공합니다. 예시 형식:
   `123456789:AAH...rest_of_token`
6. 이 토큰을 복사하여 GitHub Secrets의 `BOT_TOKEN`으로 추가하세요.

## 2) 본인 Chat ID 확인 (CHAT_ID)
- 개인(1:1) 챗 ID 확인 방법
  1. Telegram에서 `@userinfobot` 또는 `@RawDataBot` 등을 검색해 시작합니다.
  2. `/start`를 누르면 봇이 당신의 `chat id`를 보여줍니다. 또는 `@userinfobot` 의 경우 메시지에 숫자 ID가 표시됩니다.
  3. 표시된 숫자(보통 음수가 아닌 정수)를 복사해 GitHub Secrets의 `CHAT_ID`로 추가하세요.

- 그룹 채팅에 알림을 보내고 싶다면:
  1. 그룹을 만들고, 생성한 알림 봇을 그룹에 초대합니다.
  2. 그룹에서 한번 봇에게 메시지를 보내거나, 그룹에서 봇과 상호작용하여 봇이 그룹의 chat_id를 알 수 있게 합니다.
  3. 그룹 chat_id는 음수(-)로 시작하는 경우가 많습니다. `@RawDataBot` 등을 사용해 그룹 chat id를 확인하세요.

## 3) 테스트 전송
- 아래 URL을 브라우저에 입력해 간단히 메시지를 보낼 수 있습니다(토큰과 CHAT_ID를 자신의 값으로 교체):
  `https://api.telegram.org/bot<BOT_TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=Hello`
- 성공하면 Telegram에서 메시지를 수신합니다.

## 4) GitHub Secrets 등록
1. GitHub 레포지토리 → Settings → Secrets and variables → Actions → New repository secret
2. Name: `BOT_TOKEN`, Value: `<발급받은 토큰>`
3. Name: `CHAT_ID`, Value: `<확인한 chat id>`

## 주의사항
- BOT_TOKEN과 CHAT_ID는 절대 공개하지 마세요.
- Telegram API 사용 시 전송 제한(스팸 방지)은 있으니 메시지 빈도는 적절히 설정하세요.
