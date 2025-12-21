from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel
from ..db.database import get_db
from ..db.models import Setting
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# SSH鍵の保存場所
SSH_KEY_DIR = os.path.expanduser("~/.ssh")
SSH_PRIVATE_KEY_PATH = os.path.join(SSH_KEY_DIR, "audiosync_rsa")
SSH_PUBLIC_KEY_PATH = os.path.join(SSH_KEY_DIR, "audiosync_rsa.pub")


class SettingModel(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True


def ensure_ssh_dir():
    """SSH ディレクトリが存在することを確認し、適切な権限を設定"""
    if not os.path.exists(SSH_KEY_DIR):
        os.makedirs(SSH_KEY_DIR, mode=0o700)
    else:
        os.chmod(SSH_KEY_DIR, 0o700)


def generate_ssh_key_pair(comment: str = ""):
    """SSH鍵ペアを生成"""
    ensure_ssh_dir()
    
    cmd = [
        "ssh-keygen",
        "-t", "rsa",
        "-b", "2048",
        "-f", SSH_PRIVATE_KEY_PATH,
        "-N", "",  # パスフレーズなし
        "-C", comment
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )
    
    # 適切な権限を設定
    os.chmod(SSH_PRIVATE_KEY_PATH, 0o600)  # 秘密鍵: 所有者のみ読み書き
    os.chmod(SSH_PUBLIC_KEY_PATH, 0o644)   # 公開鍵: 所有者読み書き、その他読み取り
    
    logger.info(f"SSH key pair generated at {SSH_PRIVATE_KEY_PATH} with comment '{comment}'")


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


@router.get("/ssh-key/public")
async def get_public_key(db: AsyncSession = Depends(get_db)):
    """保存されている公開鍵を取得（存在しない場合は生成）"""
    try:
        # 既存の鍵ファイルをチェック
        if not (os.path.exists(SSH_PRIVATE_KEY_PATH) and os.path.exists(SSH_PUBLIC_KEY_PATH)):
            # 設定からユーザー名とホスト名を取得してコメントに使用
            result = await db.execute(
                select(Setting).where(Setting.key.in_(["rsync_user", "rsync_host"]))
            )
            settings = {s.key: s.value for s in result.scalars().all()}
            
            user = settings.get("rsync_user")
            host = settings.get("rsync_host")
            comment = ""
            
            if user and host:
                comment = f"{user}@{host}"
            
            logger.info(f"SSH key pair not found, generating new one with comment: {comment}")
            generate_ssh_key_pair(comment)
            
            # 鍵パスをデータベースに保存
            result = await db.execute(select(Setting).where(Setting.key == "rsync_key_path"))
            existing = result.scalars().first()
            if existing:
                existing.value = SSH_PRIVATE_KEY_PATH
            else:
                new_setting = Setting(key="rsync_key_path", value=SSH_PRIVATE_KEY_PATH)
                db.add(new_setting)
            await db.commit()
        else:
            logger.info("Using existing SSH key pair")
        
        # 公開鍵を読み取り
        with open(SSH_PUBLIC_KEY_PATH, "r") as f:
            public_key = f.read().strip()
        
        return Response(
            content=public_key, 
            media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="audiosync_rsa.pub"'}
        )
        
    except subprocess.CalledProcessError as e:
        logger.error(f"SSH key generation failed: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"SSH key generation failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Public key retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Public key retrieval error: {str(e)}")
