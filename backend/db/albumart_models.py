from datetime import datetime

from sqlalchemy import Column, Float, Integer, LargeBinary, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AlbumArt(Base):
    __tablename__ = "album_arts"

    id = Column(Integer, primary_key=True, index=True)
    # Searching/indexing key (lowercased)
    album_normalized = Column(String, unique=True, index=True, nullable=False)
    # Display name
    album_display = Column(String)
    
    # Binary image data (resized 500x500 max)
    image_data = Column(LargeBinary, nullable=True)
    
    # Where does this come from?
    source_path = Column(String) # File path of the source image or audio file
    source_type = Column(String) # 'meta' or 'file'
    source_mtime = Column(Float) # Timestamp of the source file to detect changes

    updated_at = Column(Float, default=lambda: datetime.now().timestamp())
