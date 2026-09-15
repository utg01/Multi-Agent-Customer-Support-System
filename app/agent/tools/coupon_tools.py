from app.core.db.models import Coupon
from app.core.db.base import SessionLocal
from datetime import datetime, timedelta
import random
import string


def get_active_coupons(db):
    """Gets all currently active and valid coupons"""

    try:
        coupons = db.query(Coupon).filter(
            Coupon.is_active == True,
            Coupon.valid_till >= datetime.now()
        ).all()

        all_coupons = []
        for c in coupons:
            all_coupons.append({
                "code": c.code,
                "discount_percent": c.discount_percent,
                "discount_amount": c.discount_amount,
                "valid_till": str(c.valid_till)
            })

        if not all_coupons:
            return {"coupons": []}

        return {"coupons": all_coupons}

    except Exception as e:
        print("Error fetching active coupons:", e)
        return {"error": "Unable to fetch active coupons"}


def validate_coupon(db, code: str):
    """Checks if a coupon code is valid and active"""

    try:
        coupon = db.query(Coupon).filter(
            Coupon.code == code
        ).first()

        if not coupon:
            return {"error": "Coupon not found"}

        if not coupon.is_active:
            return {"error": "Coupon is not active"}

        if coupon.valid_till < datetime.now():
            return {"error": "Coupon has expired"}

        return {
            "code": coupon.code,
            "discount_percent": coupon.discount_percent,
            "discount_amount": coupon.discount_amount,
            "valid_till": str(coupon.valid_till)
        }

    except Exception as e:
        print("Error validating coupon:", e)
        return {"error": "Unable to validate coupon"}


def create_coupon(db, user_id: int, discount_amount: float, valid_days: int = 30):
    """Creates a refund coupon for a user with a fixed discount amount"""

    try:
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"REFUND{user_id}{suffix}"

        coupon = Coupon(
            code=code,
            discount_amount=discount_amount,
            discount_percent=None,
            valid_till=datetime.now() + timedelta(days=valid_days),
            is_active=True
        )
        db.add(coupon)
        db.commit()

        return {
            "message": "Coupon created successfully",
            "code": coupon.code,
            "discount_amount": coupon.discount_amount,
            "valid_till": str(coupon.valid_till)
        }

    except Exception as e:
        print("Error creating coupon:", e)
        return {"error": "Unable to create coupon"}


if __name__ == '__main__':
    db = SessionLocal()
    print(create_coupon(db, 2, 500))