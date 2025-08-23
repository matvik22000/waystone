import re

from src.api.context import ctx
from src.config import CONFIG


def datetime_format(value, format=CONFIG.TIME_FORMAT):
    return value.strftime(format)


RE_MALFORM = re.compile(r"[\u0000-\u001F\u007F-\u009F\uFFFD]+")


def replace_malformed(text: str) -> str:
    return RE_MALFORM.sub("", text)


def register_filters():
    ctx().jinja_env.filters["strftime"] = datetime_format
    ctx().jinja_env.filters["replace_malformed"] = replace_malformed
