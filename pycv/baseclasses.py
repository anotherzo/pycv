from pathlib import Path
from instructor import patch
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Cvitem(BaseModel):
    job: int
    item: str

class Education(BaseModel):
    edu: int
    title: str
    organization: str
    location: str
    date: List[str]
    desc: Optional[str] = None

class Job(BaseModel):
    job: int
    position: str
    organization: str
    location: str
    date: List[str]

class JobDescription(BaseModel):
    job: int
    description: str

class Letterinfo(BaseModel):
    recipient: List[str]
    subject: str
    opening: str
    content: str

class Statement(BaseModel):
    job: int
    statement: str

class SkillCategory(BaseModel):
    category: str
    items: List[str]

class Language(BaseModel):
    language: str
    level: str

class CarStory(BaseModel):
    job: int
    challenge: str
    action: str
    result: str
    skills: List[str]

class PersonalData(BaseModel):
    photo: str
    name: List[str]
    position: str
    address: str
    mobile: str
    email: str
    linkedin: str

class Summary(BaseModel):
    summary: str
