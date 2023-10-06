import datetime
import ipaddress
import re
from urllib.parse import urlparse, parse_qs, urlencode

import bcrypt
import jwt

from app.common.consts import JWT_ALGORITHM
from app.common.config import JWT_SECRET, config, ProdConfig
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


async def hash_password(plain_password: str):
    hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
    return hashed_password.decode('utf-8')


def verify_password(hashed_password, plain_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def update_query_string(url: str, **kwargs):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # if not isinstance(config, ProdConfig):
    #     new_redirect_uri = f"http://{config.HOST_MAIN}:{config.PORT}/discord/callback"
    # else:
    #     new_redirect_uri = f"https://{config.HOST_MAIN}/discord/callback"
    # # 인코드된 redirect_uri을 다시 URL에 삽입하여 새로운 authorize_url 생성
    # query_params['redirect_uri'] = [new_redirect_uri]

    for key, value in kwargs.items():
        if value is None:
            continue
        query_params[key] = [value]
    updated_query = urlencode(query_params, doseq=True)

    new_url = parsed_url._replace(query=updated_query).geturl()

    return new_url
