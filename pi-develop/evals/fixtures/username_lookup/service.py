from repository import find_by_username


def get_user(username: str) -> dict[str, str] | None:
    return find_by_username(username)
