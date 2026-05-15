#!/usr/bin/env python3
"""
vconv - Video Converter GUI
A modern video conversion application powered by HandBrakeCLI

Author: vconv Team
Version: 8.0.0
License: GPLv3
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.logging import setup_logging
from utils.config import Config
from utils.i18n import I18n
from utils.tools import DependencyChecker
from ui.main_window import MainWindow


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='vconv',
        description='Video Converter GUI - Powered by HandBrakeCLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vconv              Start application
  vconv --debug      Enable debug logging
  vconv --no-check   Skip dependency check
  vconv --reset      Reset configuration
        """
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--no-check',
        action='store_true',
        help='Skip dependency check on startup'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset configuration to defaults'
    )
    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help='Show version information'
    )
    return parser.parse_args()


def show_version():
    """Display version information."""
    print("vconv - Video Converter GUI")
    print("Version: 8.0.0")
    print("License: GPLv3")
    print("Powered by HandBrakeCLI")


def main():
    """Main entry point for vconv application."""
    args = parse_arguments()

    if args.version:
        show_version()
        sys.exit(0)

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logging(level=log_level)
    logger.info("Starting vconv v8.0.0...")

    # Load configuration
    config = Config()
    if args.reset:
        logger.info("Resetting configuration to defaults")
        config.reset_to_defaults()
    config.load()

    # Setup internationalization
    i18n = I18n(lang=config.get('general', 'language', 'en'))
    logger.info(f"Language set to: {config.get('general', 'language', 'en')}")

    # Check dependencies
    if not args.no_check:
        dep_checker = DependencyChecker()
        if not dep_checker.check_all():
            logger.warning("Some dependencies are missing")
            # Note: UI will handle the install dialog
        else:
            logger.info("All dependencies verified")

    # Launch main window
    try:
        app = MainWindow(config=config, i18n=i18n)
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Application crashed: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Application exited normally")


if __name__ == "__main__":
    main()