from pathlib import Path

from fastapi import APIRouter
from starlette.templating import Jinja2Templates

from .exceptions import RedirectException
from ..templates.filters.oauth import encode_next_state

# jinja template 객체 생성
# resolve() 함수는 파일의 Path객체 실제 경로(절대경로) -> 부모 : 현재 폴더
current_directory = Path(__file__).resolve().parent
# Path 객체에서 "/" 연산자를 사용하면 경로를 결합
templates_directory = current_directory.parent / "templates"
templates = Jinja2Templates(directory=str(templates_directory))
# 필터 등록
templates.env.filters["encode_next_state"] = encode_next_state

from . import index, discord

router = APIRouter()
router.include_router(index.router, tags=['Pages'])
router.include_router(discord.router, prefix='/discord', tags=['Pages'])
