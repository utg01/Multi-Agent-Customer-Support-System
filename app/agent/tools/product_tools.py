from app.core.db.models import Product, OrderItem, Order
from app.utils.imptools import get_product_info
from app.core.db.base import SessionLocal

def get_ordered_products(db, order_id:int):

    try:
        items = db.query(OrderItem).filter(
            OrderItem.order_id == order_id
        ).all()

        ordered_products = []
        for item in items:
            product_info = get_product_info(db, item.product_id)

            ordered_products.append({
                'orderitem_id': item.orderitem_id,
                'product_id': item.product_id,
                'Product_name': product_info['name'],
                'quantity': item.quantity,
                'price': item.price_at_purchase
            })

        return ordered_products

    except Exception as e:
        return {"error": "Error fetching ordered products: " + str(e)}

from typing import Optional

def search_products(db, keyword: Optional[str]=None, category: Optional[str]=None):
    """Searches products by keyword (matches name) and/or category. Returns a lightweight list."""

    try:
        query = db.query(Product)
        if keyword:
            query = query.filter(Product.name.ilike(f"%{keyword}%"))

        if category:
            query = query.filter(Product.category.ilike(f"%{category}%"))

        products = query.all()
        if not products:
            return {"products": []}

        return {
            "products": [
                {
                    "prod_id": p.prod_id,
                    "name": p.name,
                    "price": p.price,
                    "category": p.category,
                    "in_stock": p.stock > 0
                }
                for p in products
            ]
        }
    except Exception as e:
        print("Error searching products:", e)
        return {"error": "Unable to search products"}

    
if __name__=='__main__':
    db=SessionLocal()
    print(get_ordered_products(db,1))