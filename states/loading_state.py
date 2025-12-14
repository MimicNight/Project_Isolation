import pygame
import threading
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from ui.state_base import GameState
from game_systems import GameSystemManager
from managers.llm_manager import LLMManager

class LoadingState(GameState):
    """
    초기 로딩 화면
    1. [캐시] 외장 하드 감지 -> 허깅페이스/토치 캐시 경로 설정 (용량 확보)
    2. [자산] 프로젝트 내부 assets 폴더에서 모델 및 DB 로드
    3. 완료 후 GameplayState 전환
    """

    def __init__(self, game):
        super().__init__(game)
        # 폰트 초기화
        try:
            self.font = pygame.font.Font("assets/Silver.ttf", 28)
            self.small_font = pygame.font.Font("assets/Silver.ttf", 20)
        except:
            self.font = pygame.font.SysFont("malgungothic", 24)
            self.small_font = pygame.font.SysFont("malgungothic", 16)

        self.current_task = "시스템 초기화 시작..."
        self.progress = 0.0
        self.is_done = False

        self.dots = 0
        self.timer = 0

        self.thread = threading.Thread(target=self._load_all_assets)
        self.thread.daemon = True
        self.thread.start()

    def _find_external_drive(self):
        """캐시 저장용 외장 하드 찾기 (모델 로딩용 아님)"""
        external_drives = ["D:\\", "E:\\", "F:\\", "G:\\"]
        for drive in external_drives:
            if os.path.exists(drive):
                try:
                    # 쓰기 테스트
                    test_file = os.path.join(drive, "test_write.tmp")
                    with open(test_file, 'w') as f:
                        f.write("test")
                    os.remove(test_file)
                    return drive
                except:
                    continue
        return None

    def _load_animation_frames(self, folder_path: str, scale_to: Optional[tuple] = None) -> List[pygame.Surface]:
        frames = []
        try:
            image_files = sorted([
                f for f in os.listdir(folder_path)
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
            ])

            for img_file in image_files:
                full_path = os.path.join(folder_path, img_file)
                surface = pygame.image.load(full_path)
                if scale_to:
                    surface = pygame.transform.scale(surface, scale_to)
                try:
                    surface = surface.convert_alpha()
                except pygame.error:
                    pass
                frames.append(surface)
            return frames
        except Exception:
            return []

    def _recursive_load_sounds(self, config_dict: Dict, target_dict: Dict) -> int:
        count = 0
        for key, value in config_dict.items():
            if isinstance(value, str):
                if os.path.exists(value) and value.lower().endswith(('.wav', '.mp3', '.ogg')):
                    if "bgm_" in os.path.basename(value).lower():
                        continue
                    try:
                        if key not in target_dict:
                            sound = pygame.mixer.Sound(value)
                            if "tap" in key:
                                sound.set_volume(0.6)
                            target_dict[key] = sound
                            count += 1
                            print(f"[Loading] SFX 프리로드: {key}")
                    except Exception as e:
                        print(f"[Loading] ❌ 사운드 파일 오류 ({key}): {e}")
            elif isinstance(value, dict):
                count += self._recursive_load_sounds(value, target_dict)
        return count

    def _load_all_assets(self):
        """백그라운드 로딩 로직"""
        try:
            # --- [Step 1] 캐시 경로 설정 (외장하드 우선) ---
            self.current_task = "캐시 스토리지 설정 중..."
            self.progress = 0.1

            drive = self._find_external_drive()
            
            # 드라이브가 있으면 거기다가 캐시 폴더 생성, 없으면 사용자 홈 폴더 사용
            if drive:
                cache_base = os.path.join(drive, "LLM_cache")
                print(f"[Loading] 외장 하드 감지됨 ({drive}). 캐시를 이곳에 저장합니다.")
            else:
                cache_base = os.path.join(os.path.expanduser("~"), ".cache", "LLM_game_cache")
                print("[Loading] 외장 하드 없음. 기본 캐시 경로를 사용합니다.")

            # 환경 변수 설정 (라이브러리들이 이 경로를 참조함)
            os.environ["HF_HOME"] = os.path.join(cache_base, "huggingface_cache")
            os.environ["TRANSFORMERS_CACHE"] = os.path.join(cache_base, "huggingface_cache", "transformers")
            os.environ["TORCH_HOME"] = os.path.join(cache_base, "torch_cache")
            os.environ["SDL_IME_SHOW_UI"] = "1"

            # --- [Step 2] 설정 파일 로드 ---
            self.current_task = "설정 파일(Config) 로드 중..."
            self.progress = 0.2

            with open("config/media.json", "r", encoding="utf-8") as f:
                media_config = json.load(f)

            # --- [Step 3] 매니저 초기화 및 사운드 로드 ---
            self.current_task = "사운드 리소스 연결 중..."
            self.progress = 0.3

            llm_provider = os.getenv("LLM_PROVIDER", "gemini-3-pro")
            self.game.llm_manager = LLMManager(provider=llm_provider)
            self.game.game_system = GameSystemManager()

            from managers.sound_manager import SoundManager
            self.game.sound_manager = SoundManager(media_config)

            if not hasattr(self.game.sound_manager, 'loaded_sfx'):
                self.game.sound_manager.loaded_sfx = {}
            
            sound_config = media_config.get("sound", {})
            sfx_count = self._recursive_load_sounds(sound_config, self.game.sound_manager.loaded_sfx)
            print(f"[Loading] 추가 SFX {sfx_count}개 캐싱 완료")

            # --- [Step 4] STT ---
            self.current_task = "음성 인식(Whisper) 준비 중..."
            self.progress = 0.4
            from managers.stt_manager import SttManager
            self.game.stt_manager = SttManager(media_config.get("stt", {}))

            # --- [Step 5] TTS ---
            self.current_task = "음성 합성(TTS) 연결 중..."
            self.progress = 0.5
            from managers.audio_manager import AudioManager
            self.game.audio_manager = AudioManager(media_config.get("tts", {}))

            # --- [Step 6] RAG (수정됨: 프로젝트 내부 assets 경로 사용) ---
            self.current_task = "지식 베이스(RAG) 로드 중..."
            self.progress = 0.7
            
            rag_manager = None
            
            # [수정] 프로젝트 루트 기준 상대 경로 설정
            # 구조: assets/models/embedding/KURE... , assets/database/vectordb
            base_path = os.path.dirname(os.path.abspath(__file__)) # states 폴더
            project_root = os.path.dirname(base_path)              # 프로젝트 루트
            
            # 실제 모델 및 DB 경로
            model_path = os.path.join(project_root, "assets", "models", "embedding", "KURE-v1-yuhwa-final")
            vectordb_path = os.path.join(project_root, "assets", "database", "vectordb")

            print(f"[Loading] RAG 경로 확인: {model_path}")

            if os.path.exists(model_path) and os.path.exists(vectordb_path):
                try:
                    from managers.rag_manager import RAGManager
                    # 절대 경로로 변환하여 전달 (안전성 확보)
                    rag_manager = RAGManager(
                        os.path.abspath(model_path), 
                        os.path.abspath(vectordb_path)
                    )
                    print("[Loading] RAG 시스템 로드 성공")
                except Exception as e:
                    print(f"[Loading] ❌ RAG 초기화 실패: {e}")
            else:
                print(f"[Loading] ⚠️ RAG 파일을 찾을 수 없습니다. (경로: {model_path})")
                # 파일이 없어도 게임은 켜져야 하므로 rag_manager는 None 유지

            self.game.rag_manager = rag_manager

            # --- [Step 7] 캐릭터 ---
            self.current_task = "캐릭터 데이터 생성 중..."
            self.progress = 0.9
            from character import Character
            self.game.character = Character(
                name="유화",
                model_name=self.game.current_model_name,
                rag_manager=rag_manager
            )

            # --- [Step 8] 애니메이션 ---
            self.current_task = "그래픽 리소스 프리로드 중..."
            self.progress = 0.95
            
            if not hasattr(self.game, 'animation_cache'):
                self.game.animation_cache = {}

            # 애니메이션 경로도 assets 기준으로 명확히
            anim_paths = [
                os.path.join(project_root, "assets", "characters", "yuhwa"),
                os.path.join(project_root, "assets", "backgrounds"),
            ]
            
            for base in anim_paths:
                if os.path.exists(base):
                    for sub in os.listdir(base):
                        path = os.path.join(base, sub)
                        if os.path.isdir(path):
                            frames = self._load_animation_frames(path)
                            if frames:
                                self.game.animation_cache[sub] = frames

            # 완료
            self.current_task = "준비 완료!"
            self.progress = 1.0
            time.sleep(0.5)
            self.is_done = True

        except Exception as e:
            print(f"[Fatal Error] 로딩 중 오류: {e}")
            import traceback
            traceback.print_exc()
            self.current_task = "초기화 오류 발생"

    def handle_events(self, event):
        pass

    def update(self, dt):
        if self.is_done:
            from states.gameplay_state import GameplayState
            self.game.change_state(GameplayState(self.game))
            return

        self.timer += dt
        if self.timer > 0.5:
            self.dots = (self.dots + 1) % 4
            self.timer = 0

    def draw(self, screen):
        screen.fill((20, 20, 20))
        
        # 텍스트
        text_content = f"{self.current_task}" + ("." * self.dots)
        text_surf = self.font.render(text_content, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=(500, 250))
        screen.blit(text_surf, text_rect)

        # 바
        bar_x, bar_y, bar_w, bar_h = 200, 300, 600, 10
        pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(screen, (100, 200, 255), (bar_x, bar_y, int(bar_w * self.progress), bar_h))

        # 팁
        tip_surf = self.small_font.render("TIP: 책상 위 스탠드를 눌러보세요.", True, (150, 150, 150))
        screen.blit(tip_surf, tip_surf.get_rect(center=(500, 550)))