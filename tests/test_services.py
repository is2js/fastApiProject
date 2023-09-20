import pytest

from app.common.config import KAKAO_SEND_ME_ACCESS_TOKEN


@pytest.mark.skipif(KAKAO_SEND_ME_ACCESS_TOKEN is None, reason="KAKAO_SEND_ME_ACCESS_TOKEN is not set")
async def test_send_kakao(request_service):
    json = dict(
        title="안녕하세요",
        message="카카오톡 나에게 보내기 테스트입니다."
    )

    response = await request_service(
        "post",
        service_name="kakao/send",
        json=json
    )

    assert response['message'] == 'ok'


async def test_send_by_ses(request_service):
    json = dict(
        mail_title="테스트 메일 발송 입니다.",
        greetings="오늘 하루 괜찮으셨나요?", # 고객님, xxxx
        introduction="한의원 인증앱입니다.",
        title="서비스 장애 발생",
        description="금일 서버실 화재로 인해 17:00 ~ 19:00 서비스 장애가 발생하였으나, 진압되었으니 참고 부탁드립니다",
    )

    response = await request_service(
        "post",
        service_name="email/send_by_ses",
        json=json
    )

    assert response['message'] == 'ok'
