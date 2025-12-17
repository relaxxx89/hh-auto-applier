"""
Вспомогательные методы для работы с Selenium
"""

import time
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)


class SeleniumHelper:
    """Вспомогательные методы для работы с Selenium"""
    
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
    
    def safe_click(self, element) -> None:
        """Безопасный клик с fallback на JavaScript"""
        try:
            element.click()
            return
        except ElementClickInterceptedException:
            pass
        
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            element.click()
            return
        except ElementClickInterceptedException:
            self.driver.execute_script("arguments[0].click();", element)
    
    def find_element_safe(self, selector: str, timeout: float = 0.5) -> Optional[any]:
        """Безопасный поиск элемента с ожиданием"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            return None
    
    def find_elements_safe(self, selector: str) -> List:
        """Безопасный поиск нескольких элементов"""
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return []
    
    def find_by_selectors(self, selectors: List[str], parent=None) -> Optional[any]:
        """Пробует найти элемент по списку селекторов"""
        target = parent or self.driver
        for selector in selectors:
            try:
                element = target.find_element(By.CSS_SELECTOR, selector)
                if element:
                    return element
            except NoSuchElementException:
                continue
        return None
    
    def wait_for_element(self, selector: str, timeout: float = 1.0) -> Optional[any]:
        """Ожидает появления элемента"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            return None
    
    def wait_for_staleness(self, element, timeout: float = 0.5) -> bool:
        """Ожидает исчезновения элемента"""
        try:
            WebDriverWait(self.driver, timeout).until(EC.staleness_of(element))
            return True
        except TimeoutException:
            return False
    
    def scroll_to_element(self, element) -> None:
        """Прокручивает к элементу"""
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        time.sleep(0.1)
