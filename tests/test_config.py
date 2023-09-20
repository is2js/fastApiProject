

async def test_config(request_service):
    # print(await request_service("get"))
    print(await request_service("post", service_name="kakao/send", method_options=dict(
        json=dict(title='zz', message='vvv')
    )))

    assert True
