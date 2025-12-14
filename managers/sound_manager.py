import pygame
import random
import os
from typing import Dict, Any

class SoundManager:
    def __init__(self, config: Dict[str, Any]):
        print("\n" + "="*30)
        print("[SoundManager] 초기화 시작")
        
        # 1. 설정 로드
        self.config = config.get("sound", {})
        self.bgm_enabled = self.config.get("bgm_enabled", True)
        self.bgm_volume = self.config.get("bgm_volume", 0.5)
        self.bgm_tracks = self.config.get("bgm_tracks", {})
        
        self.sfx_enabled = self.config.get("sfx_enabled", True)
        self.sfx_paths = self.config.get("sfx_paths", {})
        
        print(f"[SoundManager] 설정 로드됨: BGM={self.bgm_enabled}, SFX={self.sfx_enabled}")
        print(f"[SoundManager] 현재 작업 경로(CWD): {os.getcwd()}")

        # 2. Pygame Mixer 초기화
        if not pygame.mixer.get_init():
            try:
                # 주파수 44100, 16비트, 2채널, 버퍼 2048 (일반적인 설정)
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                print("[SoundManager] ✅ Pygame Mixer 초기화 성공")
            except Exception as e:
                print(f"[SoundManager] ❌ Mixer 초기화 실패: {e}")
        else:
            print("[SoundManager] Mixer 이미 초기화됨")

        # 3. SFX 미리 로드
        self.loaded_sfx = {}
        self._preload_sfx()

        # 4. 시스템 변수
        self.current_san = 100
        self.current_bgm = None
        self.tap_timer = 0.0
        self.next_tap_interval = 999.0 
        self.is_stt_recording = False 
        
        print("[SoundManager] 초기화 완료")
        print("="*30 + "\n")

    def _preload_sfx(self):
        """효과음 메모리 로드 (디버깅용)"""
        if not self.sfx_enabled: 
            print("[SoundManager] SFX 비활성화됨")
            return
        
        print("[SoundManager] SFX 파일 로딩 시작...")
        for key, path in self.sfx_paths.items():
            # 절대 경로로 변환하여 확인
            abs_path = os.path.abspath(path)
            if os.path.exists(path):
                try:
                    sound = pygame.mixer.Sound(path)
                    if "tap" in key:
                        sound.set_volume(0.6) 
                    else:
                        sound.set_volume(0.8)
                    self.loaded_sfx[key] = sound
                    print(f"  [OK] SFX 로드 성공: {key} -> {path}")
                except Exception as e:
                    print(f"  [Error] SFX 파일 깨짐/형식 오류 ({key}): {e}")
            else:
                print(f"  [Missing] ❌ 파일 없음 ({key}): {path}")
                print(f"    -> 절대 경로 확인: {abs_path}")

    # --- 배경음(Ambience) 제어 ---

    def play_ambience(self, track_name: str) -> None:
        """배경음 재생"""
        print(f"[SoundManager] play_ambience 호출됨: {track_name}")
        
        # 호환성: "gameplay"가 들어오면 "quiet"로 강제 변환
        if track_name == "gameplay":
            print("[SoundManager] 'gameplay' 요청 감지 -> 'quiet'로 리다이렉트")
            track_name = "quiet"

        if not self.bgm_enabled:
            print("[SoundManager] BGM 설정이 꺼져 있음")
            return

        if track_name not in self.bgm_tracks:
            print(f"[SoundManager] ❌ 등록되지 않은 트랙 키: {track_name}")
            print(f"  -> 가능한 키: {list(self.bgm_tracks.keys())}")
            return

        path = self.bgm_tracks[track_name]
        abs_path = os.path.abspath(path)
        
        if not os.path.exists(path):
            print(f"[SoundManager] ❌ BGM 파일 없음: {path}")
            print(f"    -> 절대 경로 확인: {abs_path}")
            return

        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.bgm_volume)
            pygame.mixer.music.play(-1, fade_ms=2000)
            self.current_bgm = track_name
            print(f"[SoundManager] 🔊 재생 시작 성공: {path}")
        except Exception as e:
            print(f"[SoundManager] ❌ 재생 중 Pygame 오류: {e}")

    # 호환성 유지용
    def play_bgm(self, track_name: str):
        self.play_ambience(track_name)

    # --- SFX 및 탭핑 제어 ---

    def play_click(self):
        """UI 클릭음"""
        print("[SoundManager] play_click 호출")
        if "click" in self.loaded_sfx:
            self.loaded_sfx["click"].play()
        else:
            print("[SoundManager] 'click' 사운드가 로드되지 않음")

    def update_san(self, san_value: int) -> None:
        self.current_san = san_value
        # 로그가 너무 많으면 이 줄은 주석 처리
        # print(f"[SoundManager] SAN 업데이트: {san_value}")
        
        target_bgm = ""
        if self.current_san > 70: target_bgm = "hum"
        elif self.current_san > 0: target_bgm = "quiet"
        else: target_bgm = "glitch"
            
        if target_bgm and target_bgm != self.current_bgm:
            print(f"[SoundManager] SAN 변화로 인한 BGM 교체: {self.current_bgm} -> {target_bgm}")
            self.play_ambience(target_bgm)

    def update(self, dt: float) -> None:
        if self.is_stt_recording or not self.sfx_enabled: return

        # --- [수정된 탭핑 로직] ---
        
        # 1. SAN 71 ~ 100 (평온 상태)
        # 기존: self.next_tap_interval = 999.0 (아예 안 함)
        # 수정: 15초 ~ 30초 간격으로 가끔 두드림
        if self.current_san > 70:
             if self.next_tap_interval == 999.0: 
                 self.next_tap_interval = random.uniform(15.0, 30.0) 

        # 2. SAN 31 ~ 70 (불안)
        elif self.current_san > 30:
            if self.next_tap_interval == 999.0: 
                self.next_tap_interval = random.uniform(4.0, 8.0)

        # 3. SAN 1 ~ 30 (공포)
        elif self.current_san > 0:
            if self.next_tap_interval == 999.0: 
                self.next_tap_interval = random.uniform(1.0, 3.0)

        # 4. SAN 0 (광기)
        else:
            if self.next_tap_interval == 999.0: 
                self.next_tap_interval = random.uniform(0.1, 0.6)

        # 타이머 체크 및 실행 (이 부분은 기존과 동일)
        if self.next_tap_interval != 999.0:
            self.tap_timer += dt
            if self.tap_timer >= self.next_tap_interval:
                self._trigger_tap()
                self.tap_timer = 0.0
                self.next_tap_interval = 999.0

    def _trigger_tap(self):
        play_hard = False
        if self.current_san <= 30:
            chance = 0.5 if self.current_san <= 0 else 0.2
            if random.random() < chance: play_hard = True
        
        sound_key = "tap_hard" if play_hard else "tap_soft"
        if sound_key in self.loaded_sfx:
            # print(f"[SoundManager] 탭핑 발생: {sound_key}") # 너무 시끄러우면 주석
            sound = self.loaded_sfx[sound_key]
            vol = random.uniform(0.5, 0.8) 
            sound.set_volume(vol)
            sound.play()

    def pause_for_stt(self):
        self.is_stt_recording = True
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            print("[SoundManager] STT로 인한 일시정지")

    def resume_after_stt(self):
        self.is_stt_recording = False
        if not pygame.mixer.music.get_busy(): 
            pygame.mixer.music.unpause()
            print("[SoundManager] STT 종료 후 재개")