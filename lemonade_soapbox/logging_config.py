logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },

    "handlers": {
        "console": {
            "class": 'logging.StreamHandler',
            "level": "DEBUG",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        },

        "info_file_handler": {
            "class": 'logging.handlers.TimedRotatingFileHandler',
            "level": "INFO",
            "formatter": "simple",
            "filename": "info.log",
            "when": "D",
            "interval": 7,
            "backupCount": 6,
            "encoding": "utf8"
        },

        "error_file_handler": {
            "class": 'logging.handlers.TimedRotatingFileHandler',
            "level": "ERROR",
            "formatter": "simple",
            "filename": "errors.log",
            "when": "D",
            "interval": 7,
            "backupCount": 6,
            "encoding": "utf8"
        }
    },

    "root": {
        "level": "INFO",
        "handlers": ["console", "info_file_handler", "error_file_handler"]
    }
}
