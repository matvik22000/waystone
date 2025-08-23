import datetime
from dataclasses import dataclass
import typing as tp

from src.api.context import ctx
from src.api.exceptions import NotIdentified

_UserData = tp.TypeVar("_UserData")


@dataclass
class Request:
    path: str
    data: tp.Dict | tp.Any
    request_id: bytes
    link_id: bytes
    remote_identity: tp.Optional[bytes]
    requested_at: float

    def __post_init__(self):
        if self.data is None:
            self.data = dict()

    def request_at_utc(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.requested_at)

    def get_param(self, name: str):
        if name in self.data:
            return self.data[name]
        if "var_" + name in self.data:
            return self.data["var_" + name]
        if "field_" + name in self.data:
            return self.data["field_" + name]

    def has_param(self, name: str):
        return any((p in self.data for p in (name, "var_" + name, "field_" + name)))

    def get_remote_identity(self) -> str:
        if not self.remote_identity:
            raise NotIdentified()
        return str(self.remote_identity)

    def get_user_data(self, default: tp.Any = None) -> _UserData | None:
        """
        returns object, saved for user before via save_user_data

        :param default:
        :return:
        """
        return ctx().store.get(self.get_remote_identity(), default)

    def save_user_data(self, data: _UserData):
        """
        allows to save object for user, if he is identified

        :param data:
        :return:
        """
        ctx().store.set(self.get_remote_identity(), data)


# path=/test, <class 'str'>
# data=None, <class 'NoneType'>
# request_id=b'\xabO\x85\x8e\xa1\x93\x02\x06\\\x88$a!\xbd\x8dO', <class 'bytes'>
# link_id=b'\x1e\xb0\x91\xbe\xa7Z19t\xec\x85A\x1a\x9a\x02\xb1', <class 'bytes'>
# remote_identity=None, <class 'NoneType'>
# requested_at=1722471114.993077, <class 'float'>
