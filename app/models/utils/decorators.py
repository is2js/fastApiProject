from functools import wraps

from app.models.mixins.errors import TransactionException


def with_transaction(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        print("with tr - kwargs: ", kwargs.keys())

        # 외부 session이 주입된 경우, 주입시부터 tr생성하여 시작된 상태
        # -> transaction생성 없이 바로 실행만
        if self.served:
            result = await func(self, *args, **kwargs)
            return result

        # .save()-create/update or .remove()가 자체세션으로 들어왔는데 auto_commit=True가 아니면,
        #  -> tr(자동커밋)안에 넣으면 안된다. -> 흘려보내져야함.(사실상 에러 상황)
        # is_auto_commit = kwargs.get('auto_commit', False)
        # if not self.served and not is_auto_commit:
        #     raise TransactionException()
            # 자체세션 CUD 호출인데, autocommit을 안넣었다.

        # 자체세션 = async_scoped_session()이 있는 상황에서
        # tr을 만드려면, 한번더 ()호출하여
        # async_scoped_session(context-local -> 한번에 처리) 객체를
        # -> AsyncSession(독립 트랜잭션 전용)를 새로 발급하여 tr을 만들어 처리되게 한다.
        async with self.session() as transaction:
            try:
                result = await func(self, *args, **kwargs)
                # await transaction.commit()
                # CUD 메서드 내부에서 session.commit을 자체적으로 판단함.
                return result
            except Exception as e:
                await transaction.rollback()
                raise e

    return wrapper
