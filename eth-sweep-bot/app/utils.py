from loguru import logger
import sys
def setup_logging(path: str, level: str, mode: str, symbol: str):
    logger.remove(); fmt='{time:YYYY-MM-DD HH:mm:ss} | {level} | mode='+mode+' | symbol='+symbol+' | event={message}'
    logger.add(sys.stderr, level=level, format=fmt)
    logger.add(path, level=level, rotation='10 MB', retention='14 days', format=fmt)
