#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
데이터베이스 잠금 문제 해결 스크립트
- 모든 관련 프로세스 강제 종료
- 세션 파일 완전 정리
- 파일 권한 및 잠금 해제
- 안전한 재시작 준비
"""

import os
import sys
import glob
import time
import sqlite3
import subprocess
import signal
from pathlib import Path

def force_kill_processes():
    """
    모든 관련 프로세스를 강제로 종료
    """
    print("=== 관련 프로세스 강제 종료 ===")
    
    try:
        # systemd 서비스 중지
        print("1. systemd 서비스 중지...")
        subprocess.run(['sudo', 'systemctl', 'stop', 'telegram-monitor-bot.service'], 
                      capture_output=True)
        time.sleep(2)
        
        # monitor.py 프로세스 찾기 및 종료
        print("2. monitor.py 프로세스 검색 및 종료...")
        result = subprocess.run(['pgrep', '-f', 'monitor.py'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"   PID {pid} 종료 중...")
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except:
                        pass
        
        # telethon/telegram 관련 프로세스 종료
        print("3. telethon 관련 프로세스 검색 및 종료...")
        for pattern in ['telegram', 'telethon', 'bot_session']:
            result = subprocess.run(['pgrep', '-f', pattern], 
                                  capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        print(f"   {pattern} PID {pid} 종료 중...")
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except:
                            pass
        
        print("4. 잠시 대기 (프로세스 완전 종료)...")
        time.sleep(3)
        
    except Exception as e:
        print(f"프로세스 종료 중 오류: {e}")

def unlock_and_remove_sessions():
    """
    모든 세션 파일 잠금 해제 및 삭제
    """
    print("\n=== 세션 파일 정리 ===")
    
    # 모든 가능한 세션 파일 패턴
    session_patterns = [
        "*.session*",
        "telegram_session*",
        "bot_session*",
        "monitor.lock",
        "*.db*",
        "*-wal",
        "*-shm"
    ]
    
    removed_files = []
    
    for pattern in session_patterns:
        files = glob.glob(pattern)
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    # 파일 권한 변경 시도
                    try:
                        os.chmod(file_path, 0o777)
                    except:
                        pass
                    
                    # SQLite 파일인 경우 강제 잠금 해제 시도
                    if file_path.endswith('.session') or '.db' in file_path:
                        try:
                            # 짧은 연결로 잠금 해제 시도
                            conn = sqlite3.connect(file_path, timeout=0.1)
                            conn.execute("PRAGMA journal_mode=WAL;")
                            conn.execute("PRAGMA journal_mode=DELETE;")
                            conn.close()
                        except:
                            pass
                    
                    # 파일 삭제
                    os.remove(file_path)
                    removed_files.append(file_path)
                    print(f"   삭제됨: {file_path}")
                    
            except Exception as e:
                print(f"   삭제 실패: {file_path} - {e}")
                # 강제 삭제 시도
                try:
                    subprocess.run(['sudo', 'rm', '-f', file_path], capture_output=True)
                    print(f"   강제 삭제됨: {file_path}")
                    removed_files.append(file_path)
                except:
                    print(f"   강제 삭제도 실패: {file_path}")
    
    if removed_files:
        print(f"\n총 {len(removed_files)}개 파일이 삭제되었습니다.")
    else:
        print("\n삭제할 세션 파일이 없습니다.")

def check_file_permissions():
    """
    현재 디렉토리 권한 확인 및 수정
    """
    print("\n=== 파일 권한 확인 ===")
    
    current_dir = os.getcwd()
    print(f"현재 디렉토리: {current_dir}")
    
    # 디렉토리 권한 확인
    try:
        # 쓰기 권한 테스트
        test_file = os.path.join(current_dir, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("✓ 디렉토리 쓰기 권한 정상")
    except Exception as e:
        print(f"✗ 디렉토리 쓰기 권한 문제: {e}")
        print("권한 수정 시도 중...")
        try:
            subprocess.run(['chmod', '755', current_dir], capture_output=True)
        except:
            pass

def verify_cleanup():
    """
    정리 작업 검증
    """
    print("\n=== 정리 작업 검증 ===")
    
    # 관련 프로세스 확인
    result = subprocess.run(['pgrep', '-f', 'monitor.py'], 
                          capture_output=True, text=True)
    if result.stdout.strip():
        print("⚠️  monitor.py 프로세스가 여전히 실행 중입니다:")
        print(result.stdout)
    else:
        print("✓ monitor.py 프로세스 없음")
    
    # 세션 파일 확인
    session_files = glob.glob("*.session*") + glob.glob("*monitor.lock*")
    if session_files:
        print("⚠️  남은 세션 파일:")
        for f in session_files:
            print(f"   {f}")
    else:
        print("✓ 세션 파일 모두 정리됨")

def create_session_isolation():
    """
    세션 파일 격리를 위한 디렉토리 생성
    """
    print("\n=== 세션 격리 디렉토리 생성 ===")
    
    sessions_dir = os.path.join(os.getcwd(), 'sessions')
    if not os.path.exists(sessions_dir):
        os.makedirs(sessions_dir, mode=0o755)
        print(f"✓ 세션 디렉토리 생성: {sessions_dir}")
    else:
        print(f"✓ 세션 디렉토리 존재: {sessions_dir}")
    
    return sessions_dir

def main():
    print("=" * 60)
    print("텔레그램 데이터베이스 잠금 해제 스크립트")
    print("=" * 60)
    
    if os.geteuid() == 0:
        print("⚠️  루트 권한으로 실행되고 있습니다.")
    
    # 1. 모든 관련 프로세스 강제 종료
    force_kill_processes()
    
    # 2. 세션 파일 정리
    unlock_and_remove_sessions()
    
    # 3. 파일 권한 확인
    check_file_permissions()
    
    # 4. 세션 격리 디렉토리 생성
    sessions_dir = create_session_isolation()
    
    # 5. 정리 작업 검증
    verify_cleanup()
    
    print("\n" + "=" * 60)
    print("✅ 데이터베이스 잠금 해제 완료!")
    print("=" * 60)
    print("\n다음 단계:")
    print("1. python3 setup_session.py  # 새 세션 생성")
    print("2. python3 monitor.py        # 모니터 실행 테스트")
    print("3. sudo systemctl start telegram-monitor-bot.service  # 서비스 시작")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n중단됨.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        print("수동으로 다음을 실행해보세요:")
        print("sudo pkill -f monitor.py")
        print("sudo systemctl stop telegram-monitor-bot.service")
        print("rm -f *.session* monitor.lock") 