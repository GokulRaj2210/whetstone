_USERS = {1: {"name": "ada"}, 2: {"name": "grace"}}
_CACHE = {}


def get_user(user_id):
    if user_id not in _CACHE:
        _CACHE[user_id] = dict(_USERS[user_id])
    return _CACHE[user_id]


def _invalidate(user_id):
    _CACHE.pop(user_id, None)


def rename_user(user_id, name):
    _USERS[user_id]["name"] = name
    _invalidate(user_id)


def delete_user(user_id):
    _USERS.pop(user_id, None)
    _invalidate(user_id)
