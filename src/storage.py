"""
Хранилище для обработанных и пропущенных вакансий
"""

import json
import os
import time
from typing import Dict, Tuple

from .logger import get_logger


class VacancyStorage:
    """Управление хранилищем обработанных и пропущенных вакансий"""
    
    def __init__(self, processed_file: str, skipped_file: str, save_interval: int = 10):
        self.processed_file = processed_file
        self.skipped_file = skipped_file
        self.save_interval = save_interval
        self._save_counter = 0
        
        self.processed: Dict[str, Dict] = self._load_json(processed_file)
        self.skipped: Dict[str, Dict] = self._load_json(skipped_file)
    
    @staticmethod
    def _load_json(filename: str) -> Dict:
        """Загружает JSON файл или возвращает пустой словарь"""
        logger = get_logger()
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Ошибка загрузки {filename}: {e}")
        return {}
    
    def _save_json(self, filename: str, data: Dict) -> None:
        """Сохраняет данные в JSON файл"""
        logger = get_logger()
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.warn(f"Ошибка сохранения {filename}: {e}")
    
    def save(self, force: bool = False) -> None:
        """Сохраняет данные с учётом интервала"""
        self._save_counter += 1
        if force or self._save_counter % self.save_interval == 0:
            self._save_json(self.processed_file, self.processed)
            self._save_json(self.skipped_file, self.skipped)
    
    def is_processed(self, vacancy_id: str) -> bool:
        """Проверяет, была ли вакансия обработана"""
        return vacancy_id in self.processed
    
    def is_skipped(self, vacancy_id: str) -> bool:
        """Проверяет, была ли вакансия пропущена"""
        return vacancy_id in self.skipped
    
    def is_known(self, vacancy_id: str) -> bool:
        """Проверяет, известна ли вакансия (обработана или пропущена)"""
        return self.is_processed(vacancy_id) or self.is_skipped(vacancy_id)
    
    def mark_processed(self, vacancy_id: str, title: str, status: str, 
                       cover_letter: bool = False) -> None:
        """Помечает вакансию как обработанную"""
        self.processed[vacancy_id] = {
            "title": title,
            "status": status,
            "cover_letter": cover_letter,
            "timestamp": time.time()
        }
        self.save()
    
    def mark_skipped(self, vacancy_id: str, title: str, reason: str) -> None:
        """Помечает вакансию как пропущенную"""
        self.skipped[vacancy_id] = {
            "title": title,
            "reason": reason,
            "timestamp": time.time()
        }
        self.save()
    
    def get_stats(self) -> Tuple[int, int]:
        """Возвращает статистику (обработано, пропущено)"""
        return len(self.processed), len(self.skipped)
    
    def get_applied_count(self) -> int:
        """Возвращает количество успешных откликов"""
        return sum(1 for v in self.processed.values() if v.get('status') == 'applied')
