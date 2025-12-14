import pygame
import sys
import os

# 초기 상태만 임포트 (나머지는 LoadingState에서 로드)
from states.loading_state import LoadingState

class Game:
    """
    게임의 메인 클래스.
    초기화 로직을 최소화하여 즉시 LoadingState를 띄웁니다.
    """
    
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1000, 600))
        pygame.display.set_caption("LLM Game Prototype - Virtual Yuhwa")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # 설정값 정의
        # self.current_model_name = "deepseek-v3.1:671b-cloud"
        self.current_model_name = "gemini-3-pro-preview"
        # self.summary_model_name = "exaone3.5:7.8b"
        self.summary_model_name = "deepseek-v3.1:671b-cloud"
        
        # --- [중요] 매니저 슬롯만 생성 (내용은 LoadingState가 채움) ---
        self.llm_manager = None
        self.character = None
        self.rag_manager = None
        self.game_system = None
        self.audio_manager = None
        self.stt_manager = None
        self.sound_manager = None
        
        # pygame_gui UIManager 등 UI 관련은 필요하다면 여기서, 
        # 혹은 GameplayState 내부에서 생성해도 무방함.
        # 여기서는 최소한으로 둠.

        # 첫 상태를 로딩 화면으로 설정
        self.current_state = LoadingState(self)
    
    def run(self):
        while self.running:
            time_delta = self.clock.tick(60) / 1000.0
            events = pygame.event.get()
            
            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                
                self.current_state.handle_events(event)
            
            self.current_state.update(time_delta)
            self.current_state.draw(self.screen)
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()
    
    def change_state(self, new_state):
        self.current_state = new_state