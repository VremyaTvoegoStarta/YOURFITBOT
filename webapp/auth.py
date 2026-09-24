"""
Проверка initData, которую Telegram передаёт из Mini App.
Это подтверждает, что запрос реально пришёл из Telegram от конкретного
пользователя, а не подделан кем-то другим. Официальная схема проверки:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
from urllib.parse import parse_qsl


def parse_and_validate(init_data: str, bot_token: str) -> dict | None:
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None
    return pairs
