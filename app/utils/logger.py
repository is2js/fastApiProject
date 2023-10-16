import json
import time
from datetime import datetime, timedelta

from fastapi.logger import logger
import os
import logging
from logging.handlers import TimedRotatingFileHandler

from sqlalchemy.orm.exc import DetachedInstanceError
from starlette.requests import Request

from app.common.config import config
from app.errors.exceptions import APIException
from app.pages.exceptions import TemplateException


class Logger:
    # 선택할 수 있는 최소 레벨 종류
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    # def __init__(self, log_name, backup_count=conf().LOG_BACKUP_COUNT):
    def __init__(self, log_name, backup_count=config.LOG_BACKUP_COUNT):
        self.log_name = log_name
        # logger의 'APP', "DB" 등 이름에 따라 자체 폴더 경로 + 파일이름 생성
        self.log_dir = os.path.join(config.LOG_DIR, self.log_name)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f'{self.log_name}.log')

        self._log_format = '%Y-%m-%d %H:%M:%S'  # .log 파일에만 찍히는 형태
        formatter = logging.Formatter(
            '[%(levelname)s] %(asctime)s %(filename)s:%(lineno)d %(message)s',
            datefmt=self._log_format
        )
        handler = TimedRotatingFileHandler(
            filename=self.log_file,
            backupCount=backup_count,
            when="midnight",
        )
        handler.suffix = "%Y%m%d"  # 오늘이 아니라면, xxx.log.[suffix]형태로 붙음
        handler.setFormatter(formatter)

        # fastapi의 logger에 같은 이름이라면 sub logger로 설정
        # - flask + logging 버전
        # - self._logger = logging.getLogger(self.log_name)
        self._logger = logger.getChild(self.log_name)  # fastapi 전용
        self._logger.addHandler(handler)
        # 최소 level을 debug로 설정 -> 개별 logger들로 직접 찍을 것을 대비
        # cf) api용 .log()는 info or error만 사용.
        self._logger.setLevel(self.log_levels.get("DEBUG"))

    @property
    def get_logger(self):
        return self._logger

    # 선택된 logger객체마다 async 메서드를 호출하면 -> status_code에 따라 알아서 info or debug를 호출
    # => 대신 info를 찍을땐, reponse(JSONResponse)를, exception안에서는 error(APIException)을 넣어준다.

    async def log(self, request: Request, response=None, error=None):
        time_format = "%Y/%m/%d %H:%M:%S"  # log_dict용
        t = time.time() - request.state.start  # access_control에서 찍었던 시간과 비교해서, response 직전의 시간차
        status_code = error.status_code if error else response.status_code  # error가 들어왔다면, status_code 추출
        error_log = None  # 채우기 전에 초기화
        if error:
            # 핸들링이 빡센 except: 내부에서 채워짐.
            if request.state.inspect:
                frame = request.state.inspect
                error_file = frame.f_code.co_filename
                error_func = frame.f_code.co_name
                error_line = frame.f_lineno
            else:
                error_file = error_func = error_line = "UNKNOWN"

            error_log = dict(
                errorFunc=error_func,
                location="{} line in {}".format(str(error_line), error_file),
                raised=str(error.__class__.__name__),
                message=str(error.exception),
                detail=error.detail,
            )
        # user(UserToken) schema
        # - ip + user_id + email 마스킹버전
        #### 템플릿일 땐, detache error난다.
        try:
            user = request.state.user
            email = user.email.split("@") if user and user.email else None
        except DetachedInstanceError:
            user = email = None

        user_log = dict(
            client=request.state.ip,
            user=user.id if user and user.id else None,
            email="**" + email[0][2:-1] + "*@" + email[1] if user and user.email else None,
        )


        # 최종 dict
        # - UTC와 KST를 각각 time_format으로 지정
        log_dict = dict(
            url=request.url.hostname + request.url.path,
            method=str(request.method),
            statusCode=status_code,
            errorDetail=error_log,
            client=user_log,
            processedTime=str(round(t * 1000, 5)) + "ms",  # time.time()의 차이를 x1000 후, round(,5)로 하면, ms가 나온다.
            datetimeUTC=datetime.utcnow().strftime(time_format),
            datetimeKST=(datetime.utcnow() + timedelta(hours=9)).strftime(time_format),
        )
        # 400대 에러는 이미 핸들링된 에러라서, info로 찍는다.
        # -> 만든 dict를 json으로 변환한 뒤 -> logger로 찍는다.
        if error and error.status_code >= 500:
            self._logger.error(json.dumps(log_dict))
        else:
            self._logger.info(json.dumps(log_dict))


# app_logger = Logger("app").get_logger
# db_logger = Logger("db").get_logger
app_logger = Logger("app")
db_logger = Logger("db")

if __name__ == '__main__':
    # app_logger.debug("test")
    # app_logger.info("test")
    ...
