from app.core.db.models import Return, Order, OrderItem
from app.core.db.base import SessionLocal


def create_return(db, user_id: int, order_id: int, order_item_id: int, reason: str):
    """Creates a return for a given order item wrt user_id"""

    try:
        order = db.query(Order).filter(
            Order.order_id == order_id,
            Order.user_id == user_id
        ).first()

        if not order:
            return {"error": "Order not found or does not belong to the user"}

        item = db.query(OrderItem).filter(
            OrderItem.orderitem_id == order_item_id,
            OrderItem.order_id == order_id
        ).first()

        if not item:
            return {"error": "Order item not found in this order"}

        return_obj = Return(
            order_id=order_id,
            order_item_id=order_item_id,
            reason=reason
        )
        db.add(return_obj)
        db.commit()

        return {"message": "Return created successfully", "return_id": return_obj.return_id}

    except Exception as e:
        print("Error creating return:", e)
        return {"error": "Unable to create return"}


def get_return_details(db, user_id: int, return_id: int):
    """Gets details of a particular return wrt user_id"""

    try:
        return_obj = db.query(Return).join(Order).filter(
            Return.return_id == return_id,
            Order.user_id == user_id
        ).first()

        if not return_obj:
            return {"error": "Return not found or does not belong to the user"}

        return {
            "return_id": return_obj.return_id,
            "order_id": return_obj.order_id,
            "order_item_id": return_obj.order_item_id,
            "reason": return_obj.reason,
            "status": return_obj.status,
            "created_at": str(return_obj.created_at)
        }

    except Exception as e:
        print("Error fetching return details:", e)
        return {"error": "Unable to fetch return details"}


def list_user_returns(db, user_id: int):
    """Summary list of all returns for a user"""

    try:
        returns = db.query(Return).join(Order).filter(
            Order.user_id == user_id
        ).all()

        all_returns = []
        for r in returns:
            all_returns.append({
                "return_id": r.return_id,
                "order_id": r.order_id,
                "status": r.status,
                "created_at": r.created_at.strftime("%d-%m-%Y %I:%M %p")
            })

        if not all_returns:
            return {"returns": []}

        return {"returns": all_returns}

    except Exception as e:
        print("Error fetching user returns:", e)
        return {"error": "Unable to fetch user returns"}


if __name__ == '__main__':
    db = SessionLocal()
    print(create_return(db,user_id=40,order_id=4,order_item_id=5,reason='No longer required'))