from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel
from ..db.database import get_db
from ..db.models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingModel(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[SettingModel])
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    return result.scalars().all()


@router.put("")
async def update_setting(setting: SettingModel, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting).where(Setting.key == setting.key))
    existing = result.scalars().first()
    if existing:
        existing.value = setting.value
    else:
        new_setting = Setting(key=setting.key, value=setting.value)
        db.add(new_setting)
    await db.commit()
    return {"status": "ok", "key": setting.key, "value": setting.value}
