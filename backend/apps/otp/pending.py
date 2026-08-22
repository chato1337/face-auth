"""Crea o reutiliza un TenantUser pendiente para emitir OTP (purpose=email_verify)."""

from __future__ import annotations

from django.db import IntegrityError

from apps.accounts.models import TenantUser
from apps.otp.exceptions import OtpNotFoundError
from apps.otp.models import OtpChallenge
from apps.tenants.models import Application

UNAUTHENTICATED_PURPOSES = frozenset({OtpChallenge.Purpose.EMAIL_VERIFY})


def resolve_or_create_subject(
    *,
    application: Application,
    purpose: str,
    email: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
) -> TenantUser:
    email_norm = email.strip()
    existing = TenantUser.objects.filter(
        application=application,
        email__iexact=email_norm,
    ).first()
    if existing is not None:
        if purpose == OtpChallenge.Purpose.EMAIL_VERIFY and not existing.is_active:
            _update_pending_profile(existing, first_name, last_name, phone)
        return existing

    if purpose not in UNAUTHENTICATED_PURPOSES:
        raise OtpNotFoundError("No hay un código activo. Solicita uno nuevo.")

    try:
        return TenantUser.objects.create(
            application=application,
            email=email_norm,
            first_name=first_name.strip() or "Pending",
            last_name=last_name.strip() or "User",
            phone=phone.strip(),
            is_active=False,
        )
    except IntegrityError:
        return TenantUser.objects.get(application=application, email__iexact=email_norm)


def lookup_subject(*, application: Application, email: str) -> TenantUser:
    user = TenantUser.objects.filter(
        application=application,
        email__iexact=email.strip(),
    ).first()
    if user is None:
        raise OtpNotFoundError("No hay un código activo. Solicita uno nuevo.")
    return user


def _update_pending_profile(
    user: TenantUser,
    first_name: str,
    last_name: str,
    phone: str,
) -> None:
    fields: list[str] = []
    if first_name and user.first_name != first_name:
        user.first_name = first_name
        fields.append("first_name")
    if last_name and user.last_name != last_name:
        user.last_name = last_name
        fields.append("last_name")
    if phone and user.phone != phone:
        user.phone = phone
        fields.append("phone")
    if fields:
        user.save(update_fields=[*fields, "updated_at"])
