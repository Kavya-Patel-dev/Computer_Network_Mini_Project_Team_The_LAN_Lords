from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Literal["user", "admin"]
    status: Literal["active", "deactivated"]
    created_at: datetime
    last_active_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordUpdate(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    topology: dict[str, Any]
    traffic_preset: Literal["latency_focused", "light", "medium", "heavy", "manual"] = "medium"
    flows: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    selected_scenarios: list[Literal["normal", "link_failure", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop"]] = Field(default_factory=lambda: ["normal"], max_length=5)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    topology: dict[str, Any] | None = None
    traffic_preset: Literal["latency_focused", "light", "medium", "heavy", "manual"] | None = None
    flows: list[dict[str, Any]] | None = Field(default=None, max_length=5000)
    selected_scenarios: list[Literal["normal", "link_failure", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop"]] | None = Field(default=None, max_length=5)


class ReviewRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    comment: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class SimulationRequest(BaseModel):
    scenarios: list[Literal["normal", "link_failure", "link_failures", "router_failure", "traffic_spike", "bandwidth_drop"]] | None = None
    seed: int = Field(default=1000, ge=0, le=2_147_483_647)
    max_steps: int = Field(default=500, ge=1, le=2000)


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    status: Literal["active", "deactivated"] | None = None


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    message: str
    link_to: str
    read: bool
    created_at: datetime


def scenario_for_model(value: str) -> str:
    return "link_failures" if value == "link_failure" else value
