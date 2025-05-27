#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
텔레그램 메시지 모니터링 및 자동 전달 프로그램
- 모든 채널/그룹의 메시지 실시간 모니터링
- "open.kakao.com" 키워드가 포함된 메시지 감지
- 감지된 메시지를 지정된 대상 채널로 즉시 전달
"""

import os
import sys
import re
import logging
import asyncio
import atexit
import time
import hashlib
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
        # Windows 콘솔 UTF-8 인코딩 설정
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

# 세션 파일 경로 설정 (격리된 디렉토리)
USER_SESSION_PATH = os.path.join(SESSIONS_DIR, SESSION_NAME)
BOT_SESSION_PATH = os.path.join(SESSIONS_DIR, 'bot_session')

# 텔레그램 클라이언트 초기화 (사용자 세션)
client = TelegramClient(USER_SESSION_PATH, API_ID, API_HASH)

# 봇 클라이언트 초기화 (메시지 전달용)
bot_client = TelegramClient(BOT_SESSION_PATH, API_ID, API_HASH)

# 전역 변수
target_entity = None
bot_target_entity = None

# 중복 전달 방지를 위한 전달된 메시지 ID 저장
forwarded_messages = set()

# 메시지 내용 기반 중복 방지 (해시값과 시간 저장)
forwarded_content_hashes = {}

# 재연결 설정
MAX_RETRIES = 5
RETRY_DELAY = 30  # 초

# 프로세스 잠금 파일
LOCK_FILE = 'monitor.lock'

class SingleInstanceLock:
    """
    단일 인스턴스 실행을 보장하는 클래스
    """
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.lock_acquired = False
        
    def acquire(self):
        """
        잠금 획득 시도
        """
        try:
            if os.path.exists(self.lock_file):
                # 기존 lock 파일이 있으면 PID 확인
                with open(self.lock_file, 'r') as f:
                    old_pid = f.read().strip()
                
                # Unix/Linux에서 프로세스 존재 확인
                if os.name != 'nt':
                    try:
                        os.kill(int(old_pid), 0)  # 프로세스 존재 확인
                        logger.error(f"이미 실행 중인 프로세스가 있습니다 (PID: {old_pid})")
                        logger.error("다른 monitor.py 인스턴스를 종료하거나 cleanup_sessions.py를 실행하세요.")
                        return False
                    except (OSError, ValueError, ProcessLookupError):
                        # 프로세스가 존재하지 않으면 lock 파일 삭제
                        logger.info(f"기존 lock 파일의 프로세스({old_pid})가 존재하지 않아 lock 파일을 제거합니다.")
                        os.remove(self.lock_file)
                else:
                    # Windows에서는 간단한 타임스탬프 기반 확인
                    stat = os.stat(self.lock_file)
                    if time.time() - stat.st_mtime < 300:  # 5분 이내면 실행 중으로 간주
                        logger.error(f"최근에 생성된 lock 파일이 있습니다.")
                        logger.error("다른 monitor.py 인스턴스를 종료하거나 cleanup_sessions.py를 실행하세요.")
                        return False
                    else:
                        os.remove(self.lock_file)
            
            # lock 파일 생성
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
        """
        잠금 해제
        """
        if self.lock_acquired and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                logger.info("프로세스 잠금 해제됨")
                self.lock_acquired = False
            except Exception as e:
                logger.error(f"프로세스 잠금 해제 실패: {str(e)}")
    
    def __del__(self):
        self.release()

def create_message_hash(text, chat_id):
    """
    메시지 텍스트와 채팅 ID를 기반으로 고유 해시 생성
    """
    # 텍스트 정규화 (공백, 줄바꿈 등 정리)
    normalized_text = re.sub(r'\s+', ' ', text.strip())
    # 해시 생성
    hash_input = f"{chat_id}:{normalized_text}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

def is_duplicate_message(text, chat_id, message_id):
    """
    중복 메시지인지 확인 (기록 추가는 하지 않음)
    """
    global forwarded_messages, forwarded_content_hashes
    
    current_time = datetime.now()
    
    # 1. 메시지 ID 기반 중복 확인
    message_key = (chat_id, message_id)
    if message_key in forwarded_messages:
        logger.debug(f"ID 기반 중복 메시지: {message_key}")
        return True
    
    # 2. 메시지 내용 기반 중복 확인 (5분 이내)
    content_hash = create_message_hash(text, chat_id)
    if content_hash in forwarded_content_hashes:
        last_forward_time = forwarded_content_hashes[content_hash]
        time_diff = current_time - last_forward_time
        
        if time_diff < timedelta(minutes=5):
            logger.debug(f"내용 기반 중복 메시지 (시간차: {time_diff.total_seconds()}초): {content_hash[:8]}...")
            return True
    
    return False

def mark_message_as_forwarded(text, chat_id, message_id):
    """
    메시지를 전달됨으로 기록
    """
    global forwarded_messages, forwarded_content_hashes
    
    current_time = datetime.now()
    
    # 메시지 ID와 내용 해시 기록
    message_key = (chat_id, message_id)
    content_hash = create_message_hash(text, chat_id)
    
    forwarded_messages.add(message_key)
    forwarded_content_hashes[content_hash] = current_time
    
    logger.debug(f"메시지 전달 기록 저장: ID={message_key}, Hash={content_hash[:8]}")
    
    # 메모리 정리 (메시지 ID)
    if len(forwarded_messages) > 10000:
        old_messages = list(forwarded_messages)[:5000]
        for old_msg in old_messages:
            forwarded_messages.discard(old_msg)
        logger.info(f"메모리 최적화: 오래된 메시지 ID {len(old_messages)}개 제거됨")
    
    # 메모리 정리 (내용 해시 - 1시간 이상 된 것)
    if len(forwarded_content_hashes) > 5000:
        cutoff_time = current_time - timedelta(hours=1)
        old_hashes = [h for h, t in forwarded_content_hashes.items() if t < cutoff_time]
        for old_hash in old_hashes:
            del forwarded_content_hashes[old_hash]
        logger.info(f"메모리 최적화: 오래된 내용 해시 {len(old_hashes)}개 제거됨")

async def get_entity_name(entity):
    """
    엔티티(채널, 그룹, 사용자)의 이름을 반환합니다.
    """
    try:
        if hasattr(entity, 'title'):
            name = entity.title
        elif hasattr(entity, 'first_name'):
            if hasattr(entity, 'last_name') and entity.last_name:
                name = f"{entity.first_name} {entity.last_name}"
            else:
                name = entity.first_name
        elif hasattr(entity, 'username'):
            name = f"@{entity.username}"
        else:
            name = str(entity.id)
        
        # 안전한 문자열 반환 (특수 문자 처리)
        return name.encode('utf-8', errors='replace').decode('utf-8')
    except Exception as e:
        logger.error(f"엔티티 이름 가져오기 오류: {str(e)}")
        return "알 수 없음"

async def resolve_target_entity():
    """
    대상 채널 엔티티를 해석합니다.
    """
    try:
        # 숫자인 경우 ID로 처리 (음수 포함)
        if TARGET_CHANNEL.lstrip('-').isdigit():
            entity = await client.get_entity(int(TARGET_CHANNEL))
        # 'me'인 경우 자기 자신으로 처리
        elif TARGET_CHANNEL.lower() == 'me':
            entity = await client.get_me()
        # 그 외의 경우 사용자명으로 처리
        else:
            entity = await client.get_entity(TARGET_CHANNEL)
        
        name = await get_entity_name(entity)
        logger.info(f"대상 채널 설정: {name}")
        return entity
    except Exception as e:
        logger.error(f"대상 채널 해석 오류: {str(e)}")
        logger.error(f"TARGET_CHANNEL '{TARGET_CHANNEL}'을(를) 찾을 수 없습니다.")
        logger.error("가능한 원인:")
        logger.error("1. 잘못된 채널 ID 또는 사용자명")
        logger.error("2. 해당 채널에 접근 권한이 없음")
        logger.error("3. 존재하지 않는 채널")
        logger.error("check_channels.py를 실행하여 올바른 채널 ID를 확인하세요.")
        logger.error("임시로 대상 채널을 자기 자신으로 설정합니다.")
        return await client.get_me()

async def resolve_bot_target_entity():
    """
    봇 클라이언트용 대상 채널 엔티티를 해석합니다.
    """
    try:
        # 숫자인 경우 ID로 처리 (음수 포함)
        if TARGET_CHANNEL.lstrip('-').isdigit():
            entity = await bot_client.get_entity(int(TARGET_CHANNEL))
        # 'me'인 경우 봇 자신으로 처리
        elif TARGET_CHANNEL.lower() == 'me':
            entity = await bot_client.get_me()
        # 그 외의 경우 사용자명으로 처리
        else:
            entity = await bot_client.get_entity(TARGET_CHANNEL)
        
        name = await get_entity_name(entity)
        logger.info(f"봇용 대상 채널 설정: {name}")
        return entity
    except Exception as e:
        logger.error(f"봇용 대상 채널 해석 오류: {str(e)}")
        logger.error(f"봇이 TARGET_CHANNEL '{TARGET_CHANNEL}'에 접근할 수 없습니다.")
        logger.error("가능한 원인:")
        logger.error("1. 봇이 해당 채널의 멤버가 아님")
        logger.error("2. 봇이 해당 채널에 메시지 전송 권한이 없음")
        logger.error("3. 잘못된 채널 ID 또는 사용자명")
        logger.error("해결 방법:")
        logger.error("1. 봇을 해당 채널에 관리자로 추가")
        logger.error("2. 봇에게 메시지 전송 권한 부여")
        return None

@client.on(events.NewMessage())
async def handler(event):
    """
    모든 새 메시지를 처리하는 이벤트 핸들러
    """
    try:
        # 메시지 텍스트 확인
        if not event.message.text:
            return
        
        # TARGET_CHANNEL에서 온 메시지는 감지하지 않음
        chat = await event.get_chat()
        if target_entity and chat.id == target_entity.id:
            return
        
        # 강화된 중복 메시지 확인
        if is_duplicate_message(event.message.text, chat.id, event.message.id):
            return
        
        # 키워드 확인
        if not KEYWORD_PATTERN.search(event.message.text):
            return
        
        # 제외 키워드 확인
        for exclude_pattern in EXCLUDE_PATTERNS:
            if exclude_pattern.search(event.message.text):
                logger.info(f"제외 키워드 감지되어 메시지 전달을 건너뜁니다: {exclude_pattern.pattern}")
                return
        
        # 메시지 발신자 정보 가져오기
        sender = await event.get_sender()
        
        chat_name = await get_entity_name(chat)
        sender_name = await get_entity_name(sender)
        
        # 로그 기록
        logger.info(f"키워드 감지: {chat_name} / {sender_name}")
        logger.info(f"메시지 내용: {event.message.text[:100]}...")
        
        # 대상 채널로 메시지 전달 (봇용 전역 변수 사용)
        if not bot_target_entity:
            logger.error("봇용 대상 채널이 설정되지 않았습니다.")
            return
        
        # 봇을 통해 원문만 전달
        await bot_client.send_message(bot_target_entity, event.message.text)
        logger.info(f"봇을 통해 메시지 전달 완료: {TARGET_CHANNEL}")
        
        # 전달 성공 후 중복 방지를 위해 기록
        mark_message_as_forwarded(event.message.text, chat.id, event.message.id)
        
    except Exception as e:
        logger.error(f"메시지 처리 중 오류 발생: {str(e)}")

async def main():
    """
    메인 함수
    """
    global target_entity, bot_target_entity
    
    # 단일 인스턴스 잠금 획득
    lock = SingleInstanceLock(LOCK_FILE)
    if not lock.acquire():
        logger.error("이미 다른 monitor.py 인스턴스가 실행 중입니다.")
        return
    
    retry_count = 0
    
    try:
        while retry_count < MAX_RETRIES:
            try:
                # 사용자 클라이언트 연결
                await client.start()
                
                # 봇 클라이언트 연결
                await bot_client.start(bot_token=BOT_TOKEN)
                
                # 사용자 정보 가져오기
                me = await client.get_me()
                logger.info(f"사용자 로그인 성공: {me.first_name} ({me.username})")
                
                # 봇 정보 가져오기
                bot_me = await bot_client.get_me()
                logger.info(f"봇 로그인 성공: {bot_me.first_name} (@{bot_me.username})")
                
                # 대상 채널 확인 (사용자 세션용)
                target_entity = await resolve_target_entity()
                
                # 봇용 대상 채널 확인
                bot_target_entity = await resolve_bot_target_entity()
                
                if not bot_target_entity:
                    logger.error("봇이 대상 채널에 접근할 수 없습니다. 프로그램을 종료합니다.")
                    logger.error("봇을 해당 채널에 관리자로 추가하고 메시지 전송 권한을 부여하세요.")
                    return
                
                logger.info("모니터링 시작: 모든 채널/그룹의 메시지를 모니터링합니다.")
                logger.info("키워드 필터: 'open.kakao.com'")
                if EXCLUDE_KEYWORDS:
                    logger.info(f"제외 키워드: {', '.join(EXCLUDE_KEYWORDS)}")
                else:
                    logger.info("제외 키워드: 없음")
                logger.info(f"대상 채널: {TARGET_CHANNEL}")
                logger.info("참고: 대상 채널에서 오는 메시지는 감지하지 않습니다.")
                logger.info("메시지 전달: 봇을 통해 전달됩니다.")
                logger.info("중복 방지: 최초 키워드 메시지만 전달, 5분간 동일 내용 차단")
                logger.info("Ctrl+C를 눌러 프로그램을 종료할 수 있습니다.")
                
                # 무한 실행
                await client.run_until_disconnected()
                return
                
            except errors.PhoneNumberInvalidError:
                logger.error("유효하지 않은 전화번호입니다.")
                return
            except errors.ApiIdInvalidError:
                logger.error("유효하지 않은 API ID 또는 API Hash입니다.")
                return
            except errors.AuthKeyUnregisteredError:
                logger.error("인증 키가 등록되지 않았습니다. setup_session.py를 다시 실행하세요.")
                return
            except errors.SessionPasswordNeededError:
                logger.error("2단계 인증이 필요합니다. setup_session.py를 다시 실행하세요.")
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
        
        # 최대 재시도 횟수 초과
        if retry_count >= MAX_RETRIES:
            logger.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다. 프로그램을 종료합니다.")
        
    finally:
        # 연결 종료
        try:
            await client.disconnect()
            await bot_client.disconnect()
        except:
            pass
        
        # 잠금 해제
        lock.release()

if __name__ == "__main__":
    try:
        # 세션 파일 확인 (격리된 디렉토리에서)
        session_file = f"{USER_SESSION_PATH}.session"
        if not os.path.exists(session_file):
            print(f"오류: 세션 파일({session_file})을 찾을 수 없습니다.")
            print("fix_database_lock.py를 실행한 후 setup_session.py를 실행하여 세션을 초기화하세요.")
            sys.exit(1)
        
        # 비동기 함수 실행
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n예기치 않은 오류가 발생했습니다: {str(e)}")
