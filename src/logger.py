"""
Логирование для HH Auto Applier
"""

from typing import Optional


class Logger:
    """Простой логгер с поддержкой режима отладки и цветного вывода"""
    
    # ANSI цвета для терминала
    COLORS = {
        'reset': '\033[0m',
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'gray': '\033[90m',
    }
    
    def __init__(self, debug_mode: bool = False, use_colors: bool = True):
        self.debug_mode = debug_mode
        self.use_colors = use_colors
    
    def _colorize(self, text: str, color: str) -> str:
        """Добавляет цвет к тексту"""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"
    
    def debug(self, message: str) -> None:
        """Выводит сообщение только в режиме отладки"""
        if self.debug_mode:
            print(self._colorize(f"[DEBUG] {message}", 'gray'))
    
    def info(self, message: str) -> None:
        """Выводит информационное сообщение"""
        print(self._colorize(f"[INFO] {message}", 'blue'))
    
    def success(self, message: str) -> None:
        """Выводит сообщение об успехе"""
        print(self._colorize(f"[OK] {message}", 'green'))
    
    def warn(self, message: str) -> None:
        """Выводит предупреждение"""
        print(self._colorize(f"[WARN] {message}", 'yellow'))
    
    def error(self, message: str) -> None:
        """Выводит сообщение об ошибке"""
        print(self._colorize(f"[ERROR] {message}", 'red'))
    
    def card(self, message: str) -> None:
        """Выводит информацию о карточке вакансии"""
        print(self._colorize(f"[CARD] {message}", 'cyan'))
    
    def search(self, message: str) -> None:
        """Выводит информацию о поиске"""
        print(self._colorize(f"[SEARCH] {message}", 'magenta'))
    
    def divider(self, char: str = "=", length: int = 60) -> None:
        """Выводит разделитель"""
        if self.debug_mode:
            print(char * length)


# Глобальный экземпляр логгера (будет настроен при загрузке конфига)
logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Возвращает глобальный экземпляр логгера"""
    global logger
    if logger is None:
        logger = Logger()
    return logger


def setup_logger(debug_mode: bool = False, use_colors: bool = True) -> Logger:
    """Настраивает и возвращает глобальный логгер"""
    global logger
    logger = Logger(debug_mode=debug_mode, use_colors=use_colors)
    return logger
