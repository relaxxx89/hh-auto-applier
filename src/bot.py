"""
Основной класс бота для HH.ru
Адаптирован из main_refactored.py
"""

import time
from pathlib import Path
from typing import Optional, List

from selenium import webdriver
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
from .logger import Logger
from .storage import VacancyStorage
from .selenium_helper import SeleniumHelper
from .vacancy import VacancyCard
from .modal import ApplicationModal


class HHApplierBot:
    """Главный класс бота для автоматических откликов"""
    
    VACANCY_CARD_SELECTOR = "[data-qa='vacancy-serp__vacancy']"
    
    AUTH_SELECTORS = [
        "[data-qa='mainmenu_applicantProfile']",
        "[data-qa='mainmenu__profile']",
        "a[data-qa='mainmenu_myResumes']",
        "button[data-qa='mainmenu_applicantProfile']",
        "[class*='account-popup']",
        "a[href*='/applicant/resumes']",
    ]
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = Config.load(config_path)
        self.logger = Logger(debug_mode=self.config.debug)
        self.driver: Optional[webdriver.Chrome] = None
        self.helper: Optional[SeleniumHelper] = None
        self.modal: Optional[ApplicationModal] = None
        self.storage: Optional[VacancyStorage] = None
    
    def _create_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        chrome_options.add_argument("start-maximized")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        chrome_options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2
        })
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        if self.config.chrome_profile:
            profile_dir = Path(self.config.chrome_profile).absolute()
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            chrome_options.add_argument(f"--profile-directory={self.config.profile_name}")
        
        if self.config.headless:
            chrome_options.add_argument("--headless=new")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(self.config.timeouts.implicit_wait)
        return driver
    
    def _is_logged_in(self) -> bool:
        for selector in self.AUTH_SELECTORS:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    self.logger.debug(f"Найден элемент авторизации: {selector}")
                    return True
            except NoSuchElementException:
                continue
        self.logger.debug("Авторизация не обнаружена")
        return False
    
    def _wait_for_login(self) -> bool:
        print("\n" + "=" * 60)
        print("🔐 ТРЕБУЕТСЯ АВТОРИЗАЦИЯ")
        print("=" * 60)
        print("👉 Войди в свой аккаунт в открывшемся окне браузера")
        print("👉 После успешного входа вернись сюда и нажми Enter")
        print("=" * 60)
        input("\n⏎ Нажми Enter после авторизации... ")
        
        self.driver.refresh()
        time.sleep(self.config.timeouts.page_load_wait)
        
        if not self._is_logged_in():
            print("\n❌ Авторизация не обнаружена!")
            print("\n📋 Проверь, что:")
            print("   1. ✓ Прошел авторизацию полностью")
            print("   2. ✓ Страница hh.ru загрузилась")
            print("   3. ✓ Видишь свой профиль в правом верхнем углу")
            return False
        
        print("\n✅ Авторизация успешна!")
        return True
    
    def _get_vacancy_cards(self) -> List:
        return self.driver.find_elements(By.CSS_SELECTOR, self.VACANCY_CARD_SELECTOR)
    
    def _process_card(self, card_element) -> None:
        if self.config.debug:
            print("\n" + "=" * 80)
        
        card = VacancyCard(card_element, self.helper)
        vacancy_id = card.id
        title = card.title
        
        if not title:
            self.logger.debug("Не удалось получить заголовок")
            return
        
        if self.storage.is_processed(vacancy_id):
            self.logger.debug(f"✓ Уже откликнулись: {title[:50]}...")
            return
        
        if self.storage.is_skipped(vacancy_id):
            self.logger.debug(f"⊗ Уже пропущено: {title[:50]}...")
            return
        
        # Показываем вакансию красиво
        print(f"\n  📋 {title}")
        
        if self.config.allowed_keywords and not card.is_suitable(self.config.allowed_keywords):
            print("     ⊗ Пропуск: не подходит по ключевым словам")
            self.storage.mark_skipped(vacancy_id, title, "not_suitable_keywords")
            return
        
        btn = card.get_apply_button()
        if not btn:
            print("     ✓ Уже откликались ранее")
            self.storage.mark_processed(vacancy_id, title, "already_applied")
            return
        
        search_page_url = self.driver.current_url
        
        if not self.modal.open(btn):
            current_url = self.driver.current_url
            if current_url != search_page_url:
                print("     ⊗ Пропуск: обязательный тест (редирект)")
                self.storage.mark_skipped(vacancy_id, title, "mandatory_test_redirect")
                self.driver.back()
                time.sleep(0.2)
            else:
                print("     ⚠ Не удалось открыть форму отклика")
            return
        
        try:
            if self.modal.has_mandatory_test():
                print("     ⊗ Пропуск: обязательный тест")
                self.storage.mark_skipped(vacancy_id, title, "mandatory_test")
                self.modal.close()
                # Убеждаемся, что вернулись на страницу поиска
                if 'search/vacancy' not in self.driver.current_url:
                    self.driver.back()
                    time.sleep(0.5)
                return
            
            self.modal.choose_resume(title, self.config.resume_rules)
            
            added_letter = False
            if self.modal.is_cover_letter_required():
                added_letter = self.modal.add_cover_letter(self.config.cover_letter)
                if not added_letter:
                    print("     ⊗ Пропуск: не удалось добавить сопроводительное письмо")
                    self.storage.mark_skipped(vacancy_id, title, "cover_letter_failed")
                    self.modal.close()
                    if 'search/vacancy' not in self.driver.current_url:
                        self.driver.back()
                        time.sleep(0.5)
                    return
            
            success = self.modal.submit()
            
            if success:
                letter_icon = '📝' if added_letter else '📄'
                print(f"     ✅ Отклик отправлен {letter_icon}")
                self.storage.mark_processed(vacancy_id, title, "applied", added_letter)
            else:
                print("     ⚠ Не удалось отправить отклик")
                self.storage.mark_skipped(vacancy_id, title, "submit_failed")
            
            if 'search/vacancy' not in self.driver.current_url:
                self.driver.back()
                time.sleep(0.5)
                
        except Exception as e:
            error_msg = str(e)[:80]
            print(f"     ❌ Ошибка: {error_msg}")
            self.storage.mark_skipped(vacancy_id, title, f"error: {str(e)[:100]}")
        finally:
            self.modal.close()
            if 'search/vacancy' not in self.driver.current_url:
                self.driver.back()
                time.sleep(0.5)
    
    def _get_next_page_url(self, current_page: int) -> str:
        """Формирует URL следующей страницы"""
        current_url = self.driver.current_url
        
        # Если в URL уже есть параметр page, заменяем его
        if 'page=' in current_url:
            import re
            next_url = re.sub(r'page=\d+', f'page={current_page + 1}', current_url)
        else:
            # Добавляем параметр page
            separator = '&' if '?' in current_url else '?'
            next_url = f"{current_url}{separator}page={current_page + 1}"
        
        return next_url
    
    def _has_next_page(self, current_page: int) -> bool:
        """Проверяет наличие следующей страницы через пагинацию"""
        time.sleep(0.3)
        
        try:
            # Ищем все ссылки на страницы в пагинаторе
            page_links = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "[data-qa='pager-page'], .bloko-button[data-page], a[data-page]"
            )
            
            if page_links:
                # Проверяем, есть ли ссылка на следующую страницу
                for link in page_links:
                    try:
                        page_num = link.get_attribute("data-page") or link.text.strip()
                        if page_num and page_num.isdigit() and int(page_num) == current_page + 1:
                            self.logger.debug(f"✓ Найдена страница {current_page + 1}")
                            return True
                    except:
                        continue
            
            # Альтернатива - проверяем максимальный номер страницы
            max_page_elem = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[data-qa='pager-page']:last-of-type, .bloko-button[data-page]:last-of-type"
            )
            
            if max_page_elem:
                try:
                    max_page = int(max_page_elem[-1].text.strip())
                    has_next = current_page < max_page
                    if has_next:
                        self.logger.debug(f"✓ Есть ещё страницы (текущая: {current_page}, максимум: {max_page})")
                    else:
                        self.logger.debug(f"✗ Достигнута последняя страница (текущая: {current_page}, максимум: {max_page})")
                    return has_next
                except:
                    pass
                    
        except Exception as e:
            self.logger.debug(f"✗ Ошибка проверки пагинации: {e}")
        
        self.logger.debug("✗ Следующая страница не найдена")
        return False
    
    def _go_to_next_page(self, current_page: int) -> bool:
        """Переходит на следующую страницу результатов"""
        try:
            # Формируем URL следующей страницы
            next_url = self._get_next_page_url(current_page)
            self.logger.debug(f"Переход на: {next_url}")
            
            # Переходим на следующую страницу
            self.driver.get(next_url)
            time.sleep(self.config.timeouts.page_load_wait)
            
            # Ждем загрузки новых карточек
            WebDriverWait(self.driver, self.config.timeouts.page_load_wait * 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.VACANCY_CARD_SELECTOR))
            )
            
            self.logger.debug(f"✓ Успешно перешли на страницу {current_page + 1}")
            return True
            
        except (TimeoutException, Exception) as e:
            self.logger.debug(f"✗ Не удалось перейти на следующую страницу: {e}")
            return False
    
    def _process_search_query(self, query: dict) -> None:
        url = query.get("url")
        name = query.get("name", url[:50] if url else "unknown")
        
        if not url:
            self.logger.warn(f"⚠ Пропуск запроса без URL: {name}")
            return
        
        print(f"\n🔍 Поиск: {name}")
        self.driver.get(url)
        
        try:
            WebDriverWait(self.driver, self.config.timeouts.page_load_wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.VACANCY_CARD_SELECTOR))
            )
        except TimeoutException:
            print("  ⚠ Нет вакансий или проблема с доступом")
            return
        
        page_num = 1
        max_pages = self.config.max_pages if hasattr(self.config, 'max_pages') else 5
        total_processed_in_query = 0
        total_skipped_in_query = 0
        
        while page_num <= max_pages:
            print(f"\n  📄 Страница {page_num}/{max_pages}")
            
            cards = self._get_vacancy_cards()
            if not cards:
                print("  ⚠ Карточки не найдены")
                break
            
            print(f"  📊 Вакансий на странице: {len(cards)}")
            
            page_processed = 0
            page_skipped = 0
            page_already_seen = 0
            
            for i in range(len(cards)):
                try:
                    cards = self._get_vacancy_cards()
                    if i >= len(cards):
                        break
                    
                    # Проверяем, была ли вакансия уже обработана
                    card = cards[i]
                    try:
                        vacancy_id = card.get_attribute("data-vacancy-id") or card.get_attribute("id")
                        if vacancy_id:
                            vacancy_id = vacancy_id.replace("vacancy_", "")
                            if self.storage.is_processed(vacancy_id) or self.storage.is_skipped(vacancy_id):
                                page_already_seen += 1
                                self._process_card(card)
                                continue
                    except:
                        pass
                    
                    before_processed = self.storage.get_stats()[0]
                    before_skipped = self.storage.get_stats()[1]
                    
                    self._process_card(cards[i])
                    
                    after_processed = self.storage.get_stats()[0]
                    after_skipped = self.storage.get_stats()[1]
                    
                    if after_processed > before_processed:
                        page_processed += 1
                    elif after_skipped > before_skipped:
                        page_skipped += 1
                        
                except StaleElementReferenceException:
                    self.logger.debug(f"⚠ Stale element at index {i}, пропускаем")
                    continue
                except Exception as e:
                    print(f"  ❌ Ошибка при обработке карточки {i}: {e}")
                    page_skipped += 1
                    continue
            
            total_processed_in_query += page_processed
            total_skipped_in_query += page_skipped
            
            if page_processed > 0 or page_skipped > 0 or page_already_seen > 0:
                summary = f"  📈 На странице: откликнулись {page_processed}, пропущено {page_skipped}"
                if page_already_seen > 0:
                    summary += f", уже обработано ранее {page_already_seen}"
                print(summary)
            
            # Убеждаемся, что мы на странице поиска
            if 'search/vacancy' not in self.driver.current_url:
                self.logger.debug("⚠ Не на странице поиска, возвращаемся...")
                self.driver.back()
                time.sleep(1)
            
            # Ждём, чтобы страница стабилизировалась
            time.sleep(0.5)
            
            # Переходим на следующую страницу
            if page_num < max_pages:
                # Проверяем наличие следующей страницы
                has_next = self._has_next_page(page_num)
                
                if has_next:
                    print(f"\n  ➡️  Переход на страницу {page_num + 1}...")
                    if not self._go_to_next_page(page_num):
                        print("  ⚠ Не удалось перейти на следующую страницу (технический сбой)")
                        break
                    page_num += 1
                else:
                    if page_num == 1:
                        print(f"\n  💡 По этому запросу всего 1 страница результатов")
                    else:
                        print(f"\n  ✓ Обработано страниц: {page_num} из {max_pages}")
                        print("  📌 Больше страниц не найдено")
                    break
            else:
                print(f"\n  🛑 Достигнут лимит страниц ({max_pages})")
                print("  💡 Увеличь max_pages в config.yaml, если хочешь просматривать больше")
                break
        
        # Итоги по запросу
        if total_processed_in_query > 0 or total_skipped_in_query > 0:
            print(f"\n  📊 Итого по запросу '{name}':")
            print(f"     ✅ Откликнулись: {total_processed_in_query}")
            print(f"     ⊗ Пропущено: {total_skipped_in_query}")
    
    def run(self) -> None:
        print("\n" + "=" * 60)
        print("🤖 HH.ru Auto Applier Bot")
        print("=" * 60)
        print("⚙️  Настройка Chrome WebDriver...")
        
        try:
            self.driver = self._create_driver()
        except Exception as e:
            print(f"❌ Ошибка запуска Chrome: {e}")
            return
        
        print("✅ Chrome WebDriver запущен")
        
        self.helper = SeleniumHelper(self.driver)
        self.modal = ApplicationModal(self.driver, self.helper, self.config.timeouts)
        self.storage = VacancyStorage(
            self.config.processed_file,
            self.config.skipped_file,
            self.config.save_interval
        )
        
        try:
            print("🌐 Открываем hh.ru...")
            self.driver.get("https://hh.ru/")
            time.sleep(self.config.timeouts.page_load_wait)
            
            if not self._is_logged_in():
                if not self._wait_for_login():
                    return
            else:
                print("🔓 Уже авторизован")
            
            processed, skipped = self.storage.get_stats()
            print(f"\n📊 Статистика:")
            print(f"   ✅ Отправлено откликов: {processed}")
            print(f"   ⊗ Пропущено: {skipped}")
            
            print(f"\n🤖 Режим работы: АВТОНОМНЫЙ (бесконечный цикл)")
            print(f"🔍 Поисковых запросов: {len(self.config.search_queries)}")
            print(f"📄 Страниц на запрос: до {self.config.max_pages}")
            print(f"⚠️  Для остановки нажми Ctrl+C\n")
            
            cycle_num = 1
            while True:
                print(f"\n{'=' * 60}")
                print(f"🔄 ЦИКЛ #{cycle_num}")
                print(f"{'=' * 60}")
                
                for query in self.config.search_queries:
                    self._process_search_query(query)
                    self.storage.save(force=True)
                
                print("\n" + "=" * 60)
                processed, skipped = self.storage.get_stats()
                print(f"📊 Итоги цикла #{cycle_num}:")
                print(f"   ✅ Всего откликов: {processed}")
                print(f"   ⊗ Всего пропущено: {skipped}")
                print("=" * 60)
                
                cycle_num += 1
                
                # Небольшая пауза перед следующим циклом
                print(f"\n⏸️  Пауза 5 секунд перед следующим циклом...")
                time.sleep(5)
                
                print("🔄 Запускаем новый цикл...\n")
                
        except KeyboardInterrupt:
            print("\n\n⛔ Остановлено пользователем")
            processed, skipped = self.storage.get_stats()
            print(f"\n📊 Финальная статистика:")
            print(f"   ✅ Отправлено откликов: {processed}")
            print(f"   ⊗ Пропущено: {skipped}")
        finally:
            self.storage.save(force=True)
            self.driver.quit()
            print("👋 Chrome закрыт. До встречи!")
