import json
import os
from abc import ABC, abstractmethod
import typing as tp

_T = tp.TypeVar("_T")


class AbstractStore(ABC):
    @abstractmethod
    def __getitem__(self, item: str) -> _T:
        pass

    @abstractmethod
    def __setitem__(self, key: str, value: _T):
        pass

    def get(self, key: str, default: _T | None = None) -> _T | None:
        return self[key] or default

    def set(self, key: str, value: _T):
        self[key] = value


class JsonFileStore(AbstractStore):
    _path: str
    _data: dict

    def __init__(self, path: str):
        self._path = path
        if not os.path.exists(path):
            self.__save({})
        self._data = self.__load()

    def __getitem__(self, item):
        return self._data.get(item)

    def __setitem__(self, key, value):
        self._data[key] = value
        self.__save(self._data)

    def __save(self, data):
        with open(self._path, "w") as f:
            json.dump(data, f)

    def __load(self) -> dict:
        with open(self._path, "r") as f:
            return json.load(f)
