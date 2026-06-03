# DigimonRPG Discord Update Bot

디지몬RPG 업데이트 공지에서 **월드 버프 변경** 정보를 자동으로 Discord 채널에 전송하는 봇입니다.

## 기능

- 매주 수요일 00:00 KST에 최신 월드 버프 정보를 자동 전송
- 이전과 내용이 동일한 경우 자동 전송 스킵
- `!월드버프` 명령어로 즉시 조회 가능
- 30분마다 새 업데이트 공지 감지 시 자동 전송

## 명령어

| 명령어 | 설명 |
|--------|------|
| `!월드버프` | 최신 업데이트의 월드 버프 변경 정보를 즉시 출력 |

## 서버 설정 (Render)

### 1. GitHub 연동
1. [render.com](https://render.com) 접속 후 GitHub 로그인
2. **New → Web Service** 선택
3. 이 레포지토리 선택

### 2. 빌드 설정

| 항목 | 값 |
|------|-----|
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python main.py` |
| Instance Type | Free |

### 3. 환경변수 설정

Render 대시보드 **Environment** 탭에서 아래 두 변수를 추가합니다.

| 변수명 | 설명 |
|--------|------|
| `DISCORD_TOKEN` | Discord 봇 토큰 |
| `DISCORD_CHANNEL_ID` | 알림을 전송할 채널 ID |

### 4. Discord Developer Portal 설정

1. [discord.com/developers/applications](https://discord.com/developers/applications) 접속
2. 해당 애플리케이션 선택
3. **Bot → Privileged Gateway Intents** 에서 **Message Content Intent** 활성화

## 크롤링 대상

- 목록 페이지: `https://www.digimonrpg.com/Pages/Notice/Update`
- 최신 게시글의 **게임 내 변경사항 > 월드 버프 변경** 섹션 추출

## 자동 전송 주기

| 트리거 | 시간 |
|--------|------|
| 주간 자동 전송 | 매주 수요일 00:00 KST |
| 새 공지 감지 | 30분마다 확인, 새 글 등록 시 즉시 전송 |
