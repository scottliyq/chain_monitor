#!/usr/bin/env python3
"""
项目共享日志工具。
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_rotating_logger(
    logger_name: str,
    log_filename: str,
    backup_count: int = 7,
    level: int = logging.INFO,
    propagate: bool = False,
) -> logging.Logger:
    """创建带控制台和按日轮转文件处理器的 logger。"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, log_filename),
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = propagate

    return logger
