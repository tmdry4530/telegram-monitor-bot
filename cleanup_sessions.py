#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
세션 파일 정리 및 데이터베이스 잠금 해제 스크립트
- 모든 .session 파일 삭제
- 잠긴 데이터베이스 파일 해제
- 안전한 재시작을 위한 정리 작업
"""

import os
import sys
import glob
import sqlite3
import subprocess

def kill_related_processes():
    """
    텔레그램 모니터 관련 프로세스 종료
    """
    try:
        # monitor.py 프로세스 찾기 및 종료
        result = subprocess.run(['pgrep', '-f', 'monitor.py'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"프로세스 종료 중: PID {pid}")
                    subprocess.run(['kill', '-9', pid])
        
        # python 프로세스 중 telegram 관련 종료
        result = subprocess.run(['pgrep', '-f', 'telegram'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    print(f"텔레그램 관련 프로세스 종료 중: PID {pid}")
                    subprocess.run(['kill', '-9', pid])
                    
    except Exception as e:
        print(f"프로세스 종료 중 오류: {e}")

def cleanup_session_files():
    """
    세션 파일들 정리
    """
    # .session 파일들 찾기
    session_files = glob.glob("*.session")
    
    if not session_files:
        print("삭제할 세션 파일이 없습니다.")
        return
    
    print(f"발견된 세션 파일들: {session_files}")
    
    for session_file in session_files:
        try:
            # 세션 파일이 SQLite 데이터베이스인지 확인
            if os.path.exists(session_file):
                try:
                    # 데이터베이스 연결 테스트
                    conn = sqlite3.connect(session_file, timeout=1)
                    conn.close()
                    print(f"세션 파일 정상: {session_file}")
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        print(f"잠긴 세션 파일 감지: {session_file}")
                        # 강제로 파일 삭제
                        os.remove(session_file)
                        print(f"잠긴 세션 파일 삭제됨: {session_file}")
                    else:
                        print(f"세션 파일 오류: {session_file} - {e}")
                        
        except Exception as e:
            print(f"세션 파일 처리 중 오류: {session_file} - {e}")

def cleanup_journal_files():
    """
    SQLite 저널 파일들 정리
    """
    journal_files = glob.glob("*.session-wal") + glob.glob("*.session-shm")
    
    for journal_file in journal_files:
        try:
            os.remove(journal_file)
            print(f"저널 파일 삭제됨: {journal_file}")
        except Exception as e:
            print(f"저널 파일 삭제 오류: {journal_file} - {e}")

def main():
    print("=== 텔레그램 세션 정리 스크립트 ===")
    print()
    
    # 1. 관련 프로세스 종료
    print("1. 관련 프로세스 종료 중...")
    kill_related_processes()
    print()
    
    # 2. 세션 파일 정리
    print("2. 세션 파일 정리 중...")
    cleanup_session_files()
    print()
    
    # 3. 저널 파일 정리
    print("3. SQLite 저널 파일 정리 중...")
    cleanup_journal_files()
    print()
    
    print("=== 정리 완료 ===")
    print("이제 setup_session.py를 실행하여 새 세션을 생성하세요.")

if __name__ == "__main__":
    if os.name == 'nt':  # Windows
        print("이 스크립트는 Linux/Unix 환경용입니다.")
        print("Windows에서는 작업 관리자에서 python.exe 프로세스를 수동으로 종료하고")
        print("*.session 파일들을 삭제하세요.")
        sys.exit(1)
    
    main() 