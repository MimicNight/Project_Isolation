"""테마 및 색상 관리 시스템 (MIT License)"""

import json
from typing import Dict, List, Tuple
from pathlib import Path


class ThemeManager:
    """
    중앙 집중식 테마 및 색상 관리자.
    
    JSON 설정을 로드하여 색상, 폰트, 레이아웃을 관리하고,
    런타임에 테마 변경을 지원합니다.
    """

    def __init__(self, config_path: str = "config/theme.json"):
        """
        Args:
            config_path: 테마 설정 JSON 파일 경로
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> Dict:
        """JSON 설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"테마 설정 파일을 찾을 수 없습니다: {self.config_path}"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 파싱 오류: {e}")

    def _validate_config(self) -> None:
        """설정 유효성 검사"""
        required_keys = ["colors", "fonts", "layout"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"필수 설정 키 누락: {key}")

    def get_color(self, color_name: str) -> Tuple[int, int, int]:
        """
        색상 이름으로 RGB 튜플 반환
        
        Args:
            color_name: 색상 이름 (예: "text_primary")
            
        Returns:
            RGB 튜플
        """
        if color_name not in self.config["colors"]:
            raise KeyError(f"정의되지 않은 색상: {color_name}")
        return tuple(self.config["colors"][color_name])

    def get_font_path(self) -> str:
        """폰트 파일 경로 반환 (fallback 포함)"""
        primary = self.config["fonts"]["primary"]
        if Path(primary).exists():
            return primary
        return self.config["fonts"]["fallback_system"]

    def get_font_size(self, size_key: str) -> int:
        """폰트 크기 반환"""
        return self.config["fonts"]["sizes"].get(size_key, 16)

    def get_layout_value(self, key: str, default=None):
        """레이아웃 값 반환"""
        return self.config["layout"].get(key, default)

    def get_all_colors(self) -> Dict[str, Tuple[int, int, int]]:
        """모든 색상 사전 반환"""
        return {
            name: tuple(rgb)
            for name, rgb in self.config["colors"].items()
        }

    def export_theme(self, output_path: str) -> None:
        """현재 테마를 새 파일로 내보내기"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)


# 글로벌 테마 매니저 인스턴스
_theme_manager = None


def init_theme(config_path: str = "config/theme.json") -> ThemeManager:
    """전역 테마 매니저 초기화"""
    global _theme_manager
    _theme_manager = ThemeManager(config_path)
    return _theme_manager


def get_theme() -> ThemeManager:
    """전역 테마 매니저 인스턴스 반환"""
    if _theme_manager is None:
        return init_theme()
    return _theme_manager