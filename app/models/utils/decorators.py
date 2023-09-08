from functools import wraps


def with_transaction(func):

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # 외부 session이 주입된 경우, 주입시부터 tr생성하여 시작된 상태
        # -> transaction생성 없이 바로 실행만
        if self.served:
            result = await func(self, *args, **kwargs)
            return result

        async with self.session.begin() as transaction:
            try:
                result = await func(self, *args, **kwargs)
                # await transaction.commit()
                # CUD 메서드 내부에서 session.commit을 자체적으로 판단함.
                return result
            except Exception as e:
                await transaction.rollback()
                raise e
    return wrapper
