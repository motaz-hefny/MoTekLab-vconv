"""
Internationalization (i18n) Module

Supports multiple languages: English, Classical Arabic, Egyptian Arabic.
"""

import json
import os
import copy
import logging
from pathlib import Path
from typing import Optional, Dict


logger = logging.getLogger(__name__)


class I18n:
    """
    Internationalization handler for vconv.

    Loads translation files and provides translation functions.
    """

    # Supported languages
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'ar': 'العربية',
        'ar_eg': 'مصرى'
    }

    def __init__(self, lang: str = 'en', locales_dir: str = None):
        """
        Initialize i18n.

        Args:
            lang: Language code (en, ar, ar_eg)
            locales_dir: Directory containing locale files
        """
        self._requested_lang = lang
        self.lang = lang
        self._lang_resolved = lang
        self.translations: Dict[str, str] = {}
        self.is_rtl = False

        if locales_dir is None:
            # Default to project locales directory
            project_root = Path(__file__).parent.parent
            locales_dir = str(project_root / "locales")

        self.locales_dir = Path(locales_dir)
        self._load_translations()

    def _load_translations(self):
        """Load translations for current language."""
        # Try to load language-specific file first
        # Then fall back to base language

        lang_file = self.locales_dir / f"{self.lang}.json"
        base_file = self.locales_dir / f"{self.lang.split('_')[0]}.json"

        loaded = False

        if lang_file.exists():
            loaded = self._load_file(lang_file)
            self._lang_resolved = self.lang
        elif base_file.exists():
            loaded = self._load_file(base_file)
            self._lang_resolved = self.lang.split('_')[0]
        else:
            logger.warning(f"No translation file found for: {self.lang}")
            # Load English as fallback
            en_file = self.locales_dir / "en.json"
            if en_file.exists():
                loaded = self._load_file(en_file)
                self._lang_resolved = 'en'

        # Determine RTL
        self.is_rtl = self._lang_resolved in ['ar', 'ar_eg']

        if loaded:
            logger.info(f"Loaded translations for: {self._lang_resolved} (RTL: {self.is_rtl})")

    def _load_file(self, filepath: Path) -> bool:
        """Load translation file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.translations = data
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return False

    def t(self, key: str, default: str = None) -> str:
        """
        Translate a key.

        Args:
            key: Translation key (e.g., 'menu.file')
            default: Default value if key not found

        Returns:
            Translated string or default
        """
        # Handle nested keys
        keys = key.split('.')
        value = self.translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default or key

        return value if isinstance(value, str) else (default or key)

    def get_available_languages(self) -> Dict[str, str]:
        """Get dictionary of available languages."""
        return self.SUPPORTED_LANGUAGES.copy()

    def is_language_rtl(self, lang: str = None) -> bool:
        """Check if language is RTL."""
        check_lang = lang or self.lang
        return check_lang in ['ar', 'ar_eg']

    def set_language(self, lang: str) -> bool:
        """Change current language."""
        if lang not in self.SUPPORTED_LANGUAGES:
            logger.warning(f"Unsupported language: {lang}")
            return False

        # Test-load the new language before swapping
        test = I18n(lang, locales_dir=str(self.locales_dir))
        if not test.translations:
            logger.warning(f"Failed to load translations for: {lang}")
            return False

        old_lang = self._requested_lang
        self._requested_lang = lang
        self.lang = lang
        self._lang_resolved = test._lang_resolved
        self.translations = test.translations
        self.is_rtl = test.is_rtl

        logger.info(f"Language changed: {old_lang} -> {self._lang_resolved}")
        return True


# Helper function for template strings
def translate_template(template: str, **kwargs) -> str:
    """
    Translate a template string with placeholders.

    Example:
        translate_template("Hello {name}", name="World")
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Missing template value: {e}")
        return template


# Singleton instance
_i18n_instance: Optional[I18n] = None


def get_i18n(lang: str = 'en') -> I18n:
    """Get global i18n instance."""
    global _i18n_instance
    if _i18n_instance is None or _i18n_instance._requested_lang != lang:
        _i18n_instance = I18n(lang=lang)
    return _i18n_instance


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test English
    i18n = I18n('en')
    print(f"English: {i18n.t('app.title', 'vconv')}")
    print(f"RTL: {i18n.is_rtl}")

    # Test Arabic
    i18n_ar = I18n('ar')
    print(f"Arabic RTL: {i18n_ar.is_rtl}")
    print(f"Arabic: {i18n_ar.t('app.title', 'vconv')}")

    # Test missing key
    print(f"Missing key: {i18n.t('missing.key', 'Default Value')}")