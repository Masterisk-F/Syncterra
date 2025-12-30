from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(String)
    # SQLiteでboolean値を扱う場合は、0/1の文字列として保存するのがベストプラクティス


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, unique=True, index=True, nullable=False)
    relative_path = Column(String)
    file_name = Column(String, nullable=False)
    title = Column(String)
    artist = Column(String)
    album_artist = Column(String)
    composer = Column(String)
    album = Column(String)
    track_num = Column(String)
    duration = Column(Integer)
    codec = Column(String)
    size = Column(Integer)
    msg = Column(String)
    sync = Column(Boolean, default=False)
    missing = Column(Boolean, default=False)
    added_date = Column(DateTime, default=datetime.now)
    last_modified = Column(DateTime)

    # Relationships
    playlist_tracks = relationship("PlaylistTrack", back_populates="track")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # Relationships
    tracks = relationship(
        "PlaylistTrack", back_populates="playlist", cascade="all, delete-orphan"
    )


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    order = Column(Integer, nullable=False)  # Order of the track in the playlist

    # Relationships
    playlist = relationship("Playlist", back_populates="tracks")
    track = relationship("Track", back_populates="playlist_tracks")
