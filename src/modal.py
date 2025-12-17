"""
Работа с модальным окном отклика
"""

import time
from typing import List, Optional, Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException
)

from .selenium_helper import SeleniumHelper
from .logger import get_logger


class ApplicationModal:
    """Обрабатывает модальное окно отклика на вакансию"""
    
    MODAL_SELECTORS = [
        "[data-qa='modal-wrapper']",
        ".bloko-modal",
        ".bloko-modal-wrapper",
        "[role='dialog']",
    ]
    
    RESUME_SELECT_SELECTORS = [
        "[data-qa='resume-select']",
        "[data-qa='vacancy-response-letter-resume-select']",
        ".bloko-select-toggle",
        "select[data-qa*='resume']",
    ]
    
    SUBMIT_BUTTON_SELECTORS = [
        "[data-qa='vacancy-response-submit-popup']",
        "[data-qa='vacancy-response-submit']",
        "[data-qa='vacancy-response-letter-submit']",
        "button[type='submit']",
    ]
    
    CLOSE_BUTTON_SELECTORS = [
        "[data-qa='vacancy-response-letter-close']",
        ".bloko-modal-close-button",
        "[data-qa='modal-close']",
        "button[aria-label='Закрыть']",
    ]
    
    RESUME_OPTIONS_SELECTORS = [
        "[data-qa='resume-select-option']",
        "[data-qa='vacancy-response-letter-resume-option']",
        ".bloko-menu-item",
        "[role='option']",
    ]
    
    def __init__(self, driver, helper: SeleniumHelper, timeouts):
        self.driver = driver
        self.helper = helper
        self.timeouts = timeouts
    
    def wait_for_modal(self) -> bool:
        """Ожидает появления модального окна"""
        logger = get_logger()
        
        try:
            wait = WebDriverWait(self.driver, self.timeouts.modal)
            
            for selector in self.MODAL_SELECTORS:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    logger.debug(f"Модальное окно найдено: {selector}")
                    return True
                except TimeoutException:
                    continue
            
            return False
        except Exception as e:
            logger.debug(f"Ошибка ожидания модалки: {e}")
            return False
    
    def find_resume_dropdown(self):
        """Находит выпадающий список резюме"""
        for selector in self.RESUME_SELECT_SELECTORS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue
        return None
    
    def select_resume(self, rules: List, vacancy_title: str) -> str:
        """Выбирает резюме по правилам, возвращает название выбранного"""
        logger = get_logger()
        
        dropdown = self.find_resume_dropdown()
        if not dropdown:
            logger.debug("Dropdown резюме не найден")
            return ""
        
        selected = ""
        
        # Кликаем на dropdown чтобы открыть список
        for attempt in range(3):
            try:
                dropdown.click()
                time.sleep(0.7)
                break
            except StaleElementReferenceException:
                dropdown = self.find_resume_dropdown()
                if not dropdown:
                    return ""
        
        # Ищем нужное резюме по правилам
        options = self._get_resume_options()
        if not options:
            logger.debug("Варианты резюме не найдены")
            return ""
        
        title_lower = vacancy_title.lower()
        matched_resume = None
        
        # Проверяем по правилам
        for rule in rules:
            for keyword in rule.keywords:
                if keyword.lower() in title_lower:
                    # Ищем резюме по имени
                    for option in options:
                        try:
                            option_text = option.text.strip()
                            # Ищем ключевое слово в названии резюме
                            if rule.resume_name.lower() in option_text.lower():
                                matched_resume = option
                                selected = option_text
                                logger.info(f"Найдено резюме по правилу: {selected}")
                                break
                        except StaleElementReferenceException:
                            continue
                    
                    if matched_resume:
                        break
            
            if matched_resume:
                break
        
        # Если не найдено по правилам, берем первое
        if not matched_resume and options:
            try:
                matched_resume = options[0]
                selected = matched_resume.text.strip()
                logger.info(f"Выбрано первое резюме: {selected}")
            except (StaleElementReferenceException, IndexError):
                pass
        
        # Кликаем на выбранное резюме
        if matched_resume:
            try:
                matched_resume.click()
                time.sleep(0.3)
            except (StaleElementReferenceException, Exception):
                pass
        
        return selected
    
    def _get_resume_options(self) -> list:
        """Получает список вариантов резюме"""
        options = []
        
        for selector in self.RESUME_OPTIONS_SELECTORS:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    options.extend(elements)
            except Exception:
                continue
        
        return options
    
    def submit(self) -> bool:
        """Нажимает кнопку отправки отклика"""
        logger = get_logger()
        
        btn = self.helper.find_by_selectors(self.SUBMIT_BUTTON_SELECTORS)
        if btn:
            if self.helper.safe_click(btn):
                logger.debug("Отклик отправлен")
                return True
        
        logger.warn("Кнопка отправки не найдена")
        return False
    
    def close(self):
        """Закрывает модальное окно"""
        logger = get_logger()
        
        # Пробуем найти кнопку закрытия
        btn = self.helper.find_by_selectors(self.CLOSE_BUTTON_SELECTORS)
        if btn and self.helper.safe_click(btn):
            logger.debug("Модальное окно закрыто кнопкой")
            return
        
        # Пробуем Escape
        try:
            from selenium.webdriver.common.keys import Keys
            body = self.driver.find_element(By.TAG_NAME, 'body')
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.3)
            logger.debug("Модальное окно закрыто Escape")
        except Exception:
            pass
    
    def is_open(self) -> bool:
        """Проверяет, открыто ли модальное окно"""
        for selector in self.MODAL_SELECTORS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el.is_displayed():
                    return True
            except NoSuchElementException:
                continue
        return False
    
    def handle_questions(self) -> Tuple[bool, str]:
        """Обрабатывает дополнительные вопросы в модалке"""
        # Проверка на наличие обязательных вопросов
        try:
            required = self.driver.find_elements(
                By.CSS_SELECTOR, "[data-qa='vacancy-response-letter-required']"
            )
            if required:
                return False, "Вакансия требует ответы на вопросы"
        except Exception:
            pass
        
        return True, ""
