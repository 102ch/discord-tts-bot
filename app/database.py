# DBの接続情報を定義する
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import Column
from sqlalchemy.types import Integer, String, Float, BigInteger

print(os.environ["SQLALCHEMY_DATABASE_URL"])
engine = create_engine(os.environ["SQLALCHEMY_DATABASE_URL"])

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Settings(Base):
    __tablename__ = "settings"
    server_id = Column(BigInteger, primary_key=True, index=True)
    volume = Column(Float, default=0.5)

class Nicknames(Base):
    __tablename__ = "nicknames"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger, index=True)
    nickname = Column(String(255))

class Dictionaries(Base):
    __tablename__ = "dictionaries"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    server_id = Column(BigInteger, index=True)
    key = Column(String(255))
    value = Column(String(255))

Base.metadata.create_all(bind=engine)

def set_volume(server_id: int, volume: float):
    db = SessionLocal()
    db.query(Settings).filter(Settings.server_id == server_id).delete()
    db.add(Settings(server_id=server_id, volume=volume))
    db.commit()
    db.close()

def get_volume(server_id: int):
    db = SessionLocal()
    setting = db.query(Settings).filter(Settings.server_id == server_id).first()
    db.close()
    return setting.volume

def get_nickname(server_id: int, user_id: int):
    db = SessionLocal()
    nickname = db.query(Nicknames).filter(Nicknames.server_id == server_id, Nicknames.user_id == user_id).first()
    db.close()
    return nickname

def set_nickname(server_id: int, user_id: int, nickname: str):
    db = SessionLocal()
    db.query(Nicknames).filter(Nicknames.server_id == server_id, Nicknames.user_id == user_id).delete()
    db.add(Nicknames(server_id=server_id, user_id=user_id, nickname=nickname))
    db.commit()
    db.close()

def get_dictionary(server_id: int) -> dict[str, str]:
    db = SessionLocal()
    dictionaries = db.query(Dictionaries).filter(Dictionaries.server_id == server_id).all()
    db.close()
    return {d.key: d.value for d in dictionaries}

def set_dictionary(server_id: int, key: str, value: str):
    db = SessionLocal()
    db.query(Dictionaries).filter(Dictionaries.server_id == server_id, Dictionaries.key == key).delete()
    db.add(Dictionaries(server_id=server_id, key=key, value=value))
    db.commit()
    db.close()

def delete_dictionary(server_id: int, keyword: str):
    db = SessionLocal()
    db.query(Dictionaries).filter(Dictionaries.server_id == server_id, Dictionaries.key == keyword).delete()
    db.commit()
    db.close()