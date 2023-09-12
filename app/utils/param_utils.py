from base64 import b64encode
from hmac import HMAC, new


def to_query_string(params: dict) -> str:
    return '&'.join(
        f"{k}={v}" for k, v in params.items()
    )


def hash_query_string(query_string: str, secret_key: str) -> str:
    # key와 msg(해쉬 대상) string -> 모두 bytes객체로 변환한 뒤,
    # mac객체를 만들고 -> .digest()로 해쉬된 값(이진값)을 꺼낸 뒤
    # -> base64인코딩을 통해, 이진값 -> 문자열로 변환한다
    mac: HMAC = new(
        key=bytes(secret_key, encoding="utf-8"),
        msg=bytes(query_string, encoding="utf-8"),
        digestmod="sha256",
    )

    return str(b64encode(mac.digest()).decode("utf-8"))
