"""
Работа с карточками вакансий
"""

import hashlib
from typing import List, Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .selenium_helper import SeleniumHelper
from .logger import get_logger


class VacancyCard:
    """Представляет карточку вакансии в результатах поиска"""
    
    TITLE_SELECTORS = [
        "[data-qa='vacancy-serp__vacancy-title']",
        "[data-qa='serp-item__title']",
        "[data-qa='serp-item__title-text']",
    ]
    
    LINK_SELECTORS = [
        "a[data-qa='vacancy-serp__vacancy-title']",
        "a[data-qa='serp-item__title']",
        "a.bloko-link[href*='/vacancy/']",
        "a[href*='/vacancy/']",
    ]
    
    APPLY_BUTTON_SELECTOR = "[data-qa='vacancy-serp__vacancy_response']"
    
    def __init__(self, card_element, helper: SeleniumHelper):
        self.element = card_element
        self.helper = helper
        self._id: Optional[str] = None
        self._title: Optional[str] = None
    
    @property
    def id(self) -> Optional[str]:
        """Возвращает ID вакансии"""
        if self._id is not None:
            return self._id
        
        logger = get_logger()
        
        try:
            # Пробуем атрибут data-vacancy-id
            vacancy_id = self.element.get_attribute('data-vacancy-id')
            if vacancy_id:
                self._id = vacancy_id
                return self._id
            
            # Пробуем извлечь из ссылки
            link = self.helper.find_by_selectors(self.LINK_SELECTORS, self.element)
            if link:
                href = link.get_attribute('href')
                if href and '/vacancy/' in href:
                    self._id = href.split('/vacancy/')[1].split('?')[0]
                    return self._id
        except Exception as e:
            logger.debug(f"Не удалось получить ID вакансии: {e}")
        
        # Fallback на хеш заголовка
        if self.title:
            self._id = "hash_" + hashlib.md5(self.title.encode()).hexdigest()[:12]
        
        return self._id
    
    @property
    def title(self) -> str:
        """Возвращает заголовок вакансии"""
        if self._title is not None:
            return self._title
        
        for selector in self.TITLE_SELECTORS:
            try:
                el = self.element.find_element(By.CSS_SELECTOR, selector)
                text = el.text.strip()
                if text:
                    self._title = text
                    return self._title
            except NoSuchElementException:
                continue
        
        self._title = ""
        return self._title
    
    def get_apply_button(self):
        """Возвращает кнопку 'Откликнуться' или None"""
        try:
            btn = self.element.find_element(By.CSS_SELECTOR, self.APPLY_BUTTON_SELECTOR)
            if "Откликнуться" in btn.text:
                return btn
        except NoSuchElementException:
            pass
        return None
    
    def is_suitable(self, keywords: List[str]) -> bool:
        """Проверяет, подходит ли вакансия по ключевым словам"""
        title_lower = self.title.lower()
        return any(kw.lower() in title_lower for kw in keywords)
