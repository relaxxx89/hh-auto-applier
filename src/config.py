"""
Загрузка и валидация конфигурации
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class TimeoutConfig:
    """Конфигурация таймаутов"""
    implicit_wait: float = 0.3
    modal_wait: float = 1.0
    element_wait: float = 0.5
    page_load_wait: float = 2.0


@dataclass 
class ResumeRule:
    """Правило выбора резюме"""
    title: str
    keywords: List[str]


@dataclass
class Config:
    """Главная конфигурация бота"""
    
    # Поисковые запросы
    search_queries: List[str] = field(default_factory=lambda: [
        "linux системный администратор",
        "devops инженер",
    ])
    
    # Ключевые слова для фильтрации
    allowed_keywords: List[str] = field(default_factory=lambda: [
        "linux", "devops", "sre", "системный администратор",
    ])
    
    # Правила выбора резюме
    resume_rules: List[ResumeRule] = field(default_factory=list)
    
    # Сопроводительное письмо
    cover_letter: str = ""
    
    # Настройки поиска
    area: int = 113  # Россия
    schedule: str = "remote"
    max_pages: int = 5
    
    # Настройки бота
    debug: bool = False
    save_interval: int = 10
    
    # Таймауты
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    
    # Пути к файлам
    processed_file: str = "processed_vacancies.json"
    skipped_file: str = "skipped_vacancies.json"
    
    # Базовый URL
    hh_base: str = "https://hh.ru/search/vacancy"


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Загружает конфигурацию из YAML файла.
    Если файл не найден, возвращает конфигурацию по умолчанию.
    """
    if config_path is None:
        # Ищем config.yaml в текущей директории или рядом со скриптом
        possible_paths = [
            Path("config.yaml"),
            Path(__file__).parent.parent / "config.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break
    
    if config_path and os.path.exists(config_path):
        return _load_from_yaml(config_path)
    
    print("[WARN] config.yaml не найден, используем настройки по умолчанию")
    print("[HINT] Скопируйте config.example.yaml в config.yaml и настройте")
    return Config()


def _load_from_yaml(path: str) -> Config:
    """Загружает конфигурацию из YAML файла"""
    if yaml is None:
        print("[ERROR] PyYAML не установлен. Выполните: pip install pyyaml")
        sys.exit(1)
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data:
        return Config()
    
    # Парсим таймауты
    timeouts_data = data.get('timeouts', {})
    timeouts = TimeoutConfig(
        implicit_wait=timeouts_data.get('implicit_wait', 0.3),
        modal_wait=timeouts_data.get('modal_wait', 1.0),
        element_wait=timeouts_data.get('element_wait', 0.5),
        page_load_wait=timeouts_data.get('page_load_wait', 2.0),
    )
    
    # Парсим правила резюме
    resume_rules = []
    for rule_data in data.get('resume_rules', []):
        resume_rules.append(ResumeRule(
            title=rule_data.get('title', ''),
            keywords=rule_data.get('keywords', []),
        ))
    
    return Config(
        search_queries=data.get('search_queries', Config.search_queries),
        allowed_keywords=data.get('allowed_keywords', Config.allowed_keywords),
        resume_rules=resume_rules,
        cover_letter=data.get('cover_letter', ''),
        area=data.get('area', 113),
        schedule=data.get('schedule', 'remote'),
        max_pages=data.get('max_pages', 5),
        debug=data.get('debug', False),
        save_interval=data.get('save_interval', 10),
        timeouts=timeouts,
    )


def get_resume_rules_as_dicts(config: Config) -> List[Dict[str, Any]]:
    """Конвертирует правила резюме в формат словарей для совместимости"""
    return [
        {
            "title_substring": rule.title,
            "match_keywords": rule.keywords,
        }
        for rule in config.resume_rules
    ]
