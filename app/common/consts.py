# JWT
JWT_SECRET = 'abcd1234!'
JWT_ALGORITHM = 'HS256'

# 미들웨어
EXCEPT_PATH_LIST = ["/", "/openapi.json"]
EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/auth)"