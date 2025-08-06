#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
텔레그램 메시지 모니터링 및 자동 전달 프로그램
- 모든 채널/그룹의 메시지 실시간 모니터링
- "open.kakao.com" 키워드가 포함된 메시지 감지
- [수정] 감지된 메시지를 '이미지/미디어'와 함께 지정된 대상 채널로 즉시 전달
- 파일 기반 해시 DB를 사용하여 재시작 및 포워딩 시 중복 전달 방지
"""

import os
import sys
import re
import logging
import asyncio
import atexit
import time
import hashlib
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events, errors
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
from dotenv import load_dotenv

# .env 파일 로드
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if not os.path.exists(ENV_FILE):
    print(f"오류: .env 파일을 찾을 수 없습니다. setup_session.py를 먼저 실행하세요.")
    sys.exit(1)

load_dotenv(ENV_FILE)

# 환경 변수 로드
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_NAME = os.getenv('SESSION_NAME', 'telegram_session')
TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', 'me')
BOT_TOKEN = os.getenv('BOT_TOKEN')
EXCLUDE_KEYWORDS = os.getenv('EXCLUDE_KEYWORDS', '').split(',') if os.getenv('EXCLUDE_KEYWORDS') else []
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'telegram_monitor.log')

# 환경 변수 검증
if not API_ID or not API_HASH or not PHONE_NUMBER:
    print("오류: API_ID, API_HASH, PHONE_NUMBER 환경 변수가 필요합니다.")
    print("setup_session.py를 실행하여 .env 파일을 설정하세요.")
    sys.exit(1)

if not BOT_TOKEN:
    print("오류: BOT_TOKEN 환경 변수가 필요합니다.")
    print(".env 파일에 BOT_TOKEN을 추가하세요.")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    print("오류: API_ID는 숫자여야 합니다.")
    sys.exit(1)

# 로깅 설정
log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

# Windows 콘솔 UTF-8 설정
if sys.platform == "win32":
    import locale
    try:
        os.system("chcp 65001 > nul")
    except:
        pass

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- 중복 방지 로직 (파일 기반) ---
HASH_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'forwarded_hashes.json')
forwarded_content_hashes = {}
# ---

# 키워드 패턴 (대소문자 구분 없이)
KEYWORD_PATTERN = re.compile(r'open\.kakao\.com', re.IGNORECASE)

# 제외 키워드 패턴 생성
EXCLUDE_PATTERNS = []
if EXCLUDE_KEYWORDS:
    for keyword in EXCLUDE_KEYWORDS:
        keyword = keyword.strip()
        if keyword:
            EXCLUDE_PATTERNS.append(re.compile(re.escape(keyword), re.IGNORECASE))

# 세션 파일 격리를 위한 디렉토리 생성
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR, mode=0o755)

# 세션 파일 경로 설정
USER_SESSION_PATH = os.path.join(SESSIONS_DIR, SESSION_NAME)
BOT_SESSION_PATH = os.path.join(SESSIONS_DIR, 'bot_session')

# 텔레그램 클라이언트 초기화
client = TelegramClient(USER_SESSION_PATH, API_ID, API_HASH)
bot_client = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)

# 전역 변수
target_entity = None
bot_target_entity = None

# 재연결 설정
MAX_RETRIES = 5
RETRY_DELAY = 30

# 프로세스 잠금 파일
LOCK_FILE = 'monitor.lock'

class SingleInstanceLock:
    """단일 인스턴스 실행을 보장하는 클래스"""
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_acquired = False
        
    def acquire(self):
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    old_pid = f.read().strip()
                if os.name != 'nt':
                    try:
                        os.kill(int(old_pid), 0)
                        logger.error(f"이미 실행 중인 프로세스가 있습니다 (PID: {old_pid})")
                        return False
                    except (OSError, ValueError, ProcessLookupError):
                        os.remove(self.lock_file)
                else:
                    stat = os.stat(self.lock_file)
                    if time.time() - stat.st_mtime < 300:
                        logger.error(f"최근에 생성된 lock 파일이 있습니다.")
                        return False
                    else:
                        os.remove(self.lock_file)
            
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            self.lock_acquired = True
            atexit.register(self.release)
            logger.info(f"프로세스 잠금 획득됨 (PID: {os.getpid()})")
            return True
            
        except Exception as e:
            logger.error(f"프로세스 잠금 획득 실패: {str(e)}")
            return False
    
    def release(self):
        if self.lock_acquired and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                logger.info("프로세스 잠금 해제됨")
                self.lock_acquired = False
            except Exception as e:
                logger.error(f"프로세스 잠금 해제 실패: {str(e)}")
    
    def __del__(self):
        self.release()

def load_hashes_from_file():
    """파일에서 전달된 메시지 해시 목록을 불러오고 오래된 기록(24시간)을 정리합니다."""
    global forwarded_content_hashes
    try:
        if os.path.exists(HASH_DB_FILE):
            with open(HASH_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            cutoff_time = datetime.now() - timedelta(hours=24)
            cleaned_hashes = {h: datetime.fromisoformat(ts_str) for h, ts_str in data.items() if datetime.fromisoformat(ts_str) > cutoff_time}

            forwarded_content_hashes = cleaned_hashes
            logger.info(f"해시 DB 로드 완료: {len(forwarded_content_hashes)}개의 기록을 불러왔습니다.")
            
            if len(data) != len(cleaned_hashes):
                logger.info(f"오래된 해시 기록 {len(data) - len(cleaned_hashes)}개를 정리했습니다.")
                save_hashes_to_file()
        else:
            logger.info("해시 DB 파일이 존재하지 않아 새로 시작합니다.")
            forwarded_content_hashes = {}

    except Exception as e:
        logger.error(f"해시 DB 파일 로드/처리 실패: {e}. 새 DB로 시작합니다.")
        forwarded_content_hashes = {}

def save_hashes_to_file():
    """현재 메시지 해시 목록을 파일에 저장합니다."""
    data_to_save = {h: dt.isoformat() for h, dt in forwarded_content_hashes.items()}
    try:
        with open(HASH_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4)
    except IOError as e:
        logger.error(f"해시 DB 파일 저장 실패: {e}")

def create_message_hash(text):
    """메시지 텍스트(캡션 포함)를 기반으로 고유 해시를 생성합니다."""
    normalized_text = re.sub(r'\s+', ' ', text.strip())
    hash_input = normalized_text.encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

def is_duplicate_message(text):
    """내용 기반 해시를 사용하여 중복 메시지인지 확인합니다."""
    global forwarded_content_hashes
    content_hash = create_message_hash(text)
    if content_hash in forwarded_content_hashes:
        logger.info(f"내용 기반 중복 메시지 감지 (Hash: {content_hash[:8]}...). 전달을 건너뜁니다.")
        return True
    return False

def mark_message_as_forwarded(text):
    """메시지를 전달됨으로 기록하고 파일에 즉시 저장합니다."""
    global forwarded_content_hashes
    content_hash = create_message_hash(text)
    forwarded_content_hashes[content_hash] = datetime.now()
    save_hashes_to_file()
    logger.debug(f"메시지 전달 기록 저장 및 파일 업데이트 완료: Hash={content_hash[:8]}")

async def get_entity_name(entity):
    """엔티티의 이름을 반환합니다."""
    try:
        if hasattr(entity, 'title'):
            name = entity.title
        elif hasattr(entity, 'first_name'):
            name = f"{entity.first_name} {entity.last_name or ''}".strip()
        elif hasattr(entity, 'username'):
            name = f"@{entity.username}"
        else:
            name = str(entity.id)
        return name.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.error(f"엔티티 이름 가져오기 오류: {str(e)}")
        return "알 수 없음"

async def resolve_target_entity():
    """대상 채널 엔티티를 해석합니다."""
    try:
        if TARGET_CHANNEL.lstrip('-').isdigit():
            entity = await client.get_entity(int(TARGET_CHANNEL))
        elif TARGET_CHANNEL.lower() == 'me':
            entity = await client.get_me()
        else:
            entity = await client.get_entity(TARGET_CHANNEL)
        
        name = await get_entity_name(entity)
        logger.info(f"대상 채널 설정: {name}")
        return entity
    except Exception as e:
        logger.error(f"대상 채널 해석 오류: {e}")
        logger.error("임시로 대상 채널을 자기 자신으로 설정합니다.")
        return await client.get_me()

async def resolve_bot_target_entity():
    """봇 클라이언트용 대상 채널 엔티티를 해석합니다."""
    try:
        if TARGET_CHANNEL.lstrip('-').isdigit():
            entity = await bot_client.get_entity(int(TARGET_CHANNEL))
        elif TARGET_CHANNEL.lower() == 'me':
            entity = await bot_client.get_me()
        else:
            entity = await bot_client.get_entity(TARGET_CHANNEL)
        
        name = await get_entity_name(entity)
        logger.info(f"봇용 대상 채널 설정: {name}")
        return entity
    except Exception as e:
        logger.error(f"봇용 대상 채널 해석 오류: {e}")
        logger.error("해결 방법: 봇을 해당 채널에 관리자로 추가하고 메시지 전송 권한을 부여하세요.")
        return None

@client.on(events.NewMessage())
async def handler(event):
    """모든 새 메시지를 처리하는 이벤트 핸들러"""
    try:
        # 메시지 텍스트(캡션 포함)가 없으면 무시
        if not event.message.text:
            return
        
        chat = await event.get_chat()
        if target_entity and chat.id == target_entity.id:
            return
        
        if is_duplicate_message(event.message.text):
            return
        
        if not KEYWORD_PATTERN.search(event.message.text):
            return
        
        for exclude_pattern in EXCLUDE_PATTERNS:
            if exclude_pattern.search(event.message.text):
                logger.info(f"제외 키워드 감지되어 메시지 전달을 건너뜁니다: {exclude_pattern.pattern}")
                return
        
        sender = await event.get_sender()
        chat_name = await get_entity_name(chat)
        sender_name = await get_entity_name(sender)
        
        logger.info(f"키워드 감지: {chat_name} / {sender_name}")
        logger.info(f"메시지 내용: {event.message.text[:100]}...")
        
        if not bot_target_entity:
            logger.error("봇용 대상 채널이 설정되지 않았습니다.")
            return
        
        # --- [핵심 수정 사항] ---
        # 미디어(이미지 등)가 있으면 함께 보내고, 없으면 텍스트만 보냄
        await bot_client.send_message(
            bot_target_entity,
            message=event.message.text,
            file=event.message.media
        )
        # ---
        
        media_type = f" ({event.message.media.mime_type})" if event.message.media else ""
        logger.info(f"봇을 통해 메시지{media_type} 전달 완료: {TARGET_CHANNEL}")
        
        mark_message_as_forwarded(event.message.text)
        
    except Exception as e:
        logger.error(f"메시지 처리 중 오류 발생: {str(e)}")

async def main():
    """메인 함수"""
    global target_entity, bot_target_entity
    
    lock = SingleInstanceLock(LOCK_FILE)
    if not lock.acquire():
        return
        
    load_hashes_from_file()
    
    retry_count = 0
    try:
        while retry_count < MAX_RETRIES:
            try:
                await client.start()
                await bot_client.start(bot_token=BOT_TOKEN)
                
                me = await client.get_me()
                logger.info(f"사용자 로그인 성공: {me.first_name} ({me.username})")
                
                bot_me = await bot_client.get_me()
                logger.info(f"봇 로그인 성공: {bot_me.first_name} (@{bot_me.username})")
                
                target_entity = await resolve_target_entity()
                bot_target_entity = await resolve_bot_target_entity()
                
                if not bot_target_entity:
                    logger.error("봇이 대상 채널에 접근할 수 없습니다. 프로그램을 종료합니다.")
                    return
                
                logger.info("모니터링 시작...")
                logger.info("Ctrl+C를 눌러 프로그램을 종료할 수 있습니다.")
                
                await client.run_until_disconnected()
                return
                
            except (errors.PhoneNumberInvalidError, errors.ApiIdInvalidError, 
                    errors.AuthKeyUnregisteredError, errors.SessionPasswordNeededError) as e:
                logger.error(f"인증 오류: {e}. setup_session.py를 다시 실행하세요.")
                return
            except (errors.ServerError, errors.FloodWaitError, ConnectionError) as e:
                retry_count += 1
                wait_time = RETRY_DELAY * retry_count
                logger.error(f"연결 오류: {str(e)}")
                logger.info(f"재연결 시도 {retry_count}/{MAX_RETRIES} ({wait_time}초 후)")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"예기치 않은 오류: {str(e)}")
                return
    
        if retry_count >= MAX_RETRIES:
            logger.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
    
    finally:
        if client.is_connected():
            await client.disconnect()
        if bot_client.is_connected():
            await bot_client.disconnect()
        lock.release()

if __name__ == "__main__":
    try:
        session_file = f"{USER_SESSION_PATH}.session"
        if not os.path.exists(session_file):
            print(f"오류: 세션 파일({session_file})을 찾을 수 없습니다.")
            print("setup_session.py를 실행하여 세션을 초기화하세요.")
            sys.exit(1)
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n최상위 레벨에서 예기치 않은 오류가 발생했습니다: {str(e)}")