import logging
from typing import Optional, Dict, Any

class SurrealEngineLogger:
    """Logger for SurrealEngine.
    
    This class provides a centralized logging system for SurrealEngine,
    with support for different log levels and configurable handlers.
    
    Attributes:
        logger: The underlying logger instance
    """
    
    def __init__(self, name: str = 'surrealengine', level: int = logging.INFO):
        """Initialize a SurrealEngineLogger.
        
        Args:
            name: The name of the logger
            level: The log level to use
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Add a console handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            
    def set_level(self, level: int):
        """Set the log level.
        
        Args:
            level: The log level to use
        """
        self.logger.setLevel(level)
        
    def add_file_handler(self, filename: str, level: Optional[int] = None):
        """Add a file handler to the logger.
        
        Args:
            filename: The name of the log file
            level: The log level for the file handler (defaults to logger level)
        """
        handler = logging.FileHandler(filename)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        if level is not None:
            handler.setLevel(level)
        self.logger.addHandler(handler)
        
    def debug(self, msg: str, *args, **kwargs):
        """Log a debug message.
        
        Args:
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.debug(msg, *args, **kwargs)
        
    def info(self, msg: str, *args, **kwargs):
        """Log an info message.
        
        Args:
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.info(msg, *args, **kwargs)
        
    def warning(self, msg: str, *args, **kwargs):
        """Log a warning message.
        
        Args:
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.warning(msg, *args, **kwargs)
        
    def error(self, msg: str, *args, **kwargs):
        """Log an error message.
        
        Args:
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.error(msg, *args, **kwargs)
        
    def critical(self, msg: str, *args, **kwargs):
        """Log a critical message.
        
        Args:
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.critical(msg, *args, **kwargs)
        
    def exception(self, msg: str, *args, **kwargs):
        """Log an exception message.
        
        Args:
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.exception(msg, *args, **kwargs)
        
    def log(self, level: int, msg: str, *args, **kwargs):
        """Log a message at the specified level.
        
        Args:
            level: The log level to use
            msg: The message to log
            *args: Additional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self.logger.log(level, msg, *args, **kwargs)


# Create a singleton instance of the logger
logger = SurrealEngineLogger()