# AWS EC2 텔레그램 봇 배포 가이드 🚀

## 📋 준비 사항

- AWS 계정
- 현재 작동 중인 텔레그램 봇 파일들
- `.env` 파일 설정 완료
- 봇 토큰 및 API 키 준비

---

## 1️⃣ AWS EC2 인스턴스 생성

### 1.1 AWS Console 접속

1. [AWS Console](https://aws.amazon.com/console/) 로그인
2. **EC2** 서비스 선택
3. **인스턴스 시작** 클릭

### 1.2 인스턴스 설정

```
◾ 이름: telegram-monitor
◾ OS: Ubuntu Server 22.04 LTS (프리티어 가능)
◾ 인스턴스 유형: t2.micro (프리티어)
◾ 키 페어: 새로 생성 또는 기존 사용
```

### 1.3 키 페어 생성 (새로 생성하는 경우)

1. **새 키 페어 생성** 선택
2. 키 페어 이름: `telegram-bot-key`
3. 키 페어 유형: **RSA**
4. 프라이빗 키 파일 형식: **.pem**
5. **키 페어 생성** → 자동으로 `.pem` 파일 다운로드
6. ⚠️ **중요**: 다운로드된 `.pem` 파일을 안전한 곳에 보관

### 1.4 네트워크 설정

```
◾ VPC: 기본값
◾ 서브넷: 기본값
◾ 퍼블릭 IP 자동 할당: 활성화
◾ 보안 그룹: 새로 생성
```

### 1.5 보안 그룹 설정

```
보안 그룹 이름: telegram-bot-sg

인바운드 규칙:
- SSH (22) | 내 IP | 설명: SSH 접속용
```

### 1.6 스토리지 설정

```
◾ 크기: 8GB (프리티어 기본값)
◾ 볼륨 유형: gp3
```

### 1.7 인스턴스 시작

- 설정 검토 후 **인스턴스 시작** 클릭
- 인스턴스가 **running** 상태가 될 때까지 대기 (1-2분)

---

## 2️⃣ EC2 인스턴스 접속 (Windows)

### 2.1 방법 1: PuTTY 사용 (권장)

#### PuTTY 설치

1. [PuTTY 다운로드](https://www.putty.org/) 및 설치
2. PuTTYgen도 함께 설치됨

#### 키 변환 (.pem → .ppk)

1. **PuTTYgen** 실행
2. **Load** 클릭 → 다운로드한 `.pem` 파일 선택
3. **Save private key** 클릭 → `.ppk` 파일로 저장

#### PuTTY 접속

1. **PuTTY** 실행
2. 설정:
   ```
   Host Name: ubuntu@[EC2 퍼블릭 IP]
   Port: 22
   Connection type: SSH
   ```
3. **Connection** → **SSH** → **Auth** → **Credentials**
4. **Private key file for authentication** → `.ppk` 파일 선택
5. **Open** 클릭하여 접속

### 2.2 방법 2: Windows PowerShell 사용

```powershell
# .pem 파일 권한 설정
icacls "telegram-bot-key.pem" /inheritance:r
icacls "telegram-bot-key.pem" /grant:r "%username%:R"

# SSH 접속
ssh -i "telegram-bot-key.pem" ubuntu@52.65.162.105
```

---

## 3️⃣ 서버 환경 설정

### 3.1 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
```

### 3.2 Python 및 필수 패키지 설치

```bash
# Python 3.11 설치
sudo apt install python3.12 python3.12-venv python3-pip -y

# Git 설치
sudo apt install git -y
```

### 3.3 작업 디렉토리 생성

```bash
mkdir ~/telegram-bot
cd ~/telegram-bot
```

---

## 4️⃣ 코드 업로드

### 4.1 방법 1: Git 사용 (권장)

```bash
# GitHub 리포지토리가 있는 경우
# (예시) git clone https://github.com/yourusername/coffee-bot-v2.git
cd coffee-bot\ v2
```

### 4.2 방법 2: 파일 직접 업로드

#### Windows에서 SCP 사용 (PowerShell)

```powershell
# 현재 프로젝트 폴더에서 실행
scp -i "telegram-bot-key.pem" -r . ubuntu@[EC2 퍼블릭 IP]:~/coffee-bot-v2/
```

#### WinSCP 사용 (GUI)

1. [WinSCP 다운로드](https://winscp.net/) 및 설치
2. 새 세션 생성:
   ```
   호스트명: [EC2 퍼블릭 IP]
   사용자명: ubuntu
   개인키 파일: telegram-bot-key.ppk
   ```
3. 연결 후 파일 드래그 앤 드롭으로 업로드

### 4.3 방법 3: 파일 내용 직접 생성

```bash
# 각 파일을 nano 에디터로 생성
nano monitor.py
# 내용을 복사 붙여넣기

nano setup_session.py
# 내용을 복사 붙여넣기

nano requirements.txt
# 필요한 패키지들 작성
```

---

## 5️⃣ 환경 설정

### 5.1 Python 가상환경 생성

```bash
cd ~/coffee-bot-v2
python3 -m venv venv
source venv/bin/activate
```

### 5.2 필요한 패키지 설치

```bash
# requirements.txt 생성 (없는 경우)
echo "telethon>=1.34.0
python-dotenv>=1.0.0" > requirements.txt

# 패키지 설치
pip install -r requirements.txt
```

### 5.3 환경변수 파일 생성

```bash
nano .env
```

.env 파일 예시:

```
# 텔레그램 API 인증 정보
API_ID=29240486
API_HASH=ebe20bb8a9310116cac2ffdef39cd904
PHONE_NUMBER=+821090754530

# 세션 설정
SESSION_NAME=telegram_session

# 대상 채널 설정
TARGET_CHANNEL=-1002158002807

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=telegram_monitor.log

# (선택) 봇 토큰 및 제외 키워드 등
BOT_TOKEN=7315190305:AAG36KFHWzfx1cobSk5VbC_CmfX4lM3W1nw
EXCLUDE_KEYWORDS=골수이형성증후군,츄카피,오렌지왕조,Sign,펑크비즘,Hamilton,해밀턴,유후갱단,GRND,무벌스,MOVERSE,X-PASS,echo,PALIO,Palio,하양이아빠,XPLA,크몽,젬하다,ZOOMEX,코인한나,벨러,주멕스,ORBS,Orbs,마비아,틱톡,Fracatal,클레바,라임라잇,부업,뉴트론,티프로,WPG,맨틀,알렉스,CCGG,CHIWAT
```

### 5.4 세션 파일 생성

```bash
# 세션 초기화 (최초 1회만)
python3 setup_session.py
```

- 전화번호 인증코드 입력
- 2FA 설정된 경우 비밀번호 입력
- `Ctrl + C`로 종료

---

## 6️⃣ 서비스로 등록 (자동 실행)

### 6.1 systemd 서비스 파일 생성

```bash
sudo nano /etc/systemd/system/coffee-bot-v2.service
```

서비스 파일 내용 예시:

```ini
[Unit]
Description=Telegram Coffee Bot v2
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/coffee-bot-v2
Environment=PATH=/home/ubuntu/coffee-bot-v2/venv/bin
ExecStart=/home/ubuntu/coffee-bot-v2/venv/bin/python monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6.2 서비스 등록 및 시작

```bash
# 서비스 등록
sudo systemctl daemon-reload
sudo systemctl enable coffee-bot-v2.service

# 서비스 시작
sudo systemctl start coffee-bot-v2.service

# 서비스 상태 확인
sudo systemctl status coffee-bot-v2.service
```

---

## 7️⃣ 모니터링 및 관리

### 7.1 로그 확인

```bash
# 실시간 로그 확인
sudo journalctl -u telegram-monitor.service -f

# 최근 로그 확인
sudo journalctl -u telegram-monitor.service --lines=50

# 파일 로그 확인
tail -f ~/telegram-bot/telegram_monitor.log
```

### 7.2 서비스 관리 명령어

```bash
# 서비스 중지
sudo systemctl stop telegram-monitor.service

# 서비스 재시작
sudo systemctl restart telegram-monitor.service

# 서비스 비활성화 (자동 시작 해제)
sudo systemctl disable telegram-monitor.service
```

### 7.3 코드 업데이트

```bash
cd ~/telegram-bot

# 서비스 중지
sudo systemctl stop telegram-monitor.service

# 코드 업데이트 (Git 사용하는 경우)
git pull origin main

# 패키지 업데이트 (필요한 경우)
source venv/bin/activate
pip install -r requirements.txt

# 서비스 재시작
sudo systemctl start telegram-monitor.service
```

---

## 8️⃣ 보안 설정

### 8.1 방화벽 설정

```bash
# UFW 방화벽 활성화
sudo ufw enable

# SSH 포트만 허용
sudo ufw allow ssh

# 방화벽 상태 확인
sudo ufw status
```

### 8.2 SSH 키 인증만 허용 (권장)

```bash
sudo nano /etc/ssh/sshd_config
```

다음 설정 변경:

```
PasswordAuthentication no
PubkeyAuthentication yes
```

SSH 재시작:

```bash
sudo systemctl restart ssh
```

---

## 9️⃣ 백업 설정

### 9.1 자동 백업 스크립트 생성

```bash
nano ~/backup.sh
```

백업 스크립트:

```bash
#!/bin/bash
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/home/ubuntu/backups"

mkdir -p $BACKUP_DIR

# 소스코드 백업
tar -czf $BACKUP_DIR/telegram-bot_$DATE.tar.gz -C /home/ubuntu telegram-bot

# 오래된 백업 파일 삭제 (7일 이상)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: telegram-bot_$DATE.tar.gz"
```

실행 권한 부여:

```bash
chmod +x ~/backup.sh
```

### 9.2 자동 백업 cron 설정

```bash
crontab -e

# 매일 새벽 3시에 백업
0 3 * * * /home/ubuntu/backup.sh >> /home/ubuntu/backup.log 2>&1
```

---

## 🔧 문제 해결

### 자주 발생하는 문제들

#### 1. 세션 파일 권한 오류

```bash
chmod 600 telegram_session.session
```

#### 2. 메모리 부족 (t2.micro)

```bash
# 스왑 파일 생성
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 적용
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 3. 봇 권한 오류

- 봇을 대상 채널에 관리자로 추가
- 메시지 전송 권한 부여

#### 4. 네트워크 연결 오류

```bash
# DNS 설정 확인
sudo nano /etc/resolv.conf

# 구글 DNS 추가
nameserver 8.8.8.8
nameserver 8.8.4.4
```

---

## ✅ 배포 완료 체크리스트

- [ ] EC2 인스턴스 생성 완료
- [ ] SSH 접속 성공
- [ ] Python 환경 설정 완료
- [ ] 코드 업로드 완료
- [ ] `.env` 파일 설정 완료
- [ ] 세션 파일 생성 완료
- [ ] 봇 권한 설정 완료
- [ ] systemd 서비스 등록 완료
- [ ] 서비스 정상 실행 확인
- [ ] 로그 모니터링 설정 완료
- [ ] 백업 설정 완료

---

## 💰 비용 관리

### 프리티어 사용 시

- t2.micro: 월 750시간 무료
- EBS 스토리지: 30GB 무료
- 데이터 전송: 15GB 무료

### 비용 절약 팁

1. **인스턴스 중지**: 사용하지 않을 때 중지
2. **스팟 인스턴스**: 비용 절약 (중단 가능성 있음)
3. **모니터링**: CloudWatch로 리소스 사용량 확인

---

이제 AWS EC2에서 24/7 텔레그램 모니터링 봇이 자동으로 실행됩니다! 🎉
