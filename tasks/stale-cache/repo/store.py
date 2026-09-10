_USERS = {1: {"name": "ada"}, 2: {"name": "grace"}}
_CACHE = {}


def get_user(user_id):
    if user_id not in _CACHE:
        _CACHE[user_id] = dict(_USERS[user_id])
    return _CACHE[user_id]


def rename_user(user_id, name):
    _USERS[user_id]["name"] = name


def delete_user(user_id):
    _USERS.pop(user_id, None)
