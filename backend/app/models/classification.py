from enum import StrEnum

from pydantic import BaseModel, Field


class ArticleDomain(StrEnum):
    AI_AGENTS = "ai_agents"
    LLMS = "llms"
    DEV_TOOLS = "dev_tools"
    OPEN_SOURCE = "open_source"
    LIBRARIES = "libraries"
    INFRA = "infra"
    FUNDING = "funding"
    STARTUPS = "startups"
    RESEARCH = "research"
    SECURITY = "security"
    PYTHON = "python"
    SYSTEMS = "systems"
    HARDWARE = "hardware"
    BUSINESS = "business"


class ClassificationOutput(BaseModel):
    domains: list[ArticleDomain] = Field(max_length=3)
    relevance_score: float = Field(ge=0.0, le=1.0)
    is_noise: bool
    reason: str = Field(min_length=1)
