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

## TEMPLATE
# email - {name}{greetings}{introduction}{title}{description}{image_url}
EMAIL_CONTENTS_FORMAT = (
    "<div style='margin-top:0cm;margin-right:0cm;margin-bottom:10.0pt;margin-left:0cm"
    ';line-height:115%;font-size:15px;font-family:"Calibri",sans-serif;border:none;bo'
    "rder-bottom:solid #EEEEEE 1.0pt;padding:0cm 0cm 6.0pt 0cm;background:white;'>\n\n<"
    "p style='margin-top:0cm;margin-right:0cm;margin-bottom:11.25pt;margin-left:0cm;l"
    'ine-height:115%;font-size:15px;font-family:"Calibri",sans-serif;background:white'
    ";border:none;padding:0cm;'><span style='font-size:25px;font-family:\"Helvetica Ne"
    "ue\";color:#11171D;'>안녕하세요, {name}님! {greetings}</spa"
    "n></p>\n</div>\n\n<p style='margin-top:0cm;margin-right:0cm;margin-bottom:11.25pt;m"
    'argin-left:0cm;line-height:17.25pt;font-size:15px;font-family:"Calibri",sans-ser'
    "if;background:white;vertical-align:baseline;'><span style='font-size:14px;font-f"
    'amily:"Helvetica Neue";color:#11171D;\'>{introduction}</span></p>'
    "\n\n<p style='margin-top:0cm;margin-right:0cm;margin-bottom:10.0pt;margin-left:0cm"
    ';line-height:normal;font-size:15px;font-family:"Calibri",sans-serif;background:w'
    "hite;'><strong><span style='font-size:24px;font-family:\"Helvetica Neue\";color:#1"
    "1171D;'>{title}</span></stron"
    "g></p>\n\n<p style='margin-top:0cm;margin-right:0cm;margin-bottom:11.25pt;margin-l"
    'eft:0cm;line-height:17.25pt;font-size:15px;font-family:"Calibri",sans-serif;back'
    "ground:white;vertical-align:baseline;'><span style='font-size:14px;font-family:\""
    "Helvetica Neue\";color:#11171D;'>{description}</span></p>\n\n<p style='margin-top:0cm;margin-right:0cm;margin"
    '-bottom:11.25pt;margin-left:0cm;line-height:17.25pt;font-size:15px;font-family:"'
    "Calibri\",sans-serif;text-align:center;background:white;vertical-align:baseline;'"
    "><span style='font-size:14px;font-family:\"Helvetica Neue\";color:#11171D;'><img w"
    'idth="378" src="{image_url}" alt="sample1.jpg" class='
    '"fr-fic fr-dii"></span></p>\n\n<p>\n<br>\n</p>'
)
