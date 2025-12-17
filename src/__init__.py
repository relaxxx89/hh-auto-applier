"""
HH.ru Auto Applier - автоматический откликатель на вакансии
"""

__version__ = "1.0.0"
__author__ = "Your Name"

from .bot import HHApplierBot
from .config import Config
from .logger import Logger
from .storage import VacancyStorage

__all__ = [
    "HHApplierBot",
    "Config", 
    "Logger",
    "VacancyStorage",
    "__version__",
]
