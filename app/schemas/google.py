from pydantic import BaseModel, ConfigDict, Field


class CreateCalendarSyncsRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description='Calnedar를 Sync할 user의 id')
    calendar_id: int = Field(..., description='Calnedar를 Sync할 calendar의 id')
    loop_index: int = Field(..., description='partial render를 위한 loop index')


class DeleteCalendarSyncsRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description='Sync 삭제할 user의 id')
    calendar_id: int = Field(..., description='Sync 삭제할 calendar의 id')
    loop_index: int = Field(..., description='partial render를 위한 loop index')
