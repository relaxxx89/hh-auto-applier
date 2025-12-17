"""
Работа с модальным окном отклика
Адаптировано из main_refactored.py
"""

import time
from typing import List, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException
)


class ApplicationModal:
    """Управление модальным окном отклика"""
    
    MODAL_SELECTORS = [
        "[data-qa*='vacancy-response']",
        "[data-qa*='vacancy-response-modal']",
    ]
    
    CLOSE_BUTTON_SELECTORS = [
        "[data-qa='vacancy-response-modal-close']",
        "button[aria-label='Закрыть']",
    ]
    
    SUBMIT_BUTTON_SELECTORS = [
        "[data-qa='vacancy-response-link-no-questions']",
        "button[data-qa='vacancy-response-submit-popup']",
        "[data-qa='vacancy-response-submit-button']",
        "button[data-qa*='submit']",
    ]
    
    RESUME_SELECTORS = [
        "[data-qa='resume-select-item']",
        "[data-qa='resume-select'] div[data-qa='resume-title']",
        "div[data-qa='resume-title']",
    ]
    
    COVER_LETTER_TEXTAREA = "textarea[data-qa='vacancy-response-popup-form-letter-input']"
    
    def __init__(self, driver, helper, timeouts=None):
        self.driver = driver
        self.helper = helper
        self.timeouts = timeouts
        self.modal_wait = 1.0
        self.element_wait = 0.5
        if timeouts:
            self.modal_wait = getattr(timeouts, 'modal_wait', 1.0)
            self.element_wait = getattr(timeouts, 'element_wait', 0.5)
    
    def open(self, button) -> bool:
        """Открывает модальное окно. Возвращает True при успехе."""
        try:
            original_url = self.driver.current_url
            self.helper.safe_click(button)
            
            time.sleep(0.3)
            if self.driver.current_url != original_url:
                return False
            
            self.helper.wait_for_element("[data-qa*='vacancy-response']", self.modal_wait)
            return True
        except TimeoutException:
            return False
    
    def close(self) -> None:
        """Закрывает модальное окно"""
        for selector in self.CLOSE_BUTTON_SELECTORS:
            try:
                close_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                self.helper.safe_click(close_btn)
                return
            except NoSuchElementException:
                continue
    
    def has_mandatory_test(self) -> bool:
        """Проверяет наличие обязательного теста"""
        url = self.driver.current_url
        if 'startedWithQuestion=true' in url or 'vacancy_response' in url:
            return True
        
        try:
            self.driver.find_element(
                By.CSS_SELECTOR, 
                "[data-qa='vacancy-response-link-no-questions']"
            )
            return False
        except NoSuchElementException:
            pass
        
        return False
    
    def choose_resume(self, vacancy_title: str, resume_rules: List[Any]) -> None:
        """Выбирает подходящее резюме"""
        lower_title = vacancy_title.lower()
        
        matched_rule = None
        for rule in resume_rules:
            if hasattr(rule, 'keywords'):
                keywords = rule.keywords
                title_substring = rule.title
            else:
                keywords = rule.get("match_keywords", rule.get("keywords", []))
                title_substring = rule.get("title_substring", rule.get("title", ""))
            
            if any(kw.lower() in lower_title for kw in keywords):
                matched_rule = {"title_substring": title_substring, "keywords": keywords}
                break
        
        if not matched_rule:
            return
        
        target_substring = matched_rule["title_substring"].lower()
        
        self._open_resume_dropdown()
        
        try:
            resume_titles = WebDriverWait(self.driver, self.element_wait).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[data-qa='resume-title']")
                )
            )
        except TimeoutException:
            return
        
        search_keywords = target_substring.replace("-", " ").replace("--", " ").split()
        
        for block in resume_titles:
            try:
                text = ""
                try:
                    text_el = block.find_element(
                        By.CSS_SELECTOR, "div[data-qa='cell-text-content']"
                    )
                    text = text_el.text.strip()
                except NoSuchElementException:
                    text = block.text.strip()
                
                if not text:
                    continue
                
                text_lower = text.lower()
                
                if target_substring in text_lower:
                    self.helper.safe_click(block)
                    return
                
                if all(kw in text_lower for kw in search_keywords if len(kw) > 2):
                    self.helper.safe_click(block)
                    return
                    
            except Exception:
                continue
        
        if len(resume_titles) == 1:
            self.helper.safe_click(resume_titles[0])
    
    def _open_resume_dropdown(self) -> None:
        """Открывает дропдаун с резюме"""
        try:
            resume_items = self.driver.find_elements(By.CSS_SELECTOR, "div[data-qa='resume-title']")
            visible_count = sum(1 for item in resume_items if item.is_displayed())
            if visible_count > 1:
                return
            
            current_resume = WebDriverWait(self.driver, self.element_wait).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    ", ".join(self.RESUME_SELECTORS)
                ))
            )
            self.helper.safe_click(current_resume)
            time.sleep(0.2)
        except (TimeoutException, Exception):
            pass
    
    def is_cover_letter_required(self) -> bool:
        """Проверяет, обязательно ли сопроводительное письмо"""
        try:
            self.driver.find_element(
                By.XPATH,
                "//*[contains(text(),'обязательн') or contains(text(),'required')]"
            )
            return True
        except NoSuchElementException:
            return False
    
    def add_cover_letter(self, text: str) -> bool:
        """Добавляет сопроводительное письмо"""
        textarea = self._find_cover_letter_textarea()
        
        if textarea is None:
            return False
        
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", textarea
            )
            self.helper.safe_click(textarea)
            textarea.clear()
            textarea.send_keys(text)
            return True
        except Exception:
            return False
    
    def _find_cover_letter_textarea(self):
        """Ищет textarea для сопроводительного письма"""
        try:
            textarea = self.driver.find_element(By.CSS_SELECTOR, self.COVER_LETTER_TEXTAREA)
            if textarea.is_displayed():
                return textarea
        except NoSuchElementException:
            pass
        
        toggle_selectors = ["[data-qa='add-cover-letter']"]
        
        for selector in toggle_selectors:
            try:
                toggle = self.driver.find_element(By.CSS_SELECTOR, selector)
                if toggle.is_displayed():
                    self.helper.safe_click(toggle)
                    break
            except NoSuchElementException:
                continue
        
        try:
            toggle = self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'Добавить сопроводительное')]"
            )
            if toggle.is_displayed():
                self.helper.safe_click(toggle)
        except NoSuchElementException:
            pass
        
        try:
            return self.driver.find_element(By.CSS_SELECTOR, self.COVER_LETTER_TEXTAREA)
        except NoSuchElementException:
            textareas = self.helper.find_elements_safe("textarea")
            for ta in textareas:
                if ta.is_displayed():
                    return ta
        
        return None
    
    def submit(self) -> bool:
        """Отправляет отклик"""
        current_url = self.driver.current_url
        
        modal = self.helper.find_element_safe(
            "[data-qa*='vacancy-response'], [data-qa*='vacancy-response-modal']",
            timeout=0.3
        )
        
        btn = None
        for selector in self.SUBMIT_BUTTON_SELECTORS:
            try:
                found_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                if found_btn.is_displayed():
                    btn = found_btn
                    break
            except NoSuchElementException:
                continue
        
        if btn is None:
            try:
                btn = self.driver.find_element(
                    By.XPATH, "//button[contains(.,'Откликнуться')]"
                )
            except NoSuchElementException:
                pass
        
        if btn is None:
            return False
        
        self.helper.safe_click(btn)
        time.sleep(0.5)
        
        new_url = self.driver.current_url
        if new_url != current_url:
            if any(x in new_url for x in ['test', 'vacancy_response', 'startedWithQuestion=true']):
                return False
            if '/vacancy/' in new_url and 'vacancy_response' not in new_url:
                return True
        
        if modal:
            try:
                WebDriverWait(self.driver, 1.5).until(EC.staleness_of(modal))
                return True
            except TimeoutException:
                pass
        
        time.sleep(0.3)
        try:
            self.driver.find_element(By.CSS_SELECTOR, "[data-qa*='vacancy-response']")
            return False
        except NoSuchElementException:
            return True
