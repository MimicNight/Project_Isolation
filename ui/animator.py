import pygame
import os
import threading  # 스레딩 모듈 추가
from pathlib import Path
from typing import List, Optional

class AnimatedSprite:
    """
    폴더 내의 PNG 시퀀스를 로드하여 애니메이션 재생
    - 캐시된 프레임이 있으면 즉시 사용
    - 캐시가 없으면 동기로 로드 (게임 중 새로운 애니메이션용)
    """

    def __init__(
        self,
        folder_path: str,
        frame_duration: float = 0.1,
        loop: bool = True,
        scale_to: Optional[tuple] = None,
        preloaded_frames: Optional[List[pygame.Surface]] = None
    ):
        self.frames: List[pygame.Surface] = []
        self.current_frame_index = 0
        self.timer = 0.0
        self.frame_duration = frame_duration
        self.loop = loop
        self.is_playing = True
        self.is_finished = False
        self.is_loaded = False
        self.image: Optional[pygame.Surface] = None

        # 더미 이미지
        dummy_size = scale_to if scale_to else (100, 100)
        self.dummy_image = pygame.Surface(dummy_size, pygame.SRCALPHA)
        self.image = self.dummy_image

        # ✨ 캐시된 프레임이 있으면 즉시 사용
        if preloaded_frames is not None:
            self._set_frames(preloaded_frames)
        else:
            # 캐시 없음 → 동기로 로드 (게임 중 새로운 애니메이션용)
            frames = self._load_frames_sync(folder_path, scale_to)
            self._set_frames(frames)

    def _set_frames(self, frames: List[pygame.Surface]):
        """프레임 설정"""
        self.frames = frames
        self.is_loaded = True
        if self.frames:
            self.image = self.frames[0]

    def _load_frames_sync(self, folder_path: str, scale_to: Optional[tuple]) -> List[pygame.Surface]:
        """동기로 프레임 로드"""
        frames = []
        path = Path(folder_path)
        
        if not path.exists():
            print(f"[Animator] ⚠️ 경로 없음: {folder_path}")
            return frames

        try:
            image_files = sorted([
                f for f in os.listdir(folder_path)
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
            ])

            for img_file in image_files:
                full_path = os.path.join(folder_path, img_file)
                try:
                    surface = pygame.image.load(full_path)
                    if scale_to:
                        surface = pygame.transform.scale(surface, scale_to)
                    try:
                        surface = surface.convert_alpha()
                    except pygame.error:
                        pass
                    frames.append(surface)
                except Exception as e:
                    print(f"[Animator] 프레임 로드 실패 ({img_file}): {e}")

            if frames:
                print(f"[Animator] ✅ 프레임 로드 완료: {folder_path} ({len(frames)} frames)")
            
            return frames

        except Exception as e:
            print(f"[Animator] 로드 오류: {e}")
            return frames

    def reset(self):
        """처음으로 되감기"""
        self.current_frame_index = 0
        self.timer = 0.0
        self.is_finished = False
        self.is_playing = True
        if self.is_loaded and self.frames:
            self.image = self.frames[0]

    def update(self, dt: float):
        """프레임 업데이트"""
        if not self.is_loaded or not self.frames or not self.is_playing:
            return

        self.timer += dt
        if self.timer >= self.frame_duration:
            self.timer -= self.frame_duration
            next_index = self.current_frame_index + 1

            if next_index >= len(self.frames):
                if self.loop:
                    self.current_frame_index = 0
                else:
                    self.is_finished = True
                    self.is_playing = False
                    self.current_frame_index = len(self.frames) - 1
            else:
                self.current_frame_index = next_index

            self.image = self.frames[self.current_frame_index]

    def draw(self, surface: pygame.Surface, pos: tuple):
        """화면에 그리기"""
        if self.image:
            surface.blit(self.image, pos)
