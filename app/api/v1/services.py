import json

import requests
from fastapi import APIRouter
from starlette.requests import Request

from app.common.config import (
    KAKAO_SEND_ME_ACCESS_TOKEN,
    KAKAO_SEND_ME_IMAGE_URL,
    KAKAO_SEND_ME_URL
)
from app.errors.exceptions import KakaoSendMeMessageException
from app.schemas import SuccessMessage, KakaoMessageRequest

router = APIRouter()


@router.get('')
async def test(request: Request):
    return dict(you_email=request.state.user.email)


@router.post('/kakao/send')
async def send_kakao(request: Request, message_request: KakaoMessageRequest):
    # TODO: 추후 임시 8시간 TOKEN(REST API 테스트 -> 토큰발급)이 아닌, REFRESH가 계속 되도록 변경
    # 헤더
    headers = {
        'Authorization': KAKAO_SEND_ME_ACCESS_TOKEN, # Bearer uq82-Q0yOa0ITCkpqPBvgScfTEWxm0c__oHTLu7zCj102wAAAYqMOQo-
        'Content-Type': "application/x-www-form-urlencoded",
    }

    # data {'template_object': json }
    # 1) body
    # 내 앱 > 플랫폼 > Web플랫폼 등록된 것만 link로 보낼 시 보이게 됨.
    link_1 = "https://google.com"
    link_2 = "https://duckduckgo.com"

    template_object = json.dumps({
        "object_type": "feed",
        "content": {
            "title": message_request.title,
            "description": message_request.message,
            "image_url": KAKAO_SEND_ME_IMAGE_URL, # 530x640 jpg
            "image_width": 530,
            "image_height": 640,
            "link": {
                "web_url": "http://google.com",
                "mobile_web_url": "http://google.com",
                "android_execution_params": "contentId=100",
                "ios_execution_params": "contentId=100",
            },
        },
        "buttons": [
            {
                "title": "구글",
                "link": {"web_url": link_1, "mobile_web_url": link_1},
            },
            {
                "title": "덕덕고",
                "link": {"web_url": link_2, "mobile_web_url": link_2},
            },
        ],
    }, ensure_ascii=False)

    # 2) data
    data = {
        'template_object': template_object
    }

    # request
    response = requests.post(KAKAO_SEND_ME_URL, headers=headers, data=data)

    try:
        response.raise_for_status()
        # 카카오의 응답 중 result_code가 0이 아니면 에러
        if response.json()['result_code'] != 0:
            raise Exception
    except Exception as e:
        # 로깅
        raise KakaoSendMeMessageException(exception=e)

    return SuccessMessage()
