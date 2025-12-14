"""
TTS(음성 합성) 매니저
GPT-SoVITS WebAPI를 통한 음성 합성 및 재생

MIT License
"""

import requests
import pygame
import os
import json
from typing import Optional, Dict, Any
from pathlib import Path

class AudioManager:
    """TTS 기능 관리 (음성 합성 + 재생)"""

    def __init__(self, config: Dict[str, Any]):
        """
        TTS 매니저 초기화 - 안정성 강화 버전
        """
        print("[AudioManager] 초기화 시작...")

        # 1. [필수] 변수 기본값 선언 (AttributeError 방지용)
        self.enabled = False
        self.engine = "gpt-sovits"
        self._current_sound = None
        
        # 2. 설정 파일(config)이 비어있는지 체크
        if not config:
            print("[AudioManager] ⚠️ 경고: media.json의 'tts' 설정이 비어있습니다. TTS를 끕니다.")
            return

        try:
            # 3. 설정값 로드
            self.enabled = config.get("enabled", False)
            self.engine = config.get("engine", "gpt-sovits")
            self.api_url = config.get("api_url", "http://127.0.0.1:9880/tts")
            
            # [감정 매핑 데이터]
            self.emotion_maps = config.get("emotion_maps", {})
            self.default_emotion = config.get("default_emotion", "neutral")
            
            # [한글 감정 -> 영어 키 매핑]
            self.ko_to_en_map = {
                "평온": "neutral", "무표정": "neutral", 
                "흥미": "neutral", "만족": "neutral", "당혹": "neutral",
                "짜증": "annoyed", "혐오": "annoyed",
                "분노": "angry", "탐닉": "angry",
                "슬픔": "san", "우울": "san", 
                "불안": "san", "공포": "san", "고통": "san"
            }

            self.speaker_wav = config.get("speaker_wav_path")
            self.speaker_prompt_text = config.get("speaker_prompt_text", "")
            self.speaker_prompt_lang = config.get("speaker_prompt_lang", "ko")
            self.text_lang = config.get("text_lang", "ko")
            self.output_path = config.get("output_path", "assets/audio/outputs/tts_output.wav")
            self.encoding = config.get("encoding", "utf-8")
            
            # 파라미터 로드
            synthesis_params = config.get("synthesis_params", {})
            self.speed_factor = synthesis_params.get("speed_factor", 1.0)
            self.temperature = synthesis_params.get("temperature", 1.0)
            self.top_p = synthesis_params.get("top_p", 1.0)
            self.timeout = synthesis_params.get("timeout", 120)

            # 4. Pygame Mixer 초기화
            if self.enabled:
                if not pygame.mixer.get_init():
                    try:
                        pygame.mixer.init()
                        print("[AudioManager] Pygame Mixer 초기화 성공")
                    except Exception as e:
                        print(f"[AudioManager] ❌ Pygame Mixer 초기화 실패: {e}")
                        self.enabled = False  # 사운드 장치가 없으면 비활성화

        except Exception as e:
            print(f"[AudioManager] ❌ 초기화 중 로직 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            self.enabled = False  # 에러 발생 시 안전하게 비활성화

        status = "✅ 활성화" if self.enabled else "❌ 비활성화"
        print(f"[AudioManager] 초기화 완료: {status} (Engine: {self.engine})")

    def synthesize(self, text: str, emotion: str = "neutral") -> Optional[str]:
        """
        텍스트를 음성으로 변환하여 파일로 저장 (감정 반영)

        Args:
            text: 합성할 텍스트
            emotion: 감정 키워드 (기본값: neutral)

        Returns:
            저장된 음성 파일 경로, 실패 시 None
        """
        if not self.enabled:
            return None

        if not text or not text.strip():
            print("[AudioManager] 빈 텍스트")
            return None

        # 출력 디렉토리 생성
        try:
            output_dir = Path(self.output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[AudioManager] 경로 생성 오류: {e}")
            return None

        try:
            # 1. 한글 감정을 영어 키로 변환
            mapped_key = self.ko_to_en_map.get(emotion, "neutral")
            
            # 2. 영어 키가 emotion_maps에 있는지 확인
            if mapped_key not in self.emotion_maps:
                mapped_key = self.default_emotion

            target_ref = self.emotion_maps.get(mapped_key)
            
            # 3. 참조 파일 정보 설정
            if target_ref:
                ref_wav = target_ref["path"]
                prompt_text = target_ref["text"]
                prompt_lang = target_ref.get("lang", "ko")
            else:
                # 안전장치: 매핑 실패 시 기본 설정 사용
                ref_wav = self.speaker_wav
                prompt_text = self.speaker_prompt_text
                prompt_lang = self.speaker_prompt_lang

            # [중요] API 서버에 보내기 전, 상대 경로를 절대 경로로 변환
            # (API 서버는 프로젝트 내부의 상대 경로를 모를 수 있음)
            if ref_wav:
                ref_wav = os.path.abspath(ref_wav)

            # 4. 페이로드 구성
            payload = {
                "text": text,
                "text_lang": self.text_lang,
                "ref_audio_path": ref_wav, # 절대 경로로 변환된 값 사용
                "prompt_text": prompt_text,
                "prompt_lang": prompt_lang,
                "text_split_method": "cut5",
                "speed": self.speed_factor,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "batch_size": 1,
                "seed": -1
            }

            # 5. 요청 전송
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            # 6. 응답 처리 및 저장
            if response.headers.get("content-type") == "audio/wav":
                with open(self.output_path, "wb") as f:
                    f.write(response.content)
                print(f"[AudioManager] ✅ 합성 완료 ({emotion}): {self.output_path}")
                return self.output_path
            else:
                try:
                    data = response.json()
                    if "status" in data and data["status"] == "ok":
                        audio_path = data.get("audio_path", self.output_path)
                        print(f"[AudioManager] ✅ 합성 완료: {audio_path}")
                        return audio_path
                    else:
                        error_msg = data.get("message", "Unknown error")
                        raise RuntimeError(f"TTS 오류: {error_msg}")
                except json.JSONDecodeError:
                    raise RuntimeError(f"TTS 응답 파싱 오류: {response.text[:200]}")

        except requests.exceptions.ConnectionError:
            print(f"[AudioManager] ❌ TTS API 연결 실패: {self.api_url}")
            return None
        except requests.exceptions.Timeout:
            print(f"[AudioManager] ❌ TTS API 타임아웃 ({self.timeout}초)")
            return None
        except Exception as e:
            print(f"[AudioManager] ❌ 합성 오류: {e}")
            return None

    def play(self, audio_path: str) -> None:
        """
        음성 파일 재생
        """
        if not audio_path or not self.enabled:
            return

        try:
            # 이전 재생 중지
            if self._current_sound:
                self._current_sound.stop()

            # 새 사운드 로드 및 재생
            self._current_sound = pygame.mixer.Sound(audio_path)
            self._current_sound.play()

        except FileNotFoundError:
            print(f"[AudioManager] ❌ 파일 없음: {audio_path}")
        except Exception as e:
            print(f"[AudioManager] ❌ 재생 오류: {e}")

    def stop(self) -> None:
        """음성 재생 중지"""
        if self._current_sound:
            self._current_sound.stop()

    def is_playing(self) -> bool:
        """현재 재생 중인지 확인"""
        if not self._current_sound:
            return False
        return pygame.mixer.get_busy()

    def test_connection(self) -> bool:
        """API 서버 연결 테스트"""
        try:
            response = requests.get(
                self.api_url.replace("/tts", "/health"),
                timeout=5
            )
            print("[AudioManager] ✅ TTS API 서버 연결 확인")
            return True
        except:
            print("[AudioManager] ❌ TTS API 서버 연결 실패")
            return False