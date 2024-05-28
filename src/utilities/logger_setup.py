import logging
import os
from datetime import datetime


class LoggerSetup:
    def __init__(self, log_dir='./../logs/', logger_name='composite_logger'):
        self.log_dir = log_dir
        self.logger_name = logger_name
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.INFO)
        self._setup_log_directory()
        self._setup_handlers()

    def _setup_log_directory(self):
        os.makedirs(self.log_dir, exist_ok=True)

    def _setup_handlers(self):
        # Create a log file name from timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_filename = os.path.join(self.log_dir, f'app_{timestamp}.log')

        # Create handlers
        file_handler = logging.FileHandler(log_filename)

        # Set level for handlers
        file_handler.setLevel(logging.INFO)

        # Create formatters and add them to the handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger
