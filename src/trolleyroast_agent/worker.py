import logging

from trolleyroast_agent.core.logger import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    logger.info("Starting worker...")


if __name__ == "__main__":
    main()
