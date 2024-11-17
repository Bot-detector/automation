import json
import logging
import sys


# Configure JSON logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "ts": self.formatTime(record, self.datefmt),
            "lvl": record.levelname,
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


class IgnoreSpecificWarnings(logging.Filter):
    def filter(self, record):
        # Return False to filter out messages containing "Unknown table"
        return "Unknown table" not in record.getMessage()


# Set up the logger
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())

logging.basicConfig(level=logging.INFO, handlers=[handler])
logging.getLogger("asyncmy").addFilter(IgnoreSpecificWarnings())
