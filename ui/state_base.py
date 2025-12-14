"""게임 상태 기본 클래스 (MIT License)"""

from abc import ABC, abstractmethod
import pygame


class GameState(ABC):
    """모든 게임 상태의 기본 클래스"""

    def __init__(self, game):
        """
        Args:
            game: 게임 매니저 인스턴스
        """
        self.game = game

    @abstractmethod
    def handle_events(self, event: pygame.event.Event) -> None:
        """이벤트 처리"""
        pass

    @abstractmethod
    def update(self, dt: float) -> None:
        """상태 업데이트 (dt: 델타 타임)"""
        pass

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """화면에 그리기"""
        pass

    def on_enter(self) -> None:
        """상태 진입 시 호출"""
        pass

    def on_exit(self) -> None:
        """상태 종료 시 호출"""
        pass