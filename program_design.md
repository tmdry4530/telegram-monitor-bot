# 텔레그램 메시지 모니터링 및 자동 전달 프로그램 설계

## 1. 프로그램 구조

프로그램은 두 개의 독립적인 스크립트로 구성됩니다:

### 1.1. 세션 초기화 스크립트 (`setup_session.py`)
- 목적: 최초 1회 실행하여 텔레그램 API 인증 및 세션 파일 생성
- 주요 기능:
  - API ID, API Hash, 전화번호 입력 받기
  - 텔레그램 인증 코드 입력 처리
  - 세션 파일 생성 및 저장
  - 에러 핸들링 및 안내 메시지 제공

### 1.2. 메인 모니터링 프로그램 (`monitor.py`)
- 목적: 텔레그램 채널/그룹 메시지 모니터링 및 자동 전달
- 주요 기능:
  - .env 파일에서 환경 변수 로드
  - 세션 파일을 사용하여 텔레그램 클라이언트 초기화
  - 모든 채널/그룹의 메시지 실시간 모니터링
  - "open.kakao.com" 키워드 필터링
  - 감지된 메시지를 대상 채널로 전달
  - 에러 핸들링 및 로깅
  - 자동 재연결 메커니즘

## 2. 환경 변수 설계 (.env 파일)

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

## 3. 세션 관리

- 세션 파일 위치: 프로그램 실행 디렉토리에 `{SESSION_NAME}.session` 형태로 저장
- 세션 파일은 텔레그램 인증 정보를 담고 있어 재인증 없이 API 접근 가능
- 세션 파일은 민감 정보를 포함하므로 안전하게 관리 필요

## 4. 메시지 모니터링 및 전달 로직

### 4.1. 모니터링 로직
- `events.NewMessage()` 이벤트 핸들러 사용
- 모든 대화(채널/그룹)에서 메시지 수신 (필터 없음)
- 비동기 이벤트 처리로 실시간 응답성 확보

### 4.2. 필터링 로직
- 수신된 메시지 텍스트에서 "open.kakao.com" 문자열 검색
- 대소문자 구분 없이 검색 (정규식 사용)
- URL 형태가 아닌 경우도 포함하여 검색

### 4.3. 전달 로직
- 필터링된 메시지를 원본 그대로 대상 채널로 전달
- 메시지 속성(미디어, 링크 미리보기 등) 유지
- 전달 시 원본 출처 정보 포함

## 5. 에러 핸들링 및 로깅

### 5.1. 예외 처리
- 네트워크 연결 오류: 자동 재연결 시도
- 인증 오류: 세션 파일 문제 감지 및 재설정 안내
- API 제한 오류: 지수 백오프 방식으로 재시도
- 메시지 전달 실패: 로깅 후 계속 모니터링

### 5.2. 로깅 시스템
- Python 표준 logging 모듈 사용
- 로그 레벨: DEBUG, INFO, WARNING, ERROR, CRITICAL
- 콘솔 및 파일 로깅 동시 지원
- 로그 포맷: 타임스탬프, 로그 레벨, 메시지 내용

### 5.3. 재연결 메커니즘
- 연결 끊김 감지 시 자동 재연결 시도
- 최대 재시도 횟수 및 간격 설정
- 영구적 오류 시 명확한 오류 메시지와 함께 종료
