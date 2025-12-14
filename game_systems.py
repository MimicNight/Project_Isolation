"""게임 시스템 관리자 - 호감도, SAN, 턴 (MIT License)

이 모듈은 게임의 핵심 수치(호감도, SAN, 턴)를 관리합니다.
- 호감도: LLM의 감정 변화에 따라 증감
- SAN: 플레이어 입력의 키워드 유사도 검사로 감소
- 턴: 플레이어 입력마다 증가
"""

import json
from pathlib import Path
from typing import Optional, List, Dict
from rapidfuzz import fuzz


class GameSystemManager:
    """호감도(Sadism), SAN, 턴 수를 관리하는 게임 시스템"""
    
    def __init__(self, keywords_path: str = "config/san_keywords.json"):
        """
        Args:
            keywords_path: SAN 감소 키워드 설정 파일 경로
        """
        # 초기 수치
        self.likability: int = 50  # 호감도 (0~100)
        self.san: int = 100  # SAN (0~100)
        self.turn_count: int = 0  # 턴 수
        
        # 키워드 로드
        self.keywords: List[str] = []
        self.similarity_threshold: int = 80
        self.decrease_amount: int = 5
        self._load_keywords(keywords_path)
        
        # 감정 매핑
        self.positive_emotions = [
            "기쁨",      # Joy
            "흥미",      # Interest
            "만족",      # Contentment
            "친밀감",    # Warmth
            "안도",      # Relief
            "흥분"       # Excitement (긍정 극단)
        ]
        
        self.neutral_emotions = [
            "평온",      # Calm
            "당혹"       # Perplexed
        ]
        
        self.negative_emotions = [
            "경계",      # Guarded
            "불안",      # Anxious
            "슬픔",      # Sad
            "짜증",      # Irritated
            "분노",      # Angry
            "공포",      # Fear (부정 극단)
            "혐오"       # Disgust (거부 극단)
        ]
        
        print(f"[GameSystem] 초기화 완료 | 호감도: {self.likability}, SAN: {self.san}")
    
    def _load_keywords(self, path: str) -> None:
        """키워드 파일 로드"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.keywords = data.get("keywords", [])
                self.similarity_threshold = data.get("similarity_threshold", 80)
                self.decrease_amount = data.get("decrease_amount", 5)
                print(f"[GameSystem] 설정 로드 성공: {len(self.keywords)}개 키워드 (임계값: {self.similarity_threshold}%, 감소량: {self.decrease_amount})")
        except FileNotFoundError:
            print(f"[GameSystem] ⚠️ 키워드 파일 없음: {path}. 기본값 사용.")
            self.keywords = ["죽음", "살인", "피", "고통", "괴롭히다", "아이", "선악과"]
        except json.JSONDecodeError as e:
            print(f"[GameSystem] ⚠️ JSON 파싱 오류: {e}")
            self.keywords = []
    
    def increment_turn(self) -> None:
        """턴 증가 (플레이어 입력마다 호출)"""
        self.turn_count += 1
        print(f"\n[GameSystem] ==================== TURN {self.turn_count} START ====================")
        print(f"[GameSystem] 현재 상태 | 호감도: {self.likability} ({self.get_likability_label()}), SAN: {self.san} ({self.get_san_label()})")
    
    def update_likability(self, prev_emotion: str, new_emotion: str) -> int:
        """
        감정 변화에 따라 호감도 업데이트
        """
        print(f"[GameSystem] 호감도 계산 요청: '{prev_emotion}' → '{new_emotion}'")
        
        delta = 0
        reason = ""
        
        # 감정이 동일하면 변화 없음
        if prev_emotion == new_emotion:
            print(f"  └ [변동 없음] 감정이 유지됨.")
            return 0
        
        # 이전/현재 감정의 카테고리 판별
        prev_is_positive = prev_emotion in self.positive_emotions
        prev_is_neutral = prev_emotion in self.neutral_emotions
        prev_is_negative = prev_emotion in self.negative_emotions
        
        new_is_positive = new_emotion in self.positive_emotions
        new_is_neutral = new_emotion in self.neutral_emotions
        new_is_negative = new_emotion in self.negative_emotions
        
        # 로직 판별
        if prev_is_negative and new_is_positive:
            delta = 15
            reason = "부정 → 긍정 (대변화)"
        elif prev_is_positive and new_is_negative:
            delta = -15
            reason = "긍정 → 부정 (대변화)"
        elif prev_is_neutral and new_is_positive:
            delta = 8
            reason = "중립 → 긍정"
        elif prev_is_neutral and new_is_negative:
            delta = -8
            reason = "중립 → 부정"
        elif prev_is_positive and new_is_neutral:
            delta = 2
            reason = "긍정 → 중립 (여운)"
        elif prev_is_negative and new_is_neutral:
            delta = -2
            reason = "부정 → 중립 (앙금)"
        elif prev_is_positive and new_is_positive:
            delta = 5
            reason = "긍정 강화"
        elif prev_is_negative and new_is_negative:
            delta = -5
            reason = "부정 심화"
        elif prev_is_neutral and new_is_neutral:
            delta = 0
            reason = "중립 유지"
        else:
            reason = "정의되지 않은 패턴"
        
        # 호감도 갱신 (0~100 범위)
        old_likability = self.likability
        self.likability = max(0, min(100, self.likability + delta))
        
        print(f"  └ [판정] {reason}")
        print(f"  └ [결과] {old_likability} → {self.likability} (변동: {delta:+d})")
        
        return delta
    
    def check_san_keywords(self, user_input: str) -> bool:
        """
        사용자 입력에서 SAN 감소 키워드 검사 (유사도 기반)
        """
        if not user_input.strip():
            return False
            
        print(f"[GameSystem] SAN 키워드 스캔 중... (입력 길이: {len(user_input)})")
        
        user_input_lower = user_input.lower()
        detected_keywords = []
        
        for keyword in self.keywords:
            # rapidfuzz로 유사도 계산 (부분 매칭)
            similarity = fuzz.partial_ratio(keyword, user_input_lower)
            
            if similarity >= self.similarity_threshold:
                detected_keywords.append((keyword, similarity))
        
        # 키워드가 검출되면 SAN 감소
        if detected_keywords:
            old_san = self.san
            self.san = max(0, self.san - self.decrease_amount)
            
            # 로그 출력
            keyword_log = ", ".join([f"'{kw}'({sim}%)" for kw, sim in detected_keywords])
            print(f"  └ [⚠️ 경고] 위험 키워드 검출: {keyword_log}")
            print(f"  └ [SAN 감소] {old_san} → {self.san} (-{self.decrease_amount})")
            return True
        else:
            print("  └ [안전] 검출된 키워드 없음.")
        
        return False
    
    def get_san_label(self) -> str:
        """SAN 수치를 상태 레이블로 변환"""
        if self.san >= 75: return "안정"
        elif self.san >= 50: return "균열"
        elif self.san >= 25: return "착란"
        else: return "붕괴"
    
    def get_likability_label(self) -> str:
        """호감도 수치를 Sadism 레이블로 변환"""
        if self.likability < 10: return "혐오"
        elif self.likability < 30: return "불쾌"
        elif self.likability < 50: return "무관심"
        elif self.likability < 70: return "호기심"
        elif self.likability < 90: return "애착"
        else: return "탐닉"
    
    def get_status_summary(self) -> Dict:
        """현재 게임 상태 요약"""
        return {
            "likability": self.likability,
            "likability_label": self.get_likability_label(),
            "san": self.san,
            "san_label": self.get_san_label(),
            "turn_count": self.turn_count
        }
    
    def set_san(self, value: int) -> None:
        """SAN 값 직접 설정 (치트/테스트용)"""
        old_val = self.san
        self.san = max(0, min(100, value))
        print(f"[GameSystem] [Cheat] SAN 강제 변경: {old_val} → {self.san}")
    
    def set_likability(self, value: int) -> None:
        """호감도 값 직접 설정 (치트/테스트용)"""
        old_val = self.likability
        self.likability = max(0, min(100, value))
        print(f"[GameSystem] [Cheat] 호감도 강제 변경: {old_val} → {self.likability}")
    
    def reset(self) -> None:
        """게임 시스템 초기화"""
        print("[GameSystem] 시스템 리셋 중...")
        self.likability = 50
        self.san = 100
        self.turn_count = 0
        print("[GameSystem] 리셋 완료 (호감도 50, SAN 100, Turn 0)")