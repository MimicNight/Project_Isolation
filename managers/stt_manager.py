"""
STT(음성 인식) 매니저 - 비동기 지원 버전
OpenAI Whisper를 통한 음성 입력 처리

MIT License
"""

import threading
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
from typing import Optional, Dict, Any
from pathlib import Path

class SttManager:
    """STT 기능 관리 (마이크 입력 → 텍스트 변환, 비동기 지원)"""

    def __init__(self, config: Dict[str, Any]):
        """
        STT 매니저 초기화
        """
        self.enabled = config.get("enabled", False)
        self.engine = config.get("engine", "whisper")
        self.model_name = config.get("model", "small")
        self.language = config.get("language", "ko")
        self.record_seconds = config.get("record_seconds", 5)

        self.model = None
        self._temp_audio_path = "temp_audio.wav"
        
        # 비동기 처리를 위한 상태 변수
        self.is_processing = False   # 현재 녹음/변환 중인지
        self.status_message = ""     # 현재 상태 메시지 (UI 표시용)
        self._result_text: Optional[str] = None # 변환 완료된 텍스트

        if self.enabled:
            # 모델 로딩도 오래 걸리므로 스레드로 처리 가능하지만, 
            # 보통 로딩 화면에서 처리하므로 여기선 일단 둡니다.
            self._load_model()

        print(f"[SttManager] 초기화 완료 (enabled={self.enabled}, model={self.model_name})")

    def _load_model(self) -> None:
        """Whisper 모델 로드"""
        try:
            import whisper
            print(f"[SttManager] Whisper 모델 로드 중: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            print(f"[SttManager] ✅ Whisper 모델 로드 완료")
        except ImportError:
            print("[SttManager] ❌ openai-whisper 설치 필요")
            self.enabled = False
        except Exception as e:
            print(f"[SttManager] ❌ 모델 로드 실패: {e}")
            self.enabled = False

    def start_listening(self, record_seconds: Optional[int] = None) -> None:
        """
        [비동기] 녹음 및 변환 작업 시작
        이 함수는 즉시 반환되며, 작업은 백그라운드 스레드에서 실행됩니다.
        결과는 check_result()를 통해 확인해야 합니다.
        """
        if not self.enabled or not self.model:
            print("[SttManager] STT 비활성화 상태")
            return

        if self.is_processing:
            print("[SttManager] 이미 작업 중입니다.")
            return

        self.is_processing = True
        self._result_text = None
        self.status_message = "Listening..."
        
        seconds = record_seconds or self.record_seconds

        # 데몬 스레드로 실행 (메인 프로그램 종료 시 같이 종료됨)
        thread = threading.Thread(
            target=self._listening_task, 
            args=(seconds,),
            daemon=True
        )
        thread.start()

    def _listening_task(self, seconds: int):
        """백그라운드 스레드에서 실행되는 실제 작업"""
        try:
            # 1. 녹음
            print(f"[SttManager] 🎤 녹음 시작 ({seconds}s)...")
            self.status_message = "Recording..."
            
            sample_rate = 16000
            # sd.rec은 비동기지만, sd.wait()는 블로킹입니다.
            # 스레드 내부이므로 메인 게임 루프는 멈추지 않습니다.
            audio_data = sd.rec(
                int(sample_rate * seconds),
                samplerate=sample_rate,
                channels=1,
                dtype=np.float32
            )
            sd.wait() # 녹음 완료 대기
            
            # 2. 파일 저장
            self.status_message = "Processing..."
            sf.write(self._temp_audio_path, audio_data, sample_rate)
            
            # 3. 변환 (무거운 작업)
            # fp16=False는 CPU 사용 시 경고 방지용
            result = self.model.transcribe(
                self._temp_audio_path,
                language=self.language,
                fp16=False 
            )
            
            text = result.get("text", "").strip()
            print(f"[SttManager] ✅ 인식 결과: {text}")
            
            # 결과 저장
            self._result_text = text

        except Exception as e:
            print(f"[SttManager] ❌ 스레드 작업 오류: {e}")
            self._result_text = "" # 오류 시 빈 문자열
        finally:
            # 4. 정리
            try:
                Path(self._temp_audio_path).unlink()
            except:
                pass
            
            self.is_processing = False
            self.status_message = ""

    def check_result(self) -> Optional[str]:
        """
        [메인 루프용] 작업 완료 여부 확인 및 결과 반환
        
        Returns:
            str: 인식된 텍스트 (작업 완료 시)
            None: 아직 작업 중이거나 결과가 없을 때
        """
        # 작업은 끝났는데 결과가 있다면 반환하고 초기화
        if not self.is_processing and self._result_text is not None:
            result = self._result_text
            self._result_text = None # 한 번 읽으면 초기화
            return result
        
        return None

    def get_status(self) -> str:
        """현재 상태 메시지 반환 (UI 표시용)"""
        return self.status_message