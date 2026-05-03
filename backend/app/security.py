from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

JWT_SECRET = os.getenv('JWT_SECRET', 'fedhealth-mk-dev-secret')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', '12'))
PBKDF2_ROUNDS = int(os.getenv('PASSWORD_HASH_ROUNDS', '120000'))


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('utf-8')


def _b64url_decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))


def hash_password(password: str, salt: str | None = None) -> str:
    salt_bytes = os.urandom(16) if salt is None else base64.urlsafe_b64decode(salt.encode('utf-8'))
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt_bytes).decode('utf-8')}${base64.urlsafe_b64encode(digest).decode('utf-8')}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split('$', 2)
    except ValueError:
        return False
    if algorithm != 'pbkdf2_sha256':
        return False
    expected = hash_password(password, salt=salt)
    return hmac.compare_digest(expected, stored)


def create_access_token(subject: str, role: str, hospital_id: int | None = None, username: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        'sub': subject,
        'role': role,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=JWT_EXPIRES_HOURS)).timestamp()),
    }
    if hospital_id is not None:
        payload['hospital_id'] = hospital_id
    if username is not None:
        payload['username'] = username
    header = {'alg': JWT_ALGORITHM, 'typ': 'JWT'}
    header_part = _b64url_encode(json.dumps(header, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    payload_part = _b64url_encode(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    signing_input = f'{header_part}.{payload_part}'.encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    return f'{header_part}.{payload_part}.{_b64url_encode(signature)}'


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split('.')
    except ValueError as exc:
        raise ValueError('Invalid token') from exc
    signing_input = f'{header_part}.{payload_part}'.encode('utf-8')
    expected_signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_part):
        raise ValueError('Invalid token')
    payload = json.loads(_b64url_decode(payload_part).decode('utf-8'))
    if int(payload.get('exp', 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError('Token expired')
    return payload


