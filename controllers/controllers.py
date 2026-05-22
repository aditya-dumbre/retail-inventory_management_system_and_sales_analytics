"""
Controllers — MVC middle layer.
Each controller exposes methods called by Flask route functions.
All business logic is delegated to the models.
"""

from models.models import Inventory, B2BOrders, B2COrders, Restock, InventoryManager, SalesAnalytics
from models.db import DBQueries


# ─────────────────────────────────────────────────────────────────────────────
# Inventory Controller
# ─────────────────────────────────────────────────────────────────────────────

class InventoryController:

    def __init__(self):
        self._inv = Inventory()

    def list_products(self):
        return {"products": self._inv.all_products(),
                "categories": self._inv.categories()}

    def product_detail(self, product_id: int):
        p = self._inv.get_product(product_id)
        if not p:
            return {"error": "Product not found"}, 404
        return {"product": p}

    def create_product(self, form: dict):
        errors = self._validate_product_form(form)
        if errors:
            return {"errors": errors}, 400
        try:
            self._inv.add_product(
                name=form["name"], sku=form["sku"],
                category=form["category"],
                quantity=int(form["quantity"]),
                unit_price=float(form["unit_price"]),
                reorder_level=int(form.get("reorder_level", 10)),
                supplier=form.get("supplier", ""),
            )
            return {"message": "Product added successfully"}, 201
        except Exception as e:
            return {"error": str(e)}, 500

    def edit_product(self, product_id: int, form: dict):
        errors = self._validate_product_form(form)
        if errors:
            return {"errors": errors}, 400
        try:
            self._inv.update_product(
                product_id,
                name=form["name"], sku=form["sku"],
                category=form["category"],
                quantity=int(form["quantity"]),
                unit_price=float(form["unit_price"]),
                reorder_level=int(form.get("reorder_level", 10)),
                supplier=form.get("supplier", ""),
            )
            return {"message": "Product updated"}, 200
        except ValueError as e:
            return {"error": str(e)}, 404

    def remove_product(self, product_id: int):
        try:
            self._inv.delete_product(product_id)
            return {"message": "Product deleted"}, 200
        except Exception as e:
            return {"error": str(e)}, 500

    def low_stock_report(self):
        return {"items": self._inv.low_stock_items()}

    def _validate_product_form(self, form: dict) -> list[str]:
        errors = []
        for field in ("name", "sku", "category", "quantity", "unit_price"):
            if not form.get(field):
                errors.append(f"'{field}' is required")
        try:
            if float(form.get("unit_price", -1)) <= 0:
                errors.append("unit_price must be positive")
        except (TypeError, ValueError):
            errors.append("unit_price must be a number")
        try:
            if int(form.get("quantity", -1)) < 0:
                errors.append("quantity must be ≥ 0")
        except (TypeError, ValueError):
            errors.append("quantity must be an integer")
        return errors


# ─────────────────────────────────────────────────────────────────────────────
# Orders Controller
# ─────────────────────────────────────────────────────────────────────────────

class OrdersController:

    def __init__(self):
        self._b2b  = B2BOrders()
        self._b2c  = B2COrders()
        self._rst  = Restock()
        self._q    = DBQueries()
        self._inv  = Inventory()

    def _handler(self, order_type: str):
        return {"B2B": self._b2b, "B2C": self._b2c, "RESTOCK": self._rst}[order_type]

    def list_orders(self, order_type: str = None):
        orders = self._q.get_all_orders(order_type)
        regions = self._q.get_all_regions()
        return {"orders": orders, "regions": regions,
                "products": self._inv.all_products()}

    def order_detail(self, order_id: int):
        order = self._q.get_order(order_id)
        if not order:
            return {"error": "Order not found"}, 404
        return {"order": order}

    def create_order(self, order_type: str, form: dict):
        errors = self._validate_order_form(form)
        if errors:
            return {"errors": errors}, 400
        try:
            handler = self._handler(order_type)
            order_id = handler.place_order(
                product_id=int(form["product_id"]),
                quantity=int(form["quantity"]),
                unit_price=float(form["unit_price"]),
                region_id=form.get("region_id") or None,
                customer_ref=form.get("customer_ref", ""),
                notes=form.get("notes", ""),
            )
            return {"message": f"Order #{order_id} created", "order_id": order_id}, 201
        except ValueError as e:
            return {"error": str(e)}, 400
        except Exception as e:
            return {"error": str(e)}, 500

    def change_status(self, order_id: int, status: str):
        try:
            # Use any handler — update_status is shared
            self._b2b.update_status(order_id, status)
            return {"message": f"Order status updated to '{status}'"}, 200
        except ValueError as e:
            return {"error": str(e)}, 400

    def _validate_order_form(self, form: dict) -> list[str]:
        errors = []
        for field in ("product_id", "quantity", "unit_price"):
            if not form.get(field):
                errors.append(f"'{field}' is required")
        return errors


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Controller
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsController:

    def __init__(self):
        self._sa = SalesAnalytics()

    def dashboard(self):
        return self._sa.summary()

    def kpis(self):
        return self._sa.kpis()

    def channel_breakdown(self):
        return {"data": self._sa.revenue_by_channel()}

    def region_breakdown(self):
        return {"data": self._sa.revenue_by_region()}

    def top_products(self, limit: int = 5):
        return {"data": self._sa.top_products(limit)}

    def monthly_trend(self):
        return {"data": self._sa.monthly_trend()}
