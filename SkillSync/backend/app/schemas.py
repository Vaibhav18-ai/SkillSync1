from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)

class LoginIn(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    model_config = {"from_attributes": True}

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ---------- Students ----------
class SkillOut(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    model_config = {"from_attributes": True}

class SkillRatingIn(BaseModel):
    skill_id: int
    proficiency: int = Field(ge=1, le=5)
    experience_score: float = Field(default=0, ge=0, le=10)

class ProfileIn(BaseModel):
    interests: Optional[str] = Field(default=None, max_length=500)
    availability_hours: int = Field(default=0, ge=0, le=80)
    preferred_role: Optional[str] = Field(default=None, max_length=60)
    github_url: Optional[str] = Field(default=None, max_length=255)

# ---------- Competitions ----------
class RequirementIn(BaseModel):
    skill_id: int
    weight: float = Field(gt=0, le=10)
    min_level: int = Field(default=0, ge=0, le=5)
    mandatory: bool = False

class CompetitionIn(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    comp_type: Literal["dsa", "ml", "hardware", "web", "other"] = "other"
    team_size: int = Field(default=6, ge=2, le=10)
    num_teams: int = Field(default=5, ge=2, le=20)
    fairness_tolerance: float = Field(default=0.8, gt=0, le=3)
    formation_mode: Literal["balanced", "preference", "self"] = "preference"
    deadline: Optional[date] = None
    requirements: list[RequirementIn] = Field(min_length=1)

class ApplyIn(BaseModel):
    wants_to_lead: bool = False

class PreferenceIn(BaseModel):
    other_user_id: int
    kind: Literal["prefer", "avoid"] = "prefer"

# ---------- Teams ----------
class FinalizeIn(BaseModel):
    run_id: int
    option_index: int = Field(default=0, ge=0, le=2)

class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    assignee_id: Optional[int] = None
    estimated_hours: float = Field(default=0, ge=0, le=200)
    deadline: Optional[date] = None

    @field_validator("deadline")
    @classmethod
    def deadline_not_past(cls, v):
        if v is not None and v < date.today():
            raise ValueError("The deadline cannot be in the past.")
        return v

class TaskStatusIn(BaseModel):
    status: Literal["todo", "doing", "done"]

class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due_date: Optional[date] = None

    @field_validator("due_date")
    @classmethod
    def due_not_past(cls, v):
        if v is not None and v < date.today():
            raise ValueError("The due date cannot be in the past.")
        return v