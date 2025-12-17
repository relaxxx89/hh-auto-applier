#!/usr/bin/env python3
"""
HH.ru Auto Applier Bot
======================

Автоматический отклик на вакансии hh.ru

Использование:
    python run.py                  # Запуск с config.yaml
    python run.py -c myconfig.yaml # Запуск с другим конфигом
    python run.py --debug          # Запуск в режиме отладки
"""

import argparse
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import __version__
from src.bot import HHApplierBot
from src.logger import Logger


def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description="HH.ru Auto Applier Bot - автоматический отклик на вакансии",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python run.py                    Запуск с настройками по умолчанию
  python run.py -c custom.yaml     Использовать другой файл конфигурации
  python run.py --debug            Включить режим отладки

Документация: https://github.com/your-repo/hh-auto-applier
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Путь к файлу конфигурации (по умолчанию: config.yaml)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Включить режим отладки с подробными логами"
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"HH Auto Applier {__version__}"
    )
    
    return parser.parse_args()


def check_config(config_path: str) -> bool:
    """Проверяет наличие файла конфигурации"""
    if os.path.exists(config_path):
        return True
    
    # Проверяем, есть ли example
    example_path = "config.example.yaml"
    if os.path.exists(example_path):
        print(f"\n❌ Файл конфигурации '{config_path}' не найден!")
        print(f"\n📝 Скопируйте {example_path} в {config_path} и настройте:")
        print(f"   copy {example_path} {config_path}")
        print(f"\nЗатем отредактируйте {config_path} под свои нужды.\n")
    else:
        print(f"\n❌ Файл конфигурации '{config_path}' не найден!")
        print("\n📝 Создайте config.yaml с поисковыми запросами.")
        print("   Пример структуры смотрите в README.md\n")
    
    return False


def main():
    """Главная функция"""
    args = parse_args()
    
    # Проверяем конфиг
    if not check_config(args.config):
        sys.exit(1)
    
    # Создаем и запускаем бота
    try:
        bot = HHApplierBot(config_path=args.config)
        
        # Переопределяем debug если указан флаг
        if args.debug:
            bot.config.debug = True
            bot.logger = Logger(debug=True)
        
        bot.run()
    
    except KeyboardInterrupt:
        print("\n\n⛔ Прервано пользователем")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
