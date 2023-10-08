from fastapi_users.router.oauth import generate_state_token

from app.common.config import JWT_SECRET


def encode_next_state(url: str) -> str:
    # {{request.url}}로 만 사용하면 string아님. request.url._url일 경우만 string
    if not isinstance(url, str):
        url = str(url)
    state_data = dict(next=url)
    return generate_state_token(state_data, JWT_SECRET)
