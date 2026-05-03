from __future__ import annotations

from sqlalchemy.orm import Session

from . import models
from .security import hash_password

DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'
DEFAULT_HOSPITAL_PASSWORD = 'hospital123'
DEFAULT_HOSPITALS = [
    {'code': 'ohrid', 'name': 'Ohrid', 'city': 'Ohrid'},
    {'code': 'bitola', 'name': 'Bitola', 'city': 'Bitola'},
    {'code': 'skopje', 'name': 'Skopje', 'city': 'Skopje'},
]


def ensure_demo_data(db: Session) -> None:
    admin = db.query(models.User).filter(models.User.username == DEFAULT_ADMIN_USERNAME).first()
    if admin is None:
        db.add(
            models.User(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                role='ADMIN',
                hospital_id=None,
                is_active=True,
            )
        )

    for item in DEFAULT_HOSPITALS:
        hospital = db.query(models.Hospital).filter(models.Hospital.code == item['code']).first()
        if hospital is None:
            hospital = models.Hospital(
                code=item['code'],
                name=item['name'],
                city=item['city'],
                status='waiting',
                disease_type='sepsis',
                dataset_rows=0,
                dataset_columns=0,
                is_active=True,
            )
            db.add(hospital)
            db.flush()

        username = item['code']
        user = db.query(models.User).filter(models.User.username == username).first()
        if user is None:
            db.add(
                models.User(
                    username=username,
                    password_hash=hash_password(DEFAULT_HOSPITAL_PASSWORD),
                    role='HOSPITAL',
                    hospital_id=hospital.id,
                    is_active=True,
                )
            )


