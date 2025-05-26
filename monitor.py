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
from datetime import datetime
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

# 텔레그램 클라이언트 초기화 (사용자 세션)
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# 봇 클라이언트 초기화 (메시지 전달용)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)

# 전역 변수
target_entity = None
bot_target_entity = None

# 중복 전달 방지를 위한 전달된 메시지 ID 저장
forwarded_messages = set()

# 재연결 설정
MAX_RETRIES = 5
RETRY_DELAY = 30  # 초

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
        
        # 중복 메시지 확인 (chat_id와 message_id로 고유 식별)
        message_key = (chat.id, event.message.id)
        if message_key in forwarded_messages:
            logger.debug(f"이미 전달된 메시지입니다. 건너뜁니다: {message_key}")
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
        
        # 전달된 메시지 ID 저장 (중복 방지용)
        forwarded_messages.add(message_key)
        logger.debug(f"메시지 ID 저장됨: {message_key}")
        
        # 메모리 관리: 저장된 메시지 ID가 10000개를 초과하면 절반 제거
        if len(forwarded_messages) > 10000:
            # 가장 오래된 메시지 ID들을 제거 (set이므로 임의로 제거)
            old_messages = list(forwarded_messages)[:5000]
            for old_msg in old_messages:
                forwarded_messages.discard(old_msg)
            logger.info(f"메모리 최적화: 오래된 메시지 ID {len(old_messages)}개 제거됨")
        
    except Exception as e:
        logger.error(f"메시지 처리 중 오류 발생: {str(e)}")

async def main():
    """
    메인 함수
    """
    global target_entity, bot_target_entity
    retry_count = 0
    
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
                break
            
            logger.info("모니터링 시작: 모든 채널/그룹의 메시지를 모니터링합니다.")
            logger.info("키워드 필터: 'open.kakao.com'")
            if EXCLUDE_KEYWORDS:
                logger.info(f"제외 키워드: {', '.join(EXCLUDE_KEYWORDS)}")
            else:
                logger.info("제외 키워드: 없음")
            logger.info(f"대상 채널: {TARGET_CHANNEL}")
            logger.info("참고: 대상 채널에서 오는 메시지는 감지하지 않습니다.")
            logger.info("메시지 전달: 봇을 통해 전달됩니다.")
            logger.info("Ctrl+C를 눌러 프로그램을 종료할 수 있습니다.")
            
            # 무한 실행
            await client.run_until_disconnected()
            break
            
        except errors.PhoneNumberInvalidError:
            logger.error("유효하지 않은 전화번호입니다.")
            break
        except errors.ApiIdInvalidError:
            logger.error("유효하지 않은 API ID 또는 API Hash입니다.")
            break
        except errors.AuthKeyUnregisteredError:
            logger.error("인증 키가 등록되지 않았습니다. setup_session.py를 다시 실행하세요.")
            break
        except errors.SessionPasswordNeededError:
            logger.error("2단계 인증이 필요합니다. setup_session.py를 다시 실행하세요.")
            break
        except (errors.ServerError, errors.FloodWaitError, ConnectionError) as e:
            retry_count += 1
            wait_time = RETRY_DELAY * retry_count
            
            logger.error(f"연결 오류: {str(e)}")
            logger.info(f"재연결 시도 {retry_count}/{MAX_RETRIES} ({wait_time}초 후)")
            
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"예기치 않은 오류: {str(e)}")
            break
    
    # 최대 재시도 횟수 초과
    if retry_count >= MAX_RETRIES:
        logger.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다. 프로그램을 종료합니다.")
    
    # 연결 종료
    try:
        await client.disconnect()
        await bot_client.disconnect()
    except:
        pass

if __name__ == "__main__":
    try:
        # 세션 파일 확인
        session_file = f"{SESSION_NAME}.session"
        if not os.path.exists(session_file):
            print(f"오류: 세션 파일({session_file})을 찾을 수 없습니다.")
            print("setup_session.py를 먼저 실행하여 세션을 초기화하세요.")
            sys.exit(1)
        
        # 비동기 함수 실행
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n예기치 않은 오류가 발생했습니다: {str(e)}")
