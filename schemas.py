from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class RunOut(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}

class AnswerOut(BaseModel):
    id: int
    run_id: int
    question_id: str
    question_text: str
    answer_text: str
    citations: str  # raw JSON string
    model_config = {"from_attributes": True}

class AnswerEdit(BaseModel):
    answer_text: str