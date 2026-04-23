from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def is_password_hashed(value: str) -> bool:
    return value.startswith("pbkdf2:") or value.startswith("scrypt:")


def verify_password(stored_password: str, candidate_password: str) -> bool:
    if is_password_hashed(stored_password):
        return check_password_hash(stored_password, candidate_password)
    return stored_password == candidate_password
