import pygame
import json
import re
import threading
import time
from pathlib import Path
from ui.state_base import GameState
from ui.components import TextInput, AnimatedPortrait, DialogueBox
from ui.animator import AnimatedSprite
from ui.theme_manager import get_theme


class GameplayState(GameState):
    def __init__(self, game):
        super().__init__(game)
        self.llm_manager = game.llm_manager
        self.character = game.character
        self.game_system = game.game_system
        self.audio_manager = game.audio_manager
        self.stt_manager = game.stt_manager
        self.rag_manager = game.rag_manager
        self.sound_manager = game.sound_manager
        self.media_config = self._load_media_config()
        self.theme = get_theme()

        print("=" * 60)
        print("[Gameplay] 게임 시작")
        print("=" * 60)

        # 폰트 초기화
        self._init_fonts()

        # 배경
        bg_path = self.media_config.get("paths", {}).get("background_anim", "assets/backgrounds/room_noise")
        self.bg_anim = AnimatedSprite(bg_path, frame_duration=0.1, loop=True, scale_to=(1000, 600))

        # 캐릭터
        char_conf = self.media_config.get("character", {})
        char_x = char_conf.get("x", 250)
        char_y = char_conf.get("y", 50)
        self.char_portrait = AnimatedPortrait(char_x, char_y, char_conf)

        # 상태 변수
        self.next_emotion = "neutral"
        self.last_emotion = "평온"
        self.last_topic = "새로운 관리자를 기다리는 중"
        self.is_pipeline_running = False
        self.is_recording = False
        self.is_processing_tts = False
        self.current_user_msg = ""
        self.thinking_trigger = False  # 디버깅용 트리거
        
        # [수정] TTS 관련 상태 변수
        self._tts_audio_path = None  # TTS 합성 결과 저장
        self._tts_ready = False  # TTS 합성 완료 플래그
        self._pending_llm_data = None  # LLM 응답 임시 저장 (TTS 완료 대기 중)
        self._llm_response_processed = False

        self._load_objects()
        self._init_ui_components()

        if self.sound_manager:
            self.sound_manager.play_ambience("hum")

        self.emotion_map = {
            "평온": "neutral", "기쁨": "smile", "흥미": "smile", "만족": "smile",
            "분노": "angry", "짜증": "angry", "혐오": "angry", "경계": "angry",
            "슬픔": "sad", "우울": "sad", "불안": "scared", "공포": "scared",
            "당혹": "scared", "애착": "smile", "탐닉": "smile"
        }

    # ========== 초기화 메서드 ==========

    def _load_media_config(self):
        try:
            with open("config/media.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _load_font_from_path(self, path, size):
        try:
            if path and Path(path).exists():
                return pygame.font.Font(path, size)
        except:
            pass
        return pygame.font.SysFont("malgungothic", size)

    def _init_fonts(self):
        ui_settings = self.media_config.get("ui_settings", {})
        diag_conf = ui_settings.get("dialogue_box", {})
        input_conf = ui_settings.get("input_box", {})

        self.dialogue_font = self._load_font_from_path(
            diag_conf.get("font_path", "assets/D2Coding-Ver1.3.2-20180524.ttc"),
            diag_conf.get("font_size", 22)
        )

        self.input_font = self._load_font_from_path(
            input_conf.get("font_path", "assets/D2Coding-Ver1.3.2-20180524.ttc"),
            input_conf.get("font_size", 20)
        )

    def _init_ui_components(self):
        ui_settings = self.media_config.get("ui_settings", {})
        diag_conf = ui_settings.get("dialogue_box", {})
        input_conf = ui_settings.get("input_box", {})

        self.dialogue_box = DialogueBox(
            x=diag_conf.get("x", 50),
            y=diag_conf.get("y", 430),
            width=diag_conf.get("width", 900),
            height=diag_conf.get("height", 150),
            font=self.dialogue_font
        )
        
        # [수정] DialogueBox 콜백 등록 - 대사 출력 시작 시 음성 재생
        self.dialogue_box.on_dialogue_start = self._on_dialogue_start

        self.text_input = TextInput(
            x=input_conf.get("x", 250),
            y=input_conf.get("y", 560),
            width=input_conf.get("width", 500),
            height=input_conf.get("height", 35),
            font=self.input_font,
            initial_text=""
        )

    def _load_objects(self):
        objects_conf = self.media_config.get("paths", {}).get("objects", {})

        def load_and_scale(key, default_pos):
            data = objects_conf.get(key)
            if not data:
                return None, default_pos
            path = data.get("path")
            if not path or not Path(path).exists():
                return None, default_pos
            img = pygame.image.load(path).convert_alpha()
            width = data.get("width")
            if width:
                ratio = width / img.get_width()
                img = pygame.transform.smoothscale(img, (width, int(img.get_height() * ratio)))
            return img, (data.get("x", default_pos[0]), data.get("y", default_pos[1]))

        self.desk_img, self.desk_pos = load_and_scale("desk", (0, 400))
        self.lamp_img, self.lamp_pos = load_and_scale("lamp_off", (100, 320))
        self.lamp_on_img, _ = load_and_scale("lamp_on", (100, 320))
        self.lamp_rect = pygame.Rect(self.lamp_pos[0], self.lamp_pos[1], 100, 150)

    # ========== 상태 관리 메서드 ==========

    def _set_busy(self, busy: bool):
        """입력창 비활성화 상태 설정"""
        self.text_input.set_disabled(busy)

    def _on_dialogue_start(self):
        """
        DialogueBox에서 대사가 출력되기 시작할 때 호출
        (행동 출력 완료 후, 대사 출력 시작)
        
        [핵심] 이 시점에서 이미 TTS 합성이 완료된 음성을 재생
        """
        if self._tts_audio_path and self.audio_manager and self.audio_manager.enabled:
            print(f"[Gameplay] 대사 출력 시작 → 음성 재생!")
            self.audio_manager.play(self._tts_audio_path)

    # [수정] emotion 인자 받기
    def _synthesize_tts(self, dialogue: str, emotion: str = "평온") -> bool:
        try:
            print(f"[TTS Thread] 음성 합성 시작: {dialogue[:30]}... (감정: {emotion})")
            
            # [수정] emotion 전달
            audio_path = self.audio_manager.synthesize(dialogue, emotion=emotion)
            
            if not audio_path:
                print("[TTS Thread] TTS 합성 실패")
                return False
            
            self._tts_audio_path = audio_path
            return True
        except Exception as e:
            # ... (동일)
            print(f"[TTS Thread] ❌ 오류: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _display_llm_response_after_tts(self):
        """
        TTS 합성 완료 후 LLM 응답을 화면에 표시
        """
        if not self._pending_llm_data:
            print("[Display] 대기 중인 LLM 데이터 없음")
            return
        
        data = self._pending_llm_data
        dialogue = data.get("dialogue", "")
        action_pre = data.get("action_pre", "")
        action_post = data.get("action_post", "")
        emotion_kor = data.get("new_emotion", "평온")
        
        self.game_system.update_likability(self.last_emotion, emotion_kor)
        
        # [기존 코드] 호감도 업데이트
        self.game_system.update_likability(self.last_emotion, emotion_kor)
        
        # 👉 [추가] SAN/호감도 변화 후 사운드 상태 동기화
        if self.sound_manager:
            current_san = getattr(self.game_system, 'san', 100)
            self.sound_manager.update_san(current_san)
        
        self.last_emotion = emotion_kor
        self.next_emotion = self.emotion_map.get(emotion_kor, 'neutral')

        # 텍스트 구성
        full_text = ""
        if action_pre:
            full_text += f"({action_pre})\n"
        full_text += f"{dialogue}"
        if action_post:
            full_text += f"\n({action_post})"

        print(f"[Display] DialogueBox에 텍스트 표시: {full_text[:50]}...")
        self.dialogue_box.set_text(full_text)
        
        # 정리
        self._pending_llm_data = None
        self._set_busy(False)
        print("[Display] ✅ LLM 응답 표시 완료")

    def _process_llm_response(self, raw_text: str):
        try:
            print("\n[System] LLM 응답 도착, 파싱 시작...")
            self.is_pipeline_running = False

            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                dialogue = data.get("dialogue", "")
                
                # [중요] 감정 키워드 추출 (예: "슬픔")
                emotion_kor = data.get("new_emotion", "평온")

                self._pending_llm_data = data
                
                if self.audio_manager and self.audio_manager.enabled and dialogue:
                    print(f"[System] TTS 합성 시작 (감정: {emotion_kor})")
                    self.is_processing_tts = True
                    
                    tts_thread = threading.Thread(
                        target=self._synthesize_tts,
                        # [수정] emotion_kor를 인자로 전달!
                        args=(dialogue, emotion_kor) 
                    )
                    tts_thread.daemon = True
                    tts_thread.start()
                else:
                    # TTS 비활성화 상태 → 즉시 텍스트 표시
                    print("[System] TTS 비활성화 → 텍스트 즉시 표시")
                    self._display_llm_response_after_tts()
                    
            else:
                raise ValueError("No JSON found")

        except Exception as e:
            print(f"[Error] Response Parsing Failed: {e}")
            self.dialogue_box.set_text(raw_text)
            self._set_busy(False)
            self.is_pipeline_running = False
            self.is_processing_tts = False

    def _run_rag_and_llm_pipeline(self, user_msg):
        """RAG 및 LLM 파이프라인 실행 (스레드)"""
        try:
            # [추가] 새 메시지 처리 시작 - 플래그 초기화
            self._llm_response_processed = False
            self._tts_ready = False
            self._tts_audio_path = None
            self._pending_llm_data = None
            
            print(f"\n▶ [User] \"{user_msg}\"")
            self.game_system.increment_turn()
            self.game_system.check_san_keywords(user_msg)

            # 👉 [추가] 변경된 SAN 수치를 사운드 매니저에 즉시 반영 (BGM 교체)
            if self.sound_manager:
                # game_system에 san 속성이 있다고 가정 (없으면 .get_san() 등 확인 필요)
                current_san = getattr(self.game_system, 'san', 100) 
                self.sound_manager.update_san(current_san)

            status = self.game_system.get_status_summary()

            status = self.game_system.get_status_summary()
            summary_update = self.llm_manager.get_summary_update()
            if summary_update:
                self.last_topic = summary_update

            if self.rag_manager:
                self.rag_manager.search(user_msg, top_k=3)

            context_data = {
                "san_label": status['san_label'],
                "likability_label": status['likability_label'],
                "last_emotion": self.last_emotion,
                "last_topic": self.last_topic
            }

            prompt = self.character.generate_prompt(user_msg, context_data)
            self.current_user_msg = user_msg
            self.llm_manager.call_roleplay(prompt)

        except Exception as e:
            print(f"[Thread Error] {e}")
            self.is_pipeline_running = False

    # ========== 입출력 메서드 ==========

    def _handle_lamp_click(self):
        """램프 클릭 처리"""
        # [Safety Lock] 작업 중이면 무조건 리턴
        if self.is_pipeline_running or self.is_processing_tts or self.is_recording:
            return
        
        # 👉 [추가 1] 램프 클릭 효과음 재생 (딸깍!)
        if self.sound_manager:
            self.sound_manager.play_click()

        user_input = self.text_input.get_text().strip()

        if user_input:
            # 텍스트가 있으면 바로 전송
            self._start_llm_pipeline(user_input)
        else:
            # 텍스트가 없으면 비동기 녹음 시작
            print("[Lamp] STT 녹음 요청 시작...")
            
            # 👉 [추가 2] STT 시작 전 배경음/탭핑 일시정지
            if self.sound_manager:
                self.sound_manager.pause_for_stt()

            self.is_recording = True
            self.stt_manager.start_listening()

    def _start_llm_pipeline(self, user_msg: str):
        """LLM 처리 스레드 시작 (코드 중복 제거용 헬퍼)"""
        print(f"[Pipeline] 메시지 처리 시작: {user_msg}")
        self.text_input.set_text("")
        self._set_busy(True)
        self.is_pipeline_running = True # [Lock] 파이프라인 잠금
        
        thread = threading.Thread(
            target=self._run_rag_and_llm_pipeline,
            args=(user_msg,)
        )
        thread.daemon = True
        thread.start()

    def _send_message(self):
        """엔터키 입력 처리용"""
        # 램프 클릭과 동일한 로직을 타되, 엔터키는 텍스트 전송만 담당하게 제한할 수도 있음
        # 여기서는 텍스트가 있을 때만 전송하도록 처리
        user_input = self.text_input.get_text().strip()
        if user_input:
             # 작업 중이 아닐 때만
            if not (self.is_pipeline_running or self.is_processing_tts or self.is_recording):
                self._start_llm_pipeline(user_input)

    # ========== 이벤트 처리 ==========

    def handle_events(self, event):
        """이벤트 처리 (입력, 클릭 등)"""
        if self.text_input.disabled:
            return

        # [수정 1] 입력창에게 이벤트를 먼저 전달
        # 입력창이 이벤트를 처리했다면 더 이상 진행하지 않음
        if self.text_input.handle_event(event):
            return

        # [수정 2] 마우스 클릭 처리
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.lamp_rect.collidepoint(event.pos):
                self._handle_lamp_click()  # 이제 이 함수 안에서 상태 체크
                return

            # 대화창 스킵 기능 (입력창/램프 클릭이 아닐 때만)
            self.dialogue_box.skip()

        # [수정 3] 엔터키 처리 (작업 중이 아닐 때만)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            # 이미 작업 중이면 엔터키도 무시
            if not (self.is_pipeline_running or self.is_processing_tts or self.is_recording):
                self._send_message()

    # ========== 업데이트 ==========

    def update(self, dt):
        """매 프레임 업데이트"""
        self.bg_anim.update(dt)
        self.dialogue_box.update(dt)
        self.text_input.update(dt)

        # 👉 [추가] 사운드 매니저 업데이트 (자동 탭핑 타이머 계산용)
        if self.sound_manager:
            self.sound_manager.update(dt)

        # ---------------------------------------------------------
        # [1] 비동기 STT 결과 모니터링 (Polling)
        # ---------------------------------------------------------
        if self.is_recording:
            stt_result = self.stt_manager.check_result()
            
            if stt_result is not None:
                # 녹음 종료됨
                self.is_recording = False 
                
                # 👉 [추가] 녹음 끝났으니 배경음/탭핑 다시 재생
                if self.sound_manager:
                    self.sound_manager.resume_after_stt()

                if stt_result.strip():
                    print(f"[STT] 결과 수신: {stt_result}")
                    self._start_llm_pipeline(stt_result)
                else:
                    print("[STT] 인식 실패 또는 침묵")
                    # 실패했더라도 소리는 다시 켜줘야 함 (위에서 이미 처리됨)
        # ---------------------------------------------------------

        # --- [애니메이션 상태 관리] ---
        # 생각 중 상태: 파이프라인 도는 중 OR 녹음 중 OR TTS 중
        is_thinking = (
            self.is_pipeline_running or
            self.llm_manager.is_thinking() or
            self.is_processing_tts or 
            self.is_recording  # 녹음 중에도 생각하는 표정(혹은 듣는 표정)
        )

        if is_thinking:
            self.char_portrait.set_state('thinking_loop')
        else:
            self.char_portrait.set_state(self.next_emotion)

        self.char_portrait.update(dt)

        # [수정] TTS 합성 완료 감지 및 DialogueBox 표시
        if self.is_processing_tts and self._tts_audio_path and self._pending_llm_data:
            # TTS 합성이 완료되었고, 대기 중인 LLM 데이터가 있음
            print("[Update] TTS 합성 완료 감지 → DialogueBox에 텍스트 표시")
            self.is_processing_tts = False
            self._display_llm_response_after_tts()

        # [기존] LLM 응답 체크
        response = self.llm_manager.get_response()
        if response and not self._llm_response_processed:
            self._llm_response_processed = True
            
            if hasattr(self, 'current_user_msg'):
                self.llm_manager.call_summary(
                    self.current_user_msg,
                    response,
                    self.last_topic,
                    self.game.summary_model_name
                )
            self._process_llm_response(response)

    # ========== 렌더링 ==========

    def _draw_scene(self, screen):
        """씬 렌더링"""
        self.bg_anim.draw(screen, (0, 0))
        self.char_portrait.draw(screen)

        if self.desk_img:
            screen.blit(self.desk_img, self.desk_pos)

        target_img = (
            self.lamp_img if self.is_recording
            else (self.lamp_on_img or self.lamp_img)
        )
        if target_img:
            screen.blit(target_img, self.lamp_pos)

        self.dialogue_box.draw(screen)
        self.text_input.draw(screen)

    def draw(self, screen):
        """화면 렌더링"""
        self._draw_scene(screen)