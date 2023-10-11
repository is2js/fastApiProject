from pydantic import BaseModel, ConfigDict, Field


class GuildLeaveRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guild_id: int = Field(..., description='삭제할 guild의 id')
    # member_count: int = Field(..., description='삭제할 guild의 member count')
    # guild_id: str = Field(default=None, description='삭제할 guild의 id')
    # guild_id: str
