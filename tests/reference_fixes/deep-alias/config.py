import copy

from defaults import DEFAULTS


class Config:
    """A settings bag that can be cloned per request."""

    def __init__(self, data=None):
        self._data = copy.deepcopy(data if data is not None else DEFAULTS)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def clone(self):
        return Config(self._data)
