# Telegram Message Monitor Bot - AWS EC2 배포 가이드

이 가이드는 `telegram-monitor-bot` 프로젝트를 AWS EC2에 배포하고, `systemd`를 이용해 24시간 안정적으로 자동 실행하는 방법을 안내합니다. 모든 코드 관리는 Git을 통해 이루어집니다.

---

## 📋 준비 사항

- AWS 계정
- 배포할 프로젝트의 GitHub 리포지토리 주소
- `.env` 파일에 설정할 텔레그램 API 정보 및 봇 토큰

---

## 1️⃣ AWS EC2 인스턴스 생성

### 1.1 AWS Console 접속 및 인스턴스 시작

1.  AWS Console에 로그인합니다.
2.  서비스 목록에서 `EC2`를 선택합니다.
3.  `인스턴스 시작` 버튼을 클릭합니다.

### 1.2 인스턴스 설정

- **이름**: `telegram-monitor-bot`
- **OS**: Ubuntu Server 22.04 LTS (프리티어 가능)
- **인스턴스 유형**: `t2.micro` (프리티어)
- **키 페어**: 새로 생성하거나 기존 키 페어를 사용합니다.

### 1.3 키 페어 생성 (처음인 경우)

1.  `새 키 페어 생성`을 선택합니다.
2.  **키 페어 이름**: `telegram-monitor-key` (또는 원하는 이름)
3.  **키 페어 유형**: `RSA`, **프라이빗 키 파일 형식**: `.pem`
4.  `키 페어 생성`을 클릭하면 `.pem` 파일이 자동으로 다운로드됩니다.

    ⚠️ **중요**: 이 `.pem` 파일은 재발급되지 않으므로, 안전한 곳에 반드시 보관해야 합니다.

### 1.4 네트워크 및 보안 그룹 설정

- **VPC / 서브넷**: 기본값 사용
- **퍼블릭 IP 자동 할당**: 활성화
- **보안 그룹**: 새로 생성
  - **보안 그룹 이름**: `telegram-monitor-sg`
  - **인바운드 규칙**:
    - **유형**: `SSH` | **프로토콜**: `TCP` | **포트**: `22` | **소스**: 내 IP (보안을 위해 권장)

### 1.5 인스턴스 시작

1.  설정을 검토한 후 `인스턴스 시작`을 클릭합니다.
2.  인스턴스 목록에서 상태가 `Running`으로 변경될 때까지 1~2분 정도 기다립니다.

---

## 2️⃣ EC2 인스턴스 접속 (Windows 기준)

EC2 인스턴스의 퍼블릭 IPv4 주소를 확인하여 접속합니다.

### 2.1 방법 1: PuTTY 사용 (권장)

1.  `PuTTYgen`을 실행하여 `.pem` 키를 `.ppk` 키로 변환합니다 (`Load` -> `.pem` 선택 -> `Save private key`).
2.  `PuTTY`를 실행합니다.
3.  `Host Name`에 `ubuntu@[EC2 퍼블릭 IP]`를 입력합니다.
4.  왼쪽 메뉴에서 `Connection` > `SSH` > `Auth` > `Credentials`로 이동합니다.
5.  `Private key file for authentication`에서 변환한 `.ppk` 파일을 선택하고 `Open`을 눌러 접속합니다.

### 2.2 방법 2: Windows PowerShell 또는 터미널 사용

```powershell
# .pem 파일이 있는 위치에서 아래 명령 실행
ssh -i "telegram-monitor-key.pem" ubuntu@[EC2 퍼블릭 IP]
```

---

## 3️⃣ 서버 초기 환경 설정

### 3.1 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
```

### 3.2 Python 및 Git 설치

Ubuntu 22.04 LTS에는 Python 3.10이 기본 설치되어 있지만, 최신 버전을 사용하기 위해 Python 3.12를 설치합니다.

```bash
sudo apt install python3.12 python3.12-venv python3-pip git -y
```

---

## 4️⃣ 코드 배포 (Git 사용)

### 4.1 Git 리포지토리 복제(Clone)

```bash
# 홈 디렉토리로 이동
cd ~

# GitHub에서 프로젝트 코드를 복제
# 아래 URL은 본인의 리포지토리 주소로 변경하세요.
git clone https://github.com/your-username/telegram-monitor-bot.git

# 생성된 프로젝트 디렉토리로 이동
cd telegram-monitor-bot
```

### 4.2 프로젝트 구조 확인

`ls -F` 명령어로 아래와 같은 파일들이 있는지 확인합니다.

```
AWS_EC2_배포_가이드.md  cleanup_sessions.py  fix_database_lock.py  monitor.py  requirements.txt  setup_session.py ...
```

---

## 5️⃣ 봇 실행 환경 설정

### 5.1 Python 가상환경 생성 및 활성화

프로젝트별 독립적인 환경을 위해 가상환경을 사용합니다.

```bash
# python3.12를 사용하여 venv 라는 이름의 가상환경 생성
python3.12 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# (참고) 가상환경 비활성화 시: deactivate
```

활성화되면 프롬프트 앞에 `(venv)`가 표시됩니다.

### 5.2 의존성 패키지 설치

`requirements.txt` 파일에 명시된 라이브러리들을 설치합니다.

```bash
pip install -r requirements.txt
```

### 5.3 환경변수 `.env` 파일 생성

API 키 등 민감한 정보를 `.env` 파일에 작성합니다.

```bash
nano .env
```

아래 내용을 복사하여 붙여넣고, 자신의 정보로 수정한 후 `Ctrl+X` -> `Y` -> `Enter`를 눌러 저장합니다.

```ini
# .env 파일 예시
# 텔레그램 API 인증 정보
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
PHONE_NUMBER=+821012345678

# 세션 파일 이름
SESSION_NAME=telegram_session

# 전달할 대상 채널 ID 또는 사용자명
TARGET_CHANNEL=-1001234567890 # 예시: 비공개 채널 ID

# 봇 토큰
BOT_TOKEN=1234567890:ABCDEFGHIJKL-mnopqrstuvwxyz12345678

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=telegram_monitor.log

# 제외할 키워드 (쉼표로 구분)
EXCLUDE_KEYWORDS=광고,스팸,홍보
```

### 5.4 텔레그램 세션 파일 생성

`monitor.py`를 실행하기 전, 사용자 계정 인증을 위한 `.session` 파일을 생성해야 합니다.

```bash
# (venv 가상환경이 활성화된 상태여야 함)
python3 setup_session.py
```

1.  터미널에 전화번호 인증 코드를 입력하라는 메시지가 나옵니다.
2.  텔레그램으로 전송된 로그인 코드를 입력하고 `Enter`를 누릅니다.
3.  **2단계 인증(클라우드 비밀번호)**이 설정된 경우, 비밀번호를 입력하고 `Enter`를 누릅니다.
4.  "세션 파일이 성공적으로 생성되었습니다" 메시지가 나오면 `Ctrl+C`를 눌러 프로그램을 종료합니다.
5.  `sessions/` 디렉토리 안에 `telegram_session.session` 파일이 생성되었는지 확인합니다.

---

## 6️⃣ 서비스 등록 (백그라운드 자동 실행)

`systemd`를 사용하여 스크립트가 서버 부팅 시 자동으로 시작되고, 오류 발생 시 재시작되도록 설정합니다.

### 6.1 `systemd` 서비스 파일 생성

```bash
sudo nano /etc/systemd/system/telegram-monitor.service
```

아래 내용을 복사하여 붙여넣고 저장합니다. 경로가 정확한지 반드시 확인하세요.

```ini
[Unit]
Description=Telegram Message Monitor Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram-monitor-bot
ExecStart=/home/ubuntu/telegram-monitor-bot/venv/bin/python /home/ubuntu/telegram-monitor-bot/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6.2 서비스 등록 및 시작

```bash
# systemd에 새로운 서비스 파일을 로드
sudo systemctl daemon-reload

# 서버 부팅 시 서비스가 자동으로 시작되도록 활성화
sudo systemctl enable telegram-monitor.service

# 서비스를 즉시 시작
sudo systemctl start telegram-monitor.service
```

### 6.3 서비스 상태 확인

```bash
sudo systemctl status telegram-monitor.service
```

`active (running)` 메시지가 녹색으로 표시되면 정상적으로 실행 중인 것입니다. 문제가 있다면 로그를 확인하여 원인을 파악합니다. (`journalctl -u telegram-monitor.service -f` 참고) 상태 확인 창을 빠져나오려면 `q`를 누릅니다.

---

## 7️⃣ 모니터링 및 코드 업데이트

### 7.1 로그 확인 방법

- **실시간 서비스 로그 확인 (권장):**

  ```bash
  sudo journalctl -u telegram-monitor.service -f
  ```

- **파일 로그 직접 확인:**

  ```bash
  tail -f /home/ubuntu/telegram-monitor-bot/telegram_monitor.log
  ```

### 7.2 서비스 관리 명령어

```bash
# 서비스 중지
sudo systemctl stop telegram-monitor.service

# 서비스 재시작 (코드 업데이트 후 사용)
sudo systemctl restart telegram-monitor.service

# 자동 시작 비활성화
sudo systemctl disable telegram-monitor.service
```

### 7.3 코드 업데이트 방법

1.  프로젝트 디렉토리로 이동합니다.

    ```bash
    cd /home/ubuntu/telegram-monitor-bot
    ```

2.  서비스를 잠시 중지합니다.

    ```bash
    sudo systemctl stop telegram-monitor.service
    ```

3.  Git 리포지토리에서 최신 코드를 가져옵니다.

    ```bash
    git pull origin main  # 'main'은 사용하는 브랜치 이름
    ```

4.  `requirements.txt`가 변경되었다면 패키지를 업데이트합니다.

    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```

5.  서비스를 다시 시작하여 변경사항을 적용합니다.

    ```bash
    sudo systemctl start telegram-monitor.service
    ```
