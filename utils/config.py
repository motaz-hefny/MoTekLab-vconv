"""
Configuration Management Module

Handles reading, writing, and managing application configuration.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager for vconv.

    Stores settings in JSON format at ~/.config/vconv/vconv.conf
    """

    DEFAULT_CONFIG = {
        'general': {
            'language': 'en',
            'theme': 'dark',
            'check_updates': True,
            'log_level': 'info'
        },
        'defaults': {
            'encoder': 'auto',
            'quality': 23,
            'audio_encoder': 'copy',
            'audio_bitrate': 128,
            'format': 'mp4',
            'output_dir': 'source',
            'conflict_resolution': 'ask'
        },
        'ui': {
            'window_width': 900,
            'window_height': 650,
            'show_toolbar': True,
            'confirm_delete': True
        },
        'processing': {
            'parallel_jobs': 1,
            'show_parallel_warning': True,
            'auto_delete_temp': True
        }
    }

    def __init__(self, config_path: str = None):
        """Initialize configuration."""
        if config_path is None:
            config_dir = Path.home() / ".config" / "vconv"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = str(config_dir / "vconv.conf")

        self.config_path = config_path
        self.config = {}
        self._loaded = False

    def load(self) -> bool:
        """Load configuration from file."""
        if self._loaded:
            return True

        if not os.path.exists(self.config_path):
            logger.info(f"Config file not found, using defaults: {self.config_path}")
            self.config = self.DEFAULT_CONFIG.copy()
            self._loaded = True
            return False

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"Configuration loaded from: {self.config_path}")
            self._loaded = True
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            self.config = self.DEFAULT_CONFIG.copy()
            self._loaded = True
            return False
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self.config = self.DEFAULT_CONFIG.copy()
            self._loaded = True
            return False

    def save(self) -> bool:
        """Save configuration to file."""
        try:
            # Ensure directory exists
            config_dir = Path(self.config_path).parent
            config_dir.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logger.info(f"Configuration saved to: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            section: Config section (e.g., 'general', 'defaults')
            key: Key within section
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        if not self._loaded:
            self.load()

        if section in self.config:
            return self.config[section].get(key, default)
        return default

    def set(self, section: str, key: str, value: Any) -> bool:
        """
        Set a configuration value.

        Args:
            section: Config section
            key: Key within section
            value: Value to set

        Returns:
            True if successful
        """
        if not self._loaded:
            self.load()

        if section not in self.config:
            self.config[section] = {}

        self.config[section][key] = value
        return True

    def update(self, section: str, values: dict) -> bool:
        """
        Update multiple values in a section.

        Args:
            section: Config section
            values: Dictionary of key-value pairs

        Returns:
            True if successful
        """
        if not self._loaded:
            self.load()

        if section not in self.config:
            self.config[section] = {}

        self.config[section].update(values)
        return True

    def get_section(self, section: str) -> dict:
        """Get entire configuration section."""
        if not self._loaded:
            self.load()
        return self.config.get(section, {})

    def reset_to_defaults(self):
        """Reset configuration to default values."""
        self.config = self.DEFAULT_CONFIG.copy()
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        logger.info("Configuration reset to defaults")

    def export(self, filepath: str) -> bool:
        """Export configuration to a file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration exported to: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False

    def import_config(self, filepath: str) -> bool:
        """Import configuration from a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported = json.load(f)

            # Validate structure
            for section in ['general', 'defaults', 'ui']:
                if section not in imported:
                    logger.error(f"Invalid config: missing '{section}'")
                    return False

            self.config = imported
            self.save()
            logger.info(f"Configuration imported from: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return False


# Singleton instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get global config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


if __name__ == "__main__":
    # Test configuration
    logging.basicConfig(level=logging.DEBUG)

    config = Config()

    # Load
    config.load()
    print("Config loaded")

    # Get values
    print(f"Language: {config.get('general', 'language')}")
    print(f"Theme: {config.get('general', 'theme')}")
    print(f"Default encoder: {config.get('defaults', 'encoder')}")

    # Set value
    config.set('general', 'language', 'ar')
    config.save()

    # Reset
    config.reset_to_defaults()
    print("Config reset")