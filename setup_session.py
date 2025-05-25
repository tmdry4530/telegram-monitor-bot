#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
텔레그램 세션 초기화 스크립트
- API ID, API Hash, 전화번호를 입력받아 텔레그램 세션 파일 생성
- 인증 코드 입력 처리 및 세션 파일 저장
- 에러 핸들링 및 안내 메시지 제공
"""

import os
import sys
import logging
import asyncio
from telethon import TelegramClient, errors
from dotenv import load_dotenv, set_key

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# .env 파일 경로
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

async def create_session():
    """
    사용자 입력을 받아 텔레그램 세션을 생성하고 .env 파일에 저장합니다.
    """
    # .env 파일 로드 (존재하는 경우)
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE)
        
    # 기존 환경 변수 값 가져오기 (있는 경우)
    api_id = os.getenv('API_ID', '')
    api_hash = os.getenv('API_HASH', '')
    phone_number = os.getenv('PHONE_NUMBER', '')
    session_name = os.getenv('SESSION_NAME', 'telegram_session')
    
    # 사용자 입력 받기
    print("\n===== 텔레그램 세션 초기화 =====")
    print("https://my.telegram.org에서 API ID와 API Hash를 발급받으세요.\n")
    
    if not api_id:
        api_id = input("API ID를 입력하세요: ")
    else:
        change = input(f"기존 API ID ({api_id})를 사용하시겠습니까? (y/n): ")
        if change.lower() != 'y':
            api_id = input("새 API ID를 입력하세요: ")
    
    if not api_hash:
        api_hash = input("API Hash를 입력하세요: ")
    else:
        change = input(f"기존 API Hash ({api_hash[:5]}...)를 사용하시겠습니까? (y/n): ")
        if change.lower() != 'y':
            api_hash = input("새 API Hash를 입력하세요: ")
    
    if not phone_number:
        phone_number = input("전화번호를 입력하세요 (국가 코드 포함, 예: +821012345678): ")
    else:
        change = input(f"기존 전화번호 ({phone_number})를 사용하시겠습니까? (y/n): ")
        if change.lower() != 'y':
            phone_number = input("새 전화번호를 입력하세요 (국가 코드 포함, 예: +821012345678): ")
    
    change_session = input(f"세션 이름 ({session_name})을 변경하시겠습니까? (y/n): ")
    if change_session.lower() == 'y':
        session_name = input("새 세션 이름을 입력하세요: ")
    
    # 환경 변수 검증
    try:
        api_id = int(api_id)
    except ValueError:
        logger.error("API ID는 숫자여야 합니다.")
        return False
    
    if not api_hash or len(api_hash) < 10:
        logger.error("유효한 API Hash를 입력하세요.")
        return False
    
    if not phone_number or not phone_number.startswith('+'):
        logger.error("전화번호는 국가 코드(+)를 포함해야 합니다.")
        return False
    
    # 텔레그램 클라이언트 생성 및 연결
    logger.info("텔레그램 서버에 연결 중...")
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        await client.connect()
        
        # 이미 인증된 경우
        if await client.is_user_authorized():
            logger.info("이미 인증된 세션입니다.")
            await client.disconnect()
            
            # .env 파일에 환경 변수 저장
            save_to_env(api_id, api_hash, phone_number, session_name)
            
            logger.info(f"세션 파일이 '{session_name}.session'으로 저장되었습니다.")
            return True
        
        # 인증 코드 요청
        logger.info(f"{phone_number}로 인증 코드를 요청합니다...")
        await client.send_code_request(phone_number)
        
        # 인증 코드 입력
        code = input("\n텔레그램에서 받은 인증 코드를 입력하세요: ")
        
        try:
            await client.sign_in(phone_number, code)
        except errors.SessionPasswordNeededError:
            # 2단계 인증이 활성화된 경우
            password = input("2단계 인증이 활성화되어 있습니다. 비밀번호를 입력하세요: ")
            await client.sign_in(password=password)
        
        # 인증 완료
        me = await client.get_me()
        logger.info(f"인증 성공! {me.first_name} ({me.username}) 계정으로 로그인되었습니다.")
        
        # 연결 종료
        await client.disconnect()
        
        # .env 파일에 환경 변수 저장
        save_to_env(api_id, api_hash, phone_number, session_name)
        
        logger.info(f"세션 파일이 '{session_name}.session'으로 저장되었습니다.")
        return True
        
    except errors.PhoneNumberInvalidError:
        logger.error("유효하지 않은 전화번호입니다. 국가 코드를 포함하여 다시 시도하세요.")
    except errors.ApiIdInvalidError:
        logger.error("유효하지 않은 API ID 또는 API Hash입니다.")
    except errors.PhoneCodeInvalidError:
        logger.error("유효하지 않은 인증 코드입니다.")
    except errors.PhoneCodeExpiredError:
        logger.error("인증 코드가 만료되었습니다. 다시 시도하세요.")
    except errors.SessionPasswordNeededError:
        logger.error("2단계 인증 비밀번호가 필요합니다.")
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
    
    # 오류 발생 시 연결 종료
    try:
        await client.disconnect()
    except:
        pass
    
    return False

def save_to_env(api_id, api_hash, phone_number, session_name):
    """
    환경 변수를 .env 파일에 저장합니다.
    """
    # .env 파일이 없으면 생성
    if not os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write("# 텔레그램 API 인증 정보\n")
    
    # 환경 변수 설정
    set_key(ENV_FILE, 'API_ID', str(api_id))
    set_key(ENV_FILE, 'API_HASH', api_hash)
    set_key(ENV_FILE, 'PHONE_NUMBER', phone_number)
    set_key(ENV_FILE, 'SESSION_NAME', session_name)
    
    # 기본 대상 채널 설정 (없는 경우)
    if not os.getenv('TARGET_CHANNEL'):
        set_key(ENV_FILE, 'TARGET_CHANNEL', 'me')  # 기본값은 자기 자신
    
    # 로깅 설정 (없는 경우)
    if not os.getenv('LOG_LEVEL'):
        set_key(ENV_FILE, 'LOG_LEVEL', 'INFO')
    if not os.getenv('LOG_FILE'):
        set_key(ENV_FILE, 'LOG_FILE', 'telegram_monitor.log')
    
    logger.info(f".env 파일이 생성/업데이트되었습니다: {ENV_FILE}")

def main():
    """
    메인 함수
    """
    try:
        # 비동기 함수 실행
        success = asyncio.run(create_session())
        
        if success:
            print("\n===== 세션 초기화 완료 =====")
            print("이제 monitor.py를 실행하여 메시지 모니터링을 시작할 수 있습니다.")
            print("대상 채널을 변경하려면 .env 파일의 TARGET_CHANNEL 값을 수정하세요.")
        else:
            print("\n===== 세션 초기화 실패 =====")
            print("오류를 확인하고 다시 시도하세요.")
        
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n예기치 않은 오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    main()
