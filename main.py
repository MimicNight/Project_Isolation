"""엔트리 포인트: Game 실행 + AI 서버 자동 실행 (관리자 권한)"""

import os
import time
import socket
import ctypes
import sys

from game import Game 

def is_port_in_use(port: int) -> bool:
    """해당 포트가 이미 사용 중인지 확인 (서버가 이미 켜져 있는지 체크)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_api_server():
    """Windows API를 사용하여 배치 파일을 관리자 권한으로 실행"""
    
    # 1. 배치 파일의 절대 경로 찾기
    # (assets/GPT-SoVITS-v2-240821/Run_TTS_Server.bat로 설정)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bat_path = os.path.join(base_dir, "assets", "GPT-SoVITS-v2-240821", "Run_TTS_Server.bat")

    # 포트 9880 확인 (GPT-SoVITS 기본 포트)
    if is_port_in_use(9880):
        print("[Main] AI 서버가 이미 실행 중입니다.")
        return

    # 배치 파일 존재 확인
    if not os.path.exists(bat_path):
        print(f"[Main] ⚠️ 배치 파일을 찾을 수 없습니다: {bat_path}")
        print("[Main] 경로를 확인하거나 README를 참고하여 파일을 배치해주세요.")
        return

    print(f"[Main] AI TTS 서버를 시작합니다... (관리자 권한 요청)")
    
    try:
        # [핵심] ShellExecuteW를 이용한 관리자 권한 실행 ("runas")
        # 이 함수는 비동기로 실행되므로 게임 로딩을 막지 않습니다.
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            bat_path, 
            None, 
            os.path.dirname(bat_path), # 작업 디렉토리 설정
            1 # SW_SHOWNORMAL (창 보이기)
        )
        
        if ret <= 32:
            print(f"[Main] ⚠️ 서버 실행 실패 (Windows Error Code: {ret})")
        
    except Exception as e:
        print(f"[Main] 실행 중 오류 발생: {e}")

    # 서버 로딩 대기 (최대 60초)
    print("[Main] 서버 로딩 대기 중 (최대 60초)...")
    for i in range(60):
        if is_port_in_use(9880):
            print(f"[Main] ✅ 서버 연결 성공! ({i+1}초 소요)")
            time.sleep(2) # 안정화를 위해 추가 대기
            return
        time.sleep(1)
        if i % 5 == 0:
            print(f"[Main] 서버 기다리는 중... {i+1}초")
    
    print("[Main] ⚠️ 서버 준비 시간 초과. (백그라운드에서 켜지고 있을 수 있습니다)")


if __name__ == "__main__":
    # 1. AI 서버 시작 (관리자 권한 요청 팝업 뜸)
    start_api_server()
    
    # 2. 게임 시작
    game = Game()
    game.run()