from app.core.db.models import Order, OrderItem,Product
from sqlalchemy.orm import Session
from app.agent.tools.product_tools import get_ordered_products
from app.core.db.base import SessionLocal
from app.utils.imptools import get_product_info

def get_order_details(db: Session, user_id: int, order_id: int):
    """Gets all order details wrt to user and a particular order id"""

    try:
        order = db.query(Order).filter(
            Order.order_id == order_id,
            Order.user_id == user_id
        ).first()

        if not order:
            return {'error': 'Order not found or does not belong to the user'}

        od_product_details = get_ordered_products(db, order_id)

        return {
            'order_id': order_id,
            "user_id": user_id,
            "all ordered prod details": od_product_details,
            "total_amount": order.total_amount,
            "created_at": str(order.created_at),
            'status': order.status
        }

    except Exception as e:
        print("Error fetching order details:", e)
        return {'error': 'Unable to fetch order details'}

def get_user_orders(db,user_id:int):
    """Summary list of all orders for user, no item breakdown"""
    try:
        orders=db.query(Order).filter(
            Order.user_id==user_id
        ).all()
        all_orders=[]
        for order in orders:
            all_orders.append({
                'order_id':order.order_id,
                'total_amount':order.total_amount,
                'status':order.status,
                'created-at':order.created_at.strftime("%d-%m-%Y %I:%M %p")
            })
        if not all_orders:
            return "No orders for this user"            
        else:
            return all_orders
    except Exception as e:
        return {'error':"Error fetching user orders"+str(e)}



def place_order(db, user_id: int, product_id: int, quantity: int):
    """Checks stock, creates Order + Orderitem"""

    try:
        product_info = get_product_info(db, product_id)
        if "error" in product_info:
            return product_info
        if quantity <= product_info['stock']:
            order = Order(
                user_id=user_id,
                total_amount=0
            )
            db.add(order)
            db.flush()
            item = OrderItem(
                order_id=order.order_id,
                product_id=product_info['prod_id'],
                quantity=quantity,
                price_at_purchase=product_info['price']
            )
            db.add(item)

            product = db.query(Product).filter(
                Product.prod_id == product_id
            ).first()
            product.stock -= quantity
            total = quantity * product_info['price']
            order.total_amount = total
            db.commit()
            return f"order placed successfully, order_id={order.order_id}"

        else:
            return {
                "error": f"stock not available, only {product_info['stock']} available"
            }

    except Exception as e:
        print("Error placing order:", e)
        return {"error": "Unable to place order"}
    
def cancel_order_item(db, user_id: int, order_id: int):
    """Cancels order wrt to user_id and order_id"""
    try:
        order_details = get_order_details(db, user_id, order_id)
        if "error" in order_details:
            return order_details

        if order_details['status'].lower() != 'delivered':
            order = db.query(Order).filter(
                Order.user_id == user_id,
                Order.order_id == order_id
            ).first()

            # restore stock for every item in this order before cancelling
            items = db.query(OrderItem).filter(
                OrderItem.order_id == order_id
            ).all()
            for item in items:
                product = db.query(Product).filter(
                    Product.prod_id == item.product_id
                ).first()
                if product:
                    product.stock += item.quantity

            order.status = 'cancelled'
            db.commit()

        return {"message": "Order cancelled successfully"}
    except Exception as e:
        print("Error cancelling order:", e)
        return {"error": "Unable to cancel order"}

def modify_order(db, user_id: int, order_id: int, new_items: list):
    """
    Modifies an order by cancelling it entirely (restores stock for all items),
    then placing new order(s) for the items specified in new_items.
    new_items: list of dicts, e.g. [{"product_id": 5, "quantity": 2}, {"product_id": 8, "quantity": 1}]
    """
    try:
        order_details = get_order_details(db, user_id, order_id)
        if "error" in order_details:
            return order_details

        if order_details['status'].lower() != 'placed':
            return {
                "error": "Order can only be modified while it is placed"
            }

        cancel_result = cancel_order_item(db, user_id, order_id)
        if "error" in cancel_result:
            return cancel_result

        new_orders = []
        for item in new_items:
            result = place_order(db, user_id, item['product_id'], item['quantity'])
            new_orders.append(result)

        return {
            "message": "Order modified successfully",
            "new_orders": new_orders
        }
    except Exception as e:
        print("Error modifying order:", e)
        return {"error": "Unable to modify order"}

if __name__=='__main__':
    db=SessionLocal()
    print(cancel_order_item(db,2,151))