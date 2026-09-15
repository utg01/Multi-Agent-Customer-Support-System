from app.core.db.models import Product

def get_product_info(db, product_id: int):
    """This function fetches product details wrt product_id"""

    try:
        product = db.query(Product).filter(
            Product.prod_id == product_id
        ).first()

        if not product:
            return {"error": "Product not found"}

        return {
            "prod_id": product.prod_id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "stock": product.stock,
            "category": product.category
        }

    except Exception as e:
        print("Error fetching product details:", e)
        return {"error": "Unable to fetch product details"}


