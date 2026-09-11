from defaults import DEFAULTS


class Config:
    """A settings bag that can be cloned per request.

    A clone must be fully independent: handlers mutate their own copy
    and must never affect the shared base or each other.
    """

    def __init__(self, data=None):
        self._data = dict(data if data is not None else DEFAULTS)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def clone(self):
        return Config(dict(self._data))
