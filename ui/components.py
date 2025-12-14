import pygame
import os
from pathlib import Path
from .animator import AnimatedSprite


class UIComponent:
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)


class TextInput(UIComponent):
    def __init__(self, x, y, width, height, font, initial_text=""):
        super().__init__(x, y, width, height)
        self.font = font
        self.text = initial_text
        self.cursor_pos = len(initial_text)
        self.active = False
        self.cursor_timer = 0.0
        self.disabled = False
        
        # [추가] pygame 2.1+ TEXTEDITING 이벤트로 한글 IME 처리
        self.composition_text = ""  # 조합 중인 문자 (TEXTEDITING에서 가져옴)
        self.composition_start = 0  # 조합 시작 위치
        self.composition_length = 0  # 조합 길이

    def set_disabled(self, disabled: bool):
        self.disabled = disabled
        if disabled:
            self.active = False

    def handle_event(self, event):
        if self.disabled:
            return False

        # [마우스 클릭] 입력창 활성화/비활성화
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            if not self.active:
                self.composition_text = ""
                return False

        # [KEY DOWN] 입력창이 활성화되었을 때만 처리
        if event.type == pygame.KEYDOWN:
            if not self.active:
                return False

            if event.key == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos-1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                    self.composition_text = ""
                    return True

            elif event.key == pygame.K_DELETE:
                if self.cursor_pos < len(self.text):
                    self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos+1:]
                    self.composition_text = ""
                    return True

            elif event.key == pygame.K_LEFT:
                self.cursor_pos = max(0, self.cursor_pos - 1)
                self.composition_text = ""
                return True

            elif event.key == pygame.K_RIGHT:
                self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
                self.composition_text = ""
                return True

            elif event.key == pygame.K_HOME:
                self.cursor_pos = 0
                self.composition_text = ""
                return True

            elif event.key == pygame.K_END:
                self.cursor_pos = len(self.text)
                self.composition_text = ""
                return True

            elif event.key == pygame.K_RETURN:
                self.composition_text = ""
                return False

        # [TEXTEDITING] pygame 2.1+ 에서만 지원 - 한글 IME 조합 중인 문자 캡처
        if hasattr(pygame, 'TEXTEDITING') and event.type == pygame.TEXTEDITING:
            if not self.active:
                return False
            
            # TEXTEDITING 이벤트에서 조합 중인 문자와 위치 정보 가져오기
            self.composition_text = event.text  # "ㅇ", "ㅇㅏ", "ㅇㅏㄴ" 등
            self.composition_start = event.start
            self.composition_length = event.length
            # print(f"[IME] 조합 중: '{self.composition_text}' (start: {event.start}, length: {event.length})")
            return True

        # [TEXTINPUT] 완성된 문자 추가
        # [중요] event.text == '\x00' 제외, 그 외는 모두 추가 (스페이스 포함!)
        if event.type == pygame.TEXTINPUT:
            if not self.active:
                return False

            # ✅ '\x00' 만 무시하고 스페이스바는 통과시킴!
            if event.text == '\x00':
                return False

            # 완성된 문자 추가 (스페이스 " " 포함!)
            self.text = self.text[:self.cursor_pos] + event.text + self.text[self.cursor_pos:]
            self.cursor_pos += len(event.text)
            self.composition_text = ""  # 완성되면 조합 초기화
            print(f"[TextInput] 입력됨: '{event.text}' → 전체: '{self.text}'")
            return True

        return False

    def update(self, dt):
        self.cursor_timer += dt

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.text = text
        self.cursor_pos = len(text)
        self.composition_text = ""

    def draw(self, screen):
        # 입력창 배경 (반투명)
        s = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 100))
        screen.blit(s, (self.rect.x, self.rect.y))

        # 테두리
        # pygame.draw.rect(screen, (255, 255, 255), self.rect, 2)

        txt_color = (255, 255, 255) if not self.disabled else (150, 150, 150)

        # [핵심] 표시할 텍스트 = 기본 텍스트 + TEXTEDITING에서 가져온 조합 중인 문자
        display_text = self.text + self.composition_text

        # 그림자
        shadow_surf = self.font.render(display_text, True, (0, 0, 0))
        # [수정] 텍스트 좌측 패딩 추가 (8px)
        text_y = self.rect.y + (self.rect.height - shadow_surf.get_height()) // 2
        text_x = self.rect.x + 8  # ← 좌측 여백 추가
        screen.blit(shadow_surf, (text_x + 2, text_y + 2))

        # 본문
        txt_surf = self.font.render(display_text, True, txt_color)
        screen.blit(txt_surf, (text_x, text_y))

        # 커서 (활성화되었을 때만)
        if self.active and not self.disabled and int(self.cursor_timer * 2) % 2 == 0:
            prefix = self.text[:self.cursor_pos]
            try:
                prefix_w = self.font.size(prefix)[0]
            except:
                prefix_w = 0

            # [수정] 커서도 좌측 패딩 반영
            cursor_x = text_x + prefix_w
            pygame.draw.line(screen, (255, 255, 255),
                           (cursor_x, text_y),
                           (cursor_x, text_y + txt_surf.get_height()), 2)

class DialogueBox(UIComponent):

    def __init__(self, x, y, width, height, font):
        super().__init__(x, y, width, height)
        self.font = font
        self.full_text = ""
        self.display_lines = []
        self.char_index = 0
        self.timer = 0.0
        self.speed = 0.05
        self.finished = True
        self.line_height = self.font.get_height() + 2
        
        # [추가] 행동 구분 마커 위치 저장
        self.action_end_pos = None  # 첫 번째 ) 위치
        self.dialogue_start_pos = None  # 대사 시작 위치
        
        # [추가] 콜백 함수
        self.on_action_finished = None  # action_pre 출력 완료 시
        self.on_dialogue_start = None    # 대사 출력 시작 시
        self._action_callback_fired = False
        self._dialogue_callback_fired = False

    def set_text(self, text):
        """텍스트 설정 및 구조 파싱"""
        self.full_text = text
        self.char_index = 0
        self.timer = 0.0
        self.finished = False
        self.display_lines = []
        self._action_callback_fired = False
        self._dialogue_callback_fired = False
        
        # [추가] 행동-대사 구분 위치 파악
        # 형식: "(action_pre)\ndialogue\n(action_post)"
        self.action_end_pos = None
        self.dialogue_start_pos = None
        
        # 첫 번째 닫는 괄호 찾기
        close_paren_idx = text.find(')')
        if close_paren_idx != -1:
            self.action_end_pos = close_paren_idx + 1
            # 다음 '\n' 찾기
            next_newline = text.find('\n', close_paren_idx)
            if next_newline != -1:
                self.dialogue_start_pos = next_newline + 1
            else:
                self.dialogue_start_pos = close_paren_idx + 1

    def _wrap_text(self, text):
        lines = []
        current_line = ""
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ""
                continue
            test_line = current_line + char
            if self.font.size(test_line)[0] < self.rect.width - 40:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = char
        if current_line: 
            lines.append(current_line)
        return lines

    def update(self, dt):
        """매 프레임 업데이트 - 문자 단위 출력 및 콜백 발생"""
        if not self.finished:
            self.timer += dt
            if self.timer >= self.speed:
                self.timer = 0
                
                if self.char_index < len(self.full_text):
                    # [추가] 행동 출력 완료 감지
                    if (not self._action_callback_fired and 
                        self.action_end_pos and 
                        self.char_index >= self.action_end_pos):
                        self._action_callback_fired = True
                        if self.on_action_finished:
                            self.on_action_finished()
                            print("[DialogueBox] 행동(action_pre) 출력 완료, TTS 시작!")
                    
                    # [추가] 대사 출력 시작 감지
                    if (not self._dialogue_callback_fired and 
                        self.dialogue_start_pos and 
                        self.char_index >= self.dialogue_start_pos):
                        self._dialogue_callback_fired = True
                        if self.on_dialogue_start:
                            self.on_dialogue_start()
                    
                    self.char_index += 1
                    current_vis = self.full_text[:self.char_index]
                    self.display_lines = self._wrap_text(current_vis)
                else:
                    self.finished = True

    def skip(self):
        self.char_index = len(self.full_text)
        self.display_lines = self._wrap_text(self.full_text)
        self.finished = True
        # 콜백도 발생
        if self.action_end_pos and not self._action_callback_fired:
            self._action_callback_fired = True
            if self.on_action_finished:
                self.on_action_finished()
        if self.dialogue_start_pos and not self._dialogue_callback_fired:
            self._dialogue_callback_fired = True
            if self.on_dialogue_start:
                self.on_dialogue_start()

    def draw(self, screen):
        if not self.display_lines: 
            return
        start_x = self.rect.x + 20
        start_y = self.rect.y + 20
        for i, line in enumerate(self.display_lines):
            shadow = self.font.render(line, True, (0, 0, 0))
            screen.blit(shadow, (start_x + 2, start_y + (i * self.line_height) + 2))
            text = self.font.render(line, True, (240, 240, 240))
            screen.blit(text, (start_x, start_y + (i * self.line_height)))


class AnimatedPortrait(UIComponent):
    """
    JSON에서 직접 지정한 크기(Width, Height)로만 이미지를 로드합니다.
    """

    def __init__(self, x, y, config):
        super().__init__(x, y, 100, 100)
        self.base_x = x
        self.base_y = y
        self.config = config
        self.anims = {}
        self.current_key = config.get("default_state", "neutral")

        self._load_all_animations()

        if self.current_key in self.anims:
            self.current_anim = self.anims[self.current_key]
        else:
            self.current_anim = None
            print(f"[Error] 기본 상태 '{self.current_key}' 이미지를 찾을 수 없습니다.")

        self._update_rect()

    def _load_all_animations(self):
        base_path = self.config.get("base_path", "assets/characters/yuhwa")
        states = self.config.get("animation_states", {})

        print(f"\n[Portrait] JSON 기반 이미지 로드 시작")

        for state_name, settings in states.items():
            if not isinstance(settings, dict):
                continue

            w = settings.get("width")
            h = settings.get("height")

            if not w or not h:
                print(f" [Warning] {state_name}: 크기 설정(width, height)이 없습니다. (기본값 적용)")
                w, h = 400, 600

            target_size = (w, h)
            off_x = settings.get("x_offset", 0)
            off_y = settings.get("y_offset", 0)

            try:
                full_path = f"{base_path}/{state_name}"

                if not os.path.exists(full_path) and state_name == "thinking_loop":
                    print(f" [Warning] thinking_loop 폴더 없음: {full_path}")
                    continue

                sprite = AnimatedSprite(
                    full_path,
                    loop=settings.get("loop", True),
                    scale_to=target_size
                )

                self.anims[state_name] = {
                    "sprite": sprite,
                    "offset": (off_x, off_y)
                }

                print(f" - {state_name}: {target_size} 로드 완료")

            except Exception as e:
                print(f" [Fail] {state_name} 로드 실패: {e}")

    def set_state(self, key):
        if key == self.current_key:
            return

        if key in self.anims:
            self.current_key = key
            self.current_anim = self.anims[key]
            self.current_anim["sprite"].reset()
            self._update_rect()
        else:
            if key == "thinking_loop":
                print(f"[Warning] thinking_loop 없음.")
            elif self.config.get("default_state") in self.anims:
                self.set_state(self.config.get("default_state"))

    def get_state(self):
        return self.current_key

    def is_finished(self):
        if self.current_anim:
            return self.current_anim["sprite"].is_finished
        return True

    def _update_rect(self):
        if self.current_anim:
            off_x, off_y = self.current_anim["offset"]
            self.rect.x = self.base_x + off_x
            self.rect.y = self.base_y + off_y

    def update(self, dt):
        if self.current_anim:
            self.current_anim["sprite"].update(dt)

    def draw(self, screen):
        if self.current_anim:
            self.current_anim["sprite"].draw(screen, (self.rect.x, self.rect.y))