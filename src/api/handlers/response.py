import abc
from dataclasses import dataclass
import typing as tp

from src.api.context import ctx


class AbstractResponse(abc.ABC):
    @abc.abstractmethod
    def __bytes__(self):
        pass

    @staticmethod
    def parse(res: tp.Any):
        if not res:
            return None
        if isinstance(res, str):
            return StrResponse(res)
        else:
            if not isinstance(res, AbstractResponse):
                raise TypeError(
                    "'AbstractResponse' or 'str' expected, but got %s" % res.__class__
                )
            return res


@dataclass
class TemplateResponse(AbstractResponse):
    name: str
    context: dict

    def render_template(self):
        return ctx().jinja_env.get_template(self.name).render(self.context)

    def __bytes__(self):
        return self.render_template().encode("utf-8")


def render_template(name: str, context: dict = None):
    if context is None:
        context = dict()
    return TemplateResponse(name, context)


@dataclass
class StrResponse(AbstractResponse):
    payload: str

    def __bytes__(self):
        return self.payload.encode("utf-8")
