# 텔레그램 메시지 모니터링 및 자동 전달 프로그램 사용 가이드

## 목차
1. [프로그램 개요](#1-프로그램-개요)
2. [설치 방법](#2-설치-방법)
3. [초기 설정](#3-초기-설정)
4. [프로그램 실행](#4-프로그램-실행)
5. [환경 변수 설정](#5-환경-변수-설정)
6. [문제 해결](#6-문제-해결)
7. [로그 확인](#7-로그-확인)

## 1. 프로그램 개요

이 프로그램은 텔레그램 사용자 계정을 통해 참여한 모든 채널과 그룹의 메시지를 실시간으로 모니터링하고, "open.kakao.com" 키워드가 포함된 메시지를 자동으로 감지하여 지정된 대상 채널로 즉시 전달합니다.

### 주요 기능
- Telethon 라이브러리를 사용한 텔레그램 사용자 세션 구현
- 사용자가 참여한 모든 채널/그룹의 실시간 메시지 모니터링
- "open.kakao.com" 키워드가 포함된 메시지 자동 감지
- 감지된 메시지의 원문을 지정된 대상 채널로 즉시 전달
- 에러 핸들링 및 자동 재연결 기능

### 프로그램 구성
- `setup_session.py`: 세션 초기화 스크립트
- `monitor.py`: 메인 모니터링 및 전달 프로그램
- `.env`: 환경 변수 설정 파일 (자동 생성)

## 2. 설치 방법

### 필수 요구사항
- Python 3.7 이상
- pip (Python 패키지 관리자)
- 텔레그램 계정
- 텔레그램 API ID 및 API Hash (https://my.telegram.org에서 발급)

### 패키지 설치

1. 프로젝트 디렉토리를 생성하고 이동합니다.
   ```bash
   mkdir telegram_monitor
   cd telegram_monitor
   ```

2. 필요한 패키지를 설치합니다.
   ```bash
   pip install telethon python-dotenv
   ```

3. 프로젝트 파일을 다운로드하거나 복사합니다.
   - `setup_session.py`
   - `monitor.py`

4. 파일에 실행 권한을 부여합니다.
   ```bash
   chmod +x setup_session.py monitor.py
   ```

## 3. 초기 설정

### 텔레그램 API 키 발급

1. 웹 브라우저에서 https://my.telegram.org 에 접속합니다.
2. 텔레그램 계정으로 로그인합니다.
3. 'API development tools'를 선택합니다.
4. 애플리케이션 정보를 입력합니다:
   - App title: Telegram Monitor (또는 원하는 이름)
   - Short name: telegram_monitor (또는 원하는 이름)
   - Platform: Desktop
   - Description: Telegram message monitoring tool
5. 'Create Application'을 클릭합니다.
6. 생성된 `api_id`와 `api_hash`를 기록해둡니다.

### 세션 초기화

1. 세션 초기화 스크립트를 실행합니다.
   ```bash
   ./setup_session.py
   ```

2. 프롬프트에 따라 다음 정보를 입력합니다:
   - API ID: my.telegram.org에서 발급받은 API ID
   - API Hash: my.telegram.org에서 발급받은 API Hash
   - 전화번호: 국가 코드를 포함한 전화번호 (예: +821012345678)
   - 세션 이름: (기본값: telegram_session)

3. 텔레그램 앱으로 전송된 인증 코드를 입력합니다.

4. 2단계 인증이 활성화된 경우 비밀번호를 입력합니다.

5. 세션 초기화가 완료되면 `.env` 파일과 세션 파일이 생성됩니다.

## 4. 프로그램 실행

### 모니터링 시작

1. 메인 모니터링 프로그램을 실행합니다.
   ```bash
   ./monitor.py
   ```

2. 프로그램이 시작되면 다음과 같은 로그가 표시됩니다:
   ```
   로그인 성공: [사용자 이름]
   대상 채널 설정: [대상 채널 이름]
   모니터링 시작: 모든 채널/그룹의 메시지를 모니터링합니다.
   키워드 필터: 'open.kakao.com'
   대상 채널: [대상 채널]
   Ctrl+C를 눌러 프로그램을 종료할 수 있습니다.
   ```

3. 이제 프로그램은 백그라운드에서 실행되며, "open.kakao.com" 키워드가 포함된 메시지를 감지하면 지정된 대상 채널로 자동 전달합니다.

### 프로그램 종료

- 프로그램을 종료하려면 터미널에서 `Ctrl+C`를 누릅니다.

### 백그라운드 실행 (선택 사항)

- 프로그램을 백그라운드에서 계속 실행하려면 다음과 같이 실행할 수 있습니다:
  ```bash
  nohup ./monitor.py > /dev/null 2>&1 &
  ```

- 백그라운드 프로세스를 종료하려면:
  ```bash
  pkill -f monitor.py
  ```

## 5. 환경 변수 설정

프로그램은 `.env` 파일에서 환경 변수를 로드합니다. 세션 초기화 스크립트를 실행하면 이 파일이 자동으로 생성되지만, 필요에 따라 수동으로 편집할 수 있습니다.

### 기본 환경 변수

```
# 텔레그램 API 인증 정보
API_ID=your_api_id
API_HASH=your_api_hash
PHONE_NUMBER=your_phone_number

# 세션 설정
SESSION_NAME=telegram_session

# 대상 채널 설정
TARGET_CHANNEL=target_channel_username_or_id

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=telegram_monitor.log
```

### 환경 변수 설명

- `API_ID`: 텔레그램 API ID (숫자)
- `API_HASH`: 텔레그램 API Hash (문자열)
- `PHONE_NUMBER`: 국가 코드를 포함한 전화번호 (예: +821012345678)
- `SESSION_NAME`: 세션 파일 이름 (기본값: telegram_session)
- `TARGET_CHANNEL`: 감지된 메시지를 전달할 대상 채널
  - 사용자명: @username
  - 채널 ID: 숫자 ID
  - 자기 자신: me
- `LOG_LEVEL`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FILE`: 로그 파일 경로

### 대상 채널 변경

대상 채널을 변경하려면 `.env` 파일에서 `TARGET_CHANNEL` 값을 수정합니다:

```
# 자기 자신에게 전달
TARGET_CHANNEL=me

# 특정 사용자에게 전달
TARGET_CHANNEL=@username

# 특정 채널/그룹에 전달 (ID 사용)
TARGET_CHANNEL=1234567890
```

## 6. 문제 해결

### 일반적인 문제

1. **세션 초기화 실패**
   - API ID와 API Hash가 올바른지 확인하세요.
   - 전화번호가 국가 코드를 포함하고 있는지 확인하세요.
   - 인증 코드를 정확히 입력했는지 확인하세요.

2. **인증 오류**
   - 세션 파일이 손상된 경우 삭제 후 `setup_session.py`를 다시 실행하세요.
   - 2단계 인증이 활성화된 경우 비밀번호를 정확히 입력했는지 확인하세요.

3. **연결 오류**
   - 인터넷 연결을 확인하세요.
   - 텔레그램 서버에 일시적인 문제가 있을 수 있습니다. 잠시 후 다시 시도하세요.
   - 너무 많은 요청을 보내면 텔레그램에서 일시적으로 차단할 수 있습니다. 이 경우 로그에 표시된 시간만큼 기다려야 합니다.

4. **메시지가 전달되지 않음**
   - 대상 채널 설정이 올바른지 확인하세요.
   - 대상 채널에 메시지를 보낼 권한이 있는지 확인하세요.
   - 로그 파일을 확인하여 오류 메시지를 확인하세요.

### 오류 메시지 및 해결 방법

1. **"오류: .env 파일을 찾을 수 없습니다."**
   - `setup_session.py`를 먼저 실행하여 .env 파일을 생성하세요.

2. **"오류: 세션 파일을 찾을 수 없습니다."**
   - `setup_session.py`를 먼저 실행하여 세션을 초기화하세요.

3. **"유효하지 않은 전화번호입니다."**
   - 국가 코드를 포함한 올바른 형식의 전화번호를 입력하세요 (예: +821012345678).

4. **"유효하지 않은 API ID 또는 API Hash입니다."**
   - my.telegram.org에서 발급받은 올바른 API ID와 API Hash를 입력하세요.

5. **"FloodWaitError"**
   - 텔레그램에서 너무 많은 요청으로 인해 일시적으로 차단했습니다. 로그에 표시된 시간만큼 기다려야 합니다.

## 7. 로그 확인

프로그램은 콘솔과 로그 파일에 동시에 로그를 기록합니다.

### 로그 파일 위치

기본 로그 파일 위치는 프로그램 실행 디렉토리의 `telegram_monitor.log` 입니다. 이 위치는 `.env` 파일의 `LOG_FILE` 변수에서 변경할 수 있습니다.

### 로그 레벨 변경

로그 레벨을 변경하려면 `.env` 파일의 `LOG_LEVEL` 값을 수정합니다:

```
# 자세한 로그 (개발 및 디버깅용)
LOG_LEVEL=DEBUG

# 일반 정보 로그 (기본값)
LOG_LEVEL=INFO

# 경고 및 오류만 표시
LOG_LEVEL=WARNING

# 오류만 표시
LOG_LEVEL=ERROR

# 심각한 오류만 표시
LOG_LEVEL=CRITICAL
```

### 로그 파일 확인

로그 파일을 확인하려면 다음 명령을 사용합니다:

```bash
# 전체 로그 파일 보기
cat telegram_monitor.log

# 실시간 로그 확인
tail -f telegram_monitor.log

# 마지막 100줄만 확인
tail -n 100 telegram_monitor.log
```

---

이 가이드에 대한 질문이나 문제가 있으면 언제든지 문의하세요.
