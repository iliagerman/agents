USERS = {"Alice": {"username": "Alice"}}


def find_by_username(username: str) -> dict[str, str] | None:
    return USERS.get(username)
