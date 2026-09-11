from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CentralHomeAction:
    key: str
    label: str
    callback: str
    description: str


ACTIONS = (
    CentralHomeAction(
        key="register_representative",
        label="🤖 ثبت ربات نمایندگی",
        callback="central:register",
        description="Start a new representative registration flow.",
    ),
    CentralHomeAction(
        key="track_registration",
        label="🔎 پیگیری درخواست",
        callback="central:track",
        description="Show the owner's current registration status.",
    ),
)


def menu_actions() -> tuple[CentralHomeAction, ...]:
    return ACTIONS


def start_text(brand: str = "Pasarguard") -> str:
    return (
        f"🌐 {brand}\n\n"
        "به سامانه مرکزی نمایندگان خوش آمدید.\n"
        "از اینجا می‌توانید ربات نمایندگی خود را ثبت و وضعیت درخواست را پیگیری کنید."
    )


def no_registration_text() -> str:
    return "📭 هیچ درخواست فعالی برای شما پیدا نشد."
