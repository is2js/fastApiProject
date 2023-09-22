import datetime
import ipaddress
import re

import jwt

from app.common.consts import JWT_ALGORITHM
from app.common.config import JWT_SECRET
from app.errors.exceptions import TokenDecodeException, TokenExpiredException, InvalidIpException


async def url_pattern_check(path, pattern):
    result = re.match(pattern, path)
    return True if result else False


async def decode_token(token: str):
    """
    :param token:
    :return:
    """
    token = token.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, key=JWT_SECRET, algorithms=JWT_ALGORITHM)
        return payload
    except jwt.ExpiredSignatureError:
        # raise Exception("ExpiredSignature Error")
        raise TokenExpiredException()
    except jwt.InvalidTokenError:
        # raise Exception("InvalidToken Error")
        raise TokenDecodeException()


async def create_access_token(*, data: dict = None, expires_delta: int = None):
    # 들어온 데이터dict 원본을 변화시키지 않도록 미연에 방지( token 만료기간 연장)
    to_encode_data = data.copy()

    # 복사데이터dict 만료시간 update
    if expires_delta:
        to_encode_data.update({"exp": datetime.datetime.utcnow() + datetime.timedelta(hours=expires_delta)})

    # pyjwt로 엔코딩 -> string 반환
    encoded_jwt = jwt.encode(to_encode_data, key=JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


async def check_ip_format(ip_address):
    try:
        ipaddress.ip_address(ip_address)
    except Exception as e:
        raise InvalidIpException(ip_address, exception=e)
