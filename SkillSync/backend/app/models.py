from sqlalchemy import (Column, Integer, String, Float, Boolean, Text, Date,
                        DateTime, Enum, ForeignKey, UniqueConstraint, JSON, func)
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("student", "coordinator", "admin"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id"), unique=True, nullable=False)
    interests = Column(Text)
    availability_hours = Column(Integer, default=0)
    preferred_role = Column(String(60))
    github_url = Column(String(255))

class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, nullable=False)
    category = Column(String(40))

class StudentSkill(Base):
    __tablename__ = "student_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    skill_id = Column(ForeignKey("skills.id"), nullable=False)
    proficiency = Column(Integer, nullable=False)      # 1-5
    experience_score = Column(Float, default=0)        # 0-10
    assessment_score = Column(Float, default=0)        # 0-10

class Competition(Base):
    __tablename__ = "competitions"
    id = Column(Integer, primary_key=True)
    coordinator_id = Column(ForeignKey("users.id"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    comp_type = Column(String(40))                      # dsa, ml, hardware, web
    team_size = Column(Integer, default=6)
    num_teams = Column(Integer, default=5)
    fairness_tolerance = Column(Float, default=0.8)
    formation_mode = Column(Enum("balanced", "preference", "self"), default="preference")
    status = Column(Enum("draft", "registration_open", "registration_closed",
                         "teams_proposed", "under_review", "finalized",
                         "ongoing", "completed"), default="draft")
    join_code = Column(String(12), unique=True)
    deadline = Column(Date)

class CompetitionRequirement(Base):
    __tablename__ = "competition_requirements"
    __table_args__ = (UniqueConstraint("competition_id", "skill_id"),)
    id = Column(Integer, primary_key=True)
    competition_id = Column(ForeignKey("competitions.id"), nullable=False)
    skill_id = Column(ForeignKey("skills.id"), nullable=False)
    weight = Column(Float, nullable=False)              # normalized later
    min_level = Column(Integer, default=0)
    mandatory = Column(Boolean, default=False)

class CompetitionApplication(Base):
    __tablename__ = "competition_applications"
    __table_args__ = (UniqueConstraint("competition_id", "user_id"),)
    id = Column(Integer, primary_key=True)
    competition_id = Column(ForeignKey("competitions.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    status = Column(Enum("applied", "confirmed", "withdrawn"), default="applied")
    wants_to_lead = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class TeammatePreference(Base):
    __tablename__ = "teammate_preferences"
    id = Column(Integer, primary_key=True)
    competition_id = Column(ForeignKey("competitions.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    other_user_id = Column(ForeignKey("users.id"), nullable=False)
    kind = Column(Enum("prefer", "avoid"), default="prefer")

class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"
    id = Column(Integer, primary_key=True)
    competition_id = Column(ForeignKey("competitions.id"), nullable=False)
    settings = Column(JSON)
    result = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())

class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("competition_id", "team_no"),)
    id = Column(Integer, primary_key=True)
    competition_id = Column(ForeignKey("competitions.id"), nullable=False)
    team_no = Column(Integer, nullable=False)
    leader_id = Column(ForeignKey("users.id"), nullable=True)
    avg_score = Column(Float, default=0)

class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("competition_id", "user_id"),)   # one team per student
    id = Column(Integer, primary_key=True)
    team_id = Column(ForeignKey("teams.id"), nullable=False)
    competition_id = Column(ForeignKey("competitions.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    is_leader = Column(Boolean, default=False)
    score = Column(Float, default=0)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    team_id = Column(ForeignKey("teams.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    assignee_id = Column(ForeignKey("users.id"), nullable=True)
    estimated_hours = Column(Float, default=0)
    deadline = Column(Date)
    status = Column(Enum("todo", "doing", "done"), default="todo")
    created_by = Column(ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(Integer, primary_key=True)
    team_id = Column(ForeignKey("teams.id"), nullable=False)
    title = Column(String(200), nullable=False)
    due_date = Column(Date)
    done = Column(Boolean, default=False)