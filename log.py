import logging

logger: logging.Logger


def debug(msg: str):
    logger.debug(msg, stacklevel=2)

def info(msg: str):
    logger.info(msg, stacklevel=2)

def warning(msg: str):
    logger.warning(msg, stacklevel=2)
    
def error(msg: str, exc_info=False):
    logger.error(msg, stacklevel=2, exc_info=exc_info)


def init_logger(name: str):
    global logger
    logger = logging.getLogger(name)
    logger.setLevel('DEBUG')
    
    if not logger.handlers:
        formatter = logging.Formatter(
            '%(levelname)8s|%(filename)14s|%(name)s|%(funcName)22s()|%(message)s')
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        logger.addHandler(streamhandler)


def debug_level_cb(new_level: str):
    logger.setLevel(new_level)
    logger.info('Log level set to ' + new_level)
    
def setup_preferences_cb(pref):
    pref.register_callback('debug_level', debug_level_cb)
    logger.debug('logger was set up ' + __package__)


def uninit_logger(pref):
    pref.unregister_callback('debug_level', debug_level_cb)
    
    logger.debug('removing loggers handlers.')
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.handlers.clear()
