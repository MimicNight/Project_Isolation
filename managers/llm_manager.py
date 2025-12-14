import threading
import queue
import requests
import json
import os
import time
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# Gemini 라이브러리
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

class LLMManager:
    def __init__(self, provider: str = None) -> None:
        self.response_queue: "queue.Queue[str]" = queue.Queue()
        self.summary_queue: "queue.Queue[str]" = queue.Queue()
        self._is_thinking: bool = False
        self._is_summarizing: bool = False
        
        # API 키 로드
        load_dotenv()
        
    def is_thinking(self) -> bool:
        return self._is_thinking

    # =================================================================
    # 1. 메인 대화 (분기 처리: Gemini vs Ollama)
    # =================================================================
    def call_roleplay(self, prompt_data: Dict[str, Any]) -> None:
        if self._is_thinking:
            return
        self._is_thinking = True
        
        # 모델명 확인
        model_name = prompt_data.get("model", "").lower()
        
        # [핵심 로직] 모델명에 'gemini'가 있으면 Google API, 아니면 로컬 Ollama
        if "gemini" in model_name:
            threading.Thread(target=self._gemini_roleplay_thread, args=(prompt_data,), daemon=True).start()
        else:
            threading.Thread(target=self._ollama_roleplay_thread, args=(prompt_data,), daemon=True).start()

    # [Gemini 호출] - 토큰 제한 8192로 증량 + 빈 응답 방지
    def _gemini_roleplay_thread(self, prompt_data: Dict[str, Any]) -> None:
        try:
            print(f"[LLM-Main] Gemini 호출 시작: {prompt_data.get('model')}")
            
            # 1. 설정
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            
            # 2. 모델 생성
            model = genai.GenerativeModel(
                model_name=prompt_data.get("model"),
                system_instruction=prompt_data.get("system", "")
            )
            
            # 3. [핵심] 토큰 제한 대폭 상향 (8192)
            # options에서 값을 가져오되, 기본값을 8192로 설정
            user_options = prompt_data.get("options", {})
            config = genai.types.GenerationConfig(
                temperature=user_options.get("temperature", 0.7),
                top_p=user_options.get("top_p", 0.95),
                max_output_tokens=8192,
                stop_sequences=user_options.get("stop", [])
            )

            # 4. 안전 설정 (차단 해제)
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            # 5. 생성 요청
            response = model.generate_content(
                prompt_data.get("prompt"),
                generation_config=config,
                safety_settings=safety_settings
            )
            
            # 6. 결과 처리 (빈 응답 오류 방지)
            if response.candidates and response.candidates[0].content.parts:
                final_text = response.text
            else:
                # 토큰을 늘렸는데도 내용이 없으면 진짜 오류거나 모델이 침묵을 선택한 것
                finish_reason = "Unknown"
                if response.candidates:
                    finish_reason = response.candidates[0].finish_reason
                
                print(f"[LLM-Main] ⚠️ 내용 없음 (Reason: {finish_reason})")
                final_text = json.dumps({
                    "dialogue": "...", 
                    "action_pre": "생각에 잠겨 있다.",
                    "new_emotion": "무표정"
                })

            self.response_queue.put(final_text)
            print("[LLM-Main] Gemini 응답 완료")

        except Exception as e:
            print(f"[LLM-Main] 오류: {e}")
            self.response_queue.put(json.dumps({"dialogue": f"(오류: {e})", "new_emotion": "고통"}))
        finally:
            self._is_thinking = False

    # [수정됨] 재시도 로직이 추가된 Ollama 호출
    def _ollama_roleplay_thread(self, prompt_data: Dict[str, Any]) -> None:
        max_retries = 3
        url = "http://localhost:11434/api/generate"
        
        try:
            print(f"[LLM-Main] Ollama 호출 시작: {prompt_data.get('model')}")
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        url,
                        json=prompt_data,
                        timeout=120,
                    )
                    
                    # 200 OK인 경우 성공 처리
                    if response.status_code == 200:
                        data = response.json()
                        self.response_queue.put(data.get("response", ""))
                        print("[LLM-Main] Ollama 응답 완료")
                        return # 성공했으므로 함수 종료
                    
                    # 503 Service Unavailable (모델 로딩 중 or 과부하)
                    elif response.status_code == 503:
                        print(f"[LLM-Main] ⚠️ 서버 혼잡 (503). 2초 후 재시도... ({attempt+1}/{max_retries})")
                        time.sleep(2)
                        continue
                    
                    # 그 외 오류는 예외 발생시킴
                    else:
                        response.raise_for_status()
                        
                except requests.exceptions.RequestException as req_err:
                    print(f"[LLM-Main] 연결 오류: {req_err} (재시도 중...)")
                    time.sleep(2)
                    if attempt == max_retries - 1:
                        raise req_err # 마지막 시도에서도 실패하면 예외 던짐

        except Exception as e:
            print(f"[LLM-Main] 최종 오류: {e}")
            self.response_queue.put(f"오류: {e}")
        finally:
             self._is_thinking = False
    
    def get_response(self) -> Optional[str]:
        try:
            return self.response_queue.get_nowait()
        except queue.Empty:
            return None

    # =================================================================
    # 2. 요약 (무조건 Ollama) - 재시도 로직 적용
    # =================================================================
    def call_summary(self, user_text: str, ai_text: str, prev_topic: str, model_name: str) -> None:
        if self._is_summarizing: return
        
        self._is_summarizing = True
        
        prompt = f"""### [Task]
상황 기록관으로서, 아래 대화를 바탕으로 현재 핵심 주제를 한 문장으로 요약하십시오.
(주어는 '유화' 또는 '관리자'로 시작, 20자 이내 명사형 종결)

### [Previous Topic]
{prev_topic}

### [Conversation]
관리자: "{user_text}"
유화: "{ai_text}"

### [Output]
(요약문만 출력)"""
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 40, "stop": ["\n", "###"]}
        }
        
        threading.Thread(target=self._summary_thread, args=(payload,), daemon=True).start()
    
    def _summary_thread(self, payload: Dict[str, Any]) -> None:
        max_retries = 3
        url = "http://localhost:11434/api/generate"
        
        try:
            print(f"[LLM-Summary] 요약 요청 (Model: {payload['model']})")
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        timeout=30,
                    )
                    
                    if response.status_code == 200:
                        summary_text = response.json().get("response", "").strip()
                        summary_text = summary_text.replace('"', '').replace("'", "").split('\n')[0]
                        print(f"[LLM-Summary] 결과: {summary_text}")
                        
                        if summary_text:
                            self.summary_queue.put(summary_text)
                        return # 성공 시 종료
                    
                    elif response.status_code == 503:
                        print(f"[LLM-Summary] ⚠️ 서버 혼잡 (503). 2초 대기 후 재시도... ({attempt+1}/{max_retries})")
                        time.sleep(2)
                        continue
                    
                    else:
                        print(f"[LLM-Summary] 요청 실패: {response.status_code}")
                        break # 503이 아닌 에러는 바로 중단

                except Exception as e:
                    print(f"[LLM-Summary] 연결 예외: {e}")
                    time.sleep(2)
                
        except Exception as e:
            print(f"[LLM-Summary] 치명적 오류: {e}")
        finally:
            self._is_summarizing = False
    
    def get_summary_update(self) -> Optional[str]:
        try:
            return self.summary_queue.get_nowait()
        except queue.Empty:
            return None