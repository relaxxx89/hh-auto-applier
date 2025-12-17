"""
Основной класс бота для HH.ru
"""

import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException
)

from .config import Config
from .logger import Logger, get_logger
from .storage import VacancyStorage
from .selenium_helper import SeleniumHelper
from .vacancy import VacancyCard
from .modal import ApplicationModal


class HHApplierBot:
    """Основной класс для автоматического отклика на вакансии HH.ru"""
    
    VACANCY_CARD_SELECTORS = [
        "[data-qa='vacancy-serp__vacancy']",
        ".serp-item",
        "[data-qa='serp-item']",
        "div[data-vacancy-id]",
    ]
    
    NEXT_PAGE_SELECTORS = [
        "[data-qa='pager-next']",
        "a[data-qa='pager-next']",
        ".bloko-pagination__next",
        "a.bloko-button[aria-label='Следующая страница']",
    ]
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = Config.load(config_path)
        self.logger = Logger(debug=self.config.debug)
        self.storage = VacancyStorage(
            self.config.processed_file,
            self.config.skipped_file
        )
        self.driver: Optional[webdriver.Chrome] = None
        self.helper: Optional[SeleniumHelper] = None
        self.stats = {
            "applied": 0,
            "skipped": 0,
            "errors": 0,
        }
    
    def setup_driver(self):
        """Настраивает Chrome WebDriver"""
        chrome_options = Options()
        
        # Профиль Chrome для сохранения сессии
        if self.config.chrome_profile:
            chrome_options.add_argument(f"user-data-dir={self.config.chrome_profile}")
            chrome_options.add_argument(f"profile-directory={self.config.profile_name}")
        
        # Отключаем обнаружение автоматизации
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Дополнительные настройки
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        
        if self.config.headless:
            chrome_options.add_argument("--headless=new")
        
        try:
            if self.config.chromedriver_path:
                service = Service(executable_path=self.config.chromedriver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            self.helper = SeleniumHelper(self.driver, self.config.timeouts)
            self.logger.success("Chrome WebDriver запущен")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка запуска WebDriver: {e}")
            return False
    
    def is_authorized(self) -> bool:
        """Проверяет, авторизован ли пользователь"""
        try:
            # Ищем элементы авторизованного пользователя
            auth_selectors = [
                "[data-qa='mainmenu_myResumes']",
                "[data-qa='mainmenu_applicantProfile']",
                ".applicant-resumes-title",
            ]
            
            for selector in auth_selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if el:
                        return True
                except NoSuchElementException:
                    continue
            
            return False
        except Exception:
            return False
    
    def wait_for_auth(self, timeout: int = 300):
        """Ждет авторизации пользователя"""
        self.logger.info("⏳ Ожидание авторизации...")
        self.logger.info("   Пожалуйста, войдите в аккаунт HH.ru в открывшемся браузере")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_authorized():
                self.logger.success("Авторизация успешна!")
                return True
            time.sleep(2)
        
        self.logger.error("Таймаут авторизации")
        return False
    
    def process_query(self, query: dict):
        """Обрабатывает один поисковый запрос"""
        url = query.get("url")
        keywords = query.get("keywords", [])
        query_name = query.get("name", url[:50] if url else "unknown")
        
        if not url:
            self.logger.warn(f"Пропуск запроса без URL: {query_name}")
            return
        
        self.logger.info(f"📌 Запрос: {query_name}")
        self.logger.debug(f"   URL: {url}")
        self.logger.debug(f"   Ключевые слова: {keywords}")
        
        try:
            self.driver.get(url)
            time.sleep(self.config.page_load_delay)
            
            page_num = 1
            while True:
                self.logger.info(f"   Страница {page_num}")
                
                vacancies_processed = self.process_vacancy_page(keywords)
                
                if vacancies_processed == 0:
                    self.logger.debug("   Нет вакансий на странице")
                    break
                
                # Пытаемся перейти на следующую страницу
                if not self.go_to_next_page():
                    self.logger.debug("   Это последняя страница")
                    break
                
                page_num += 1
                time.sleep(self.config.delay_between_pages)
        
        except Exception as e:
            self.logger.error(f"Ошибка обработки запроса {query_name}: {e}")
    
    def process_vacancy_page(self, keywords: list) -> int:
        """Обрабатывает одну страницу с вакансиями"""
        cards = self.get_vacancy_cards()
        
        if not cards:
            return 0
        
        processed = 0
        
        for card_element in cards:
            try:
                card = VacancyCard(card_element, self.helper)
                
                vacancy_id = card.id
                if not vacancy_id:
                    continue
                
                # Пропускаем уже обработанные
                if self.storage.is_processed(vacancy_id):
                    self.logger.debug(f"   ⏭️ Уже обработана: {card.title[:40]}")
                    continue
                
                if self.storage.is_skipped(vacancy_id):
                    self.logger.debug(f"   ⏭️ Уже пропущена: {card.title[:40]}")
                    continue
                
                # Проверяем ключевые слова (если заданы)
                if keywords and not card.is_suitable(keywords):
                    self.storage.add_skipped(
                        vacancy_id, card.title, "не соответствует ключевым словам"
                    )
                    self.logger.debug(f"   ⏭️ Не подходит по ключевым: {card.title[:40]}")
                    self.stats["skipped"] += 1
                    continue
                
                # Пробуем откликнуться
                result = self.apply_to_vacancy(card)
                
                if result:
                    self.storage.add_processed(vacancy_id, card.title, "успешно")
                    self.stats["applied"] += 1
                else:
                    self.storage.add_skipped(vacancy_id, card.title, "ошибка отклика")
                    self.stats["skipped"] += 1
                
                processed += 1
                time.sleep(self.config.delay_between_applies)
            
            except StaleElementReferenceException:
                self.logger.debug("   Элемент устарел, пропуск")
                continue
            except Exception as e:
                self.logger.debug(f"   Ошибка обработки карточки: {e}")
                self.stats["errors"] += 1
                continue
        
        return processed
    
    def get_vacancy_cards(self) -> list:
        """Получает список карточек вакансий на странице"""
        for selector in self.VACANCY_CARD_SELECTORS:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    self.logger.debug(f"   Найдено {len(cards)} вакансий ({selector})")
                    return cards
            except Exception:
                continue
        return []
    
    def apply_to_vacancy(self, card: VacancyCard) -> bool:
        """Откликается на вакансию"""
        btn = card.get_apply_button()
        if not btn:
            self.logger.debug(f"   Кнопка отклика не найдена: {card.title[:40]}")
            return False
        
        # Кликаем на кнопку отклика
        if not self.helper.safe_click(btn):
            return False
        
        # Ожидаем модальное окно
        modal = ApplicationModal(self.driver, self.helper, self.config.timeouts)
        
        if not modal.wait_for_modal():
            self.logger.debug("   Модальное окно не появилось")
            return False
        
        # Проверяем на вопросы
        can_apply, reason = modal.handle_questions()
        if not can_apply:
            self.logger.debug(f"   {reason}")
            modal.close()
            return False
        
        # Выбираем резюме
        resume = modal.select_resume(self.config.resume_rules, card.title)
        if resume:
            self.logger.debug(f"   Резюме: {resume[:30]}")
        
        # Отправляем отклик
        if modal.submit():
            self.logger.success(f"✅ Отклик отправлен: {card.title[:50]}")
            time.sleep(1.5)
            
            # Закрываем модалку если еще открыта
            if modal.is_open():
                modal.close()
            
            return True
        
        modal.close()
        return False
    
    def go_to_next_page(self) -> bool:
        """Переходит на следующую страницу"""
        btn = self.helper.find_by_selectors(self.NEXT_PAGE_SELECTORS)
        if btn:
            try:
                self.helper.safe_click(btn)
                time.sleep(self.config.page_load_delay)
                return True
            except Exception:
                pass
        return False
    
    def run(self):
        """Запускает бота"""
        self.logger.info("=" * 50)
        self.logger.info("🤖 HH.ru Auto Applier Bot")
        self.logger.info("=" * 50)
        
        # Запускаем драйвер
        if not self.setup_driver():
            return
        
        try:
            # Открываем HH.ru
            self.driver.get("https://hh.ru")
            time.sleep(2)
            
            # Проверяем/ждем авторизацию
            if not self.is_authorized():
                if not self.wait_for_auth():
                    return
            else:
                self.logger.success("Уже авторизованы!")
            
            # Обрабатываем запросы
            for i, query in enumerate(self.config.search_queries, 1):
                self.logger.info(f"\n{'='*40}")
                self.logger.info(f"Запрос {i}/{len(self.config.search_queries)}")
                self.process_query(query)
            
            # Итоговая статистика
            self.print_stats()
        
        except KeyboardInterrupt:
            self.logger.warn("\n⛔ Прервано пользователем")
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
        finally:
            self.cleanup()
    
    def print_stats(self):
        """Выводит статистику"""
        self.logger.info("\n" + "=" * 50)
        self.logger.info("📊 СТАТИСТИКА")
        self.logger.info("=" * 50)
        self.logger.info(f"   ✅ Откликов отправлено: {self.stats['applied']}")
        self.logger.info(f"   ⏭️ Пропущено: {self.stats['skipped']}")
        self.logger.info(f"   ❌ Ошибок: {self.stats['errors']}")
        self.logger.info(f"   📁 Всего обработано: {len(self.storage.processed)}")
        self.logger.info(f"   📁 Всего пропущено: {len(self.storage.skipped)}")
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.storage.save()
        
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Chrome закрыт")
            except Exception:
                pass
