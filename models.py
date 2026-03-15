from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id       = Column(Integer, primary_key=True, index=True)
    email    = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    runs = relationship("QRun", back_populates="user")

class QRun(Base):
    __tablename__ = "q_runs"
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, default="Untitled Run")
    user_id       = Column(Integer, ForeignKey("users.id"))
    status        = Column(String, default="pending")  # pending | done
    question_file = Column(String)
    questions_json = Column(Text)
    created_at    = Column(DateTime, default=datetime.utcnow)
    user    = relationship("User", back_populates="runs")
    answers = relationship("QAnswer", back_populates="run")

class QAnswer(Base):
    __tablename__ = "q_answers"
    id            = Column(Integer, primary_key=True, index=True)
    run_id        = Column(Integer, ForeignKey("q_runs.id"))
    question_id   = Column(String)
    question_text = Column(Text)
    answer_text   = Column(Text)
    citations     = Column(Text)   # JSON list of {source, snippet}
    run = relationship("QRun", back_populates="answers")