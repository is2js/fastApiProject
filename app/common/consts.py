# JWT

JWT_SECRET = 'abcd1234!'
JWT_ALGORITHM = 'HS256'

# 미들웨어
EXCEPT_PATH_LIST = ["/", "/openapi.json"]
# EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/auth)"
EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/v[0-9]+/auth)"
SERVICE_PATH_REGEX = "^(/api/v[0-9]+/services)"

# API KEY
MAX_API_KEY_COUNT = 3
MAX_API_WHITE_LIST_COUNT = 10
