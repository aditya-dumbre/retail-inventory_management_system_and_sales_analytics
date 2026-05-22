"""
Domain models following the class hierarchy specified.

Inventory
Orders (abstract)
  ├── B2BOrders
  ├── B2COrders
  └── Restock
Manager (abstract)
  └── InventoryManager  (has-an Inventory)
SalesAnalytics
"""

from abc import ABC, abstractmethod
from models.db import DBQueries


# ─────────────────────────────────────────────────────────────────────────────
# Inventory
# ─────────────────────────────────────────────────────────────────────────────

class Inventory:
    """Represents the product inventory and stock-level operations."""

    def __init__(self):
        self._q = DBQueries()

    # ── CRUD ──────────────────────────────────────────────────────────────

    def all_products(self) -> list[dict]:
        return self._q.get_all_inventory()

    def get_product(self, product_id: int) -> dict | None:
        return self._q.get_product(product_id)

    def add_product(self, name: str, sku: str, category: str,
                    quantity: int, unit_price: float,
                    reorder_level: int = 10, supplier: str = "") -> None:
        self._q.add_product({
            "name": name, "sku": sku, "category": category,
            "quantity": quantity, "unit_price": unit_price,
            "reorder_level": reorder_level, "supplier": supplier,
        })

    def update_product(self, product_id: int, **kwargs) -> None:
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        product.update(kwargs)
        self._q.update_product(product_id, product)

    def delete_product(self, product_id: int) -> None:
        self._q.delete_product(product_id)

    # ── Stock ─────────────────────────────────────────────────────────────

    def low_stock_items(self) -> list[dict]:
        return self._q.get_low_stock()

    def restock_product(self, product_id: int, qty: int) -> None:
        if qty <= 0:
            raise ValueError("Restock quantity must be positive")
        self._q.adjust_stock(product_id, qty)

    def deduct_stock(self, product_id: int, qty: int) -> None:
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        if product["quantity"] < qty:
            raise ValueError("Insufficient stock")
        self._q.adjust_stock(product_id, -qty)

    def categories(self) -> list[str]:
        return sorted({p["category"] for p in self.all_products()})


# ─────────────────────────────────────────────────────────────────────────────
# Orders (abstract base)
# ─────────────────────────────────────────────────────────────────────────────

class Orders(ABC):
    
    ORDER_TYPE: str = ""          # overridden by subclasses

    def __init__(self):
        self._q = DBQueries()

    # ── Abstract interface ────────────────────────────────────────────────

    @abstractmethod
    def place_order(self, product_id: int, quantity: int,
                    unit_price: float, **kwargs) -> int:
        """Create an order and return its order_id."""

    @abstractmethod
    def validate_order(self, product_id: int, quantity: int) -> bool:
        """Return True if the order can be placed."""

    # ── Shared helpers ────────────────────────────────────────────────────

    def get_orders(self) -> list[dict]:
        return self._q.get_all_orders(self.ORDER_TYPE)

    def get_order(self, order_id: int) -> dict | None:
        return self._q.get_order(order_id)

    def update_status(self, order_id: int, status: str) -> None:
        allowed = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
        if status not in allowed:
            raise ValueError(f"Invalid status '{status}'")
        self._q.update_order_status(order_id, status)

    def _base_payload(self, product_id, quantity, unit_price, **kwargs) -> dict:
        return {
            "order_type":   self.ORDER_TYPE,
            "product_id":   product_id,
            "quantity":     quantity,
            "unit_price":   unit_price,
            "status":       kwargs.get("status", "pending"),
            "region_id":    kwargs.get("region_id"),
            "customer_ref": kwargs.get("customer_ref", ""),
            "notes":        kwargs.get("notes", ""),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Restock
# ─────────────────────────────────────────────────────────────────────────────

class Restock(Orders):

    ORDER_TYPE = "RESTOCK"

    def validate_order(self, product_id: int, quantity: int) -> bool:
        if quantity <= 0:
            return False
        product = self._q.get_product(product_id)
        return product is not None

    def place_order(self, product_id: int, quantity: int,
                    unit_price: float, **kwargs) -> int:
        if not self.validate_order(product_id, quantity):
            raise ValueError("Invalid restock order")
        payload = self._base_payload(product_id, quantity, unit_price, **kwargs)
        order_id = self._q.create_order(payload)
        # Immediately add stock on restock
        self._q.adjust_stock(product_id, quantity)
        return order_id

    def get_orders(self) -> list[dict]:
        return self._q.get_all_orders("RESTOCK")


# ─────────────────────────────────────────────────────────────────────────────
# B2BOrders
# ─────────────────────────────────────────────────────────────────────────────

class B2BOrders(Orders):

    ORDER_TYPE = "B2B"

    BULK_THRESHOLD = 10          # minimum qty for a B2B order
    BULK_DISCOUNT  = 0.05        # 5 % discount on unit price

    def validate_order(self, product_id: int, quantity: int) -> bool:
        if quantity < self.BULK_THRESHOLD:
            return False
        product = self._q.get_product(product_id)
        if not product:
            return False
        return product["quantity"] >= quantity

    def place_order(self, product_id: int, quantity: int,
                    unit_price: float, **kwargs) -> int:
        if not self.validate_order(product_id, quantity):
            raise ValueError(
                f"B2B orders require ≥ {self.BULK_THRESHOLD} units and sufficient stock."
            )
        # Apply B2B bulk discount
        discounted_price = round(unit_price * (1 - self.BULK_DISCOUNT), 2)
        payload = self._base_payload(product_id, quantity, discounted_price, **kwargs)
        order_id = self._q.create_order(payload)
        self._q.adjust_stock(product_id, -quantity)
        return order_id

    def effective_price(self, unit_price: float) -> float:
        return round(unit_price * (1 - self.BULK_DISCOUNT), 2)


# ─────────────────────────────────────────────────────────────────────────────
# B2COrders
# ─────────────────────────────────────────────────────────────────────────────

class B2COrders(Orders):

    ORDER_TYPE = "B2C"

    MAX_QTY = 50          # single-order cap for retail customers

    def validate_order(self, product_id: int, quantity: int) -> bool:
        if not (1 <= quantity <= self.MAX_QTY):
            return False
        product = self._q.get_product(product_id)
        if not product:
            return False
        return product["quantity"] >= quantity

    def place_order(self, product_id: int, quantity: int,
                    unit_price: float, **kwargs) -> int:
        if not self.validate_order(product_id, quantity):
            raise ValueError(
                f"B2C orders must be between 1 and {self.MAX_QTY} units with sufficient stock."
            )
        payload = self._base_payload(product_id, quantity, unit_price, **kwargs)
        order_id = self._q.create_order(payload)
        self._q.adjust_stock(product_id, -quantity)
        return order_id


# ─────────────────────────────────────────────────────────────────────────────
# Manager (abstract)
# ─────────────────────────────────────────────────────────────────────────────

class Manager(ABC):

    def __init__(self, manager_id: int, username: str,
                 full_name: str, email: str, role: str):
        self.manager_id = manager_id
        self.username   = username
        self.full_name  = full_name
        self.email      = email
        self.role       = role

    @abstractmethod
    def get_dashboard_data(self) -> dict:
        """Return role-specific dashboard metrics."""

    @abstractmethod
    def can_approve_order(self, order: dict) -> bool:
        """Return True if this manager can approve the given order."""

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.username} ({self.role})>"


# ─────────────────────────────────────────────────────────────────────────────
# InventoryManager  (has-an Inventory)
# ─────────────────────────────────────────────────────────────────────────────

class InventoryManager(Manager):

    def __init__(self, manager_id: int, username: str,
                 full_name: str, email: str, role: str = "manager"):
        super().__init__(manager_id, username, full_name, email, role)
        self.inventory  = Inventory()          # has-a Inventory
        self._q         = DBQueries()

    # ── Manager abstract impl ─────────────────────────────────────────────

    def get_dashboard_data(self) -> dict:
        kpis      = self._q.get_kpis()
        low_stock = self.inventory.low_stock_items()
        return {"kpis": kpis, "low_stock": low_stock}

    def can_approve_order(self, order: dict) -> bool:
        if self.role == "admin":
            return True
        # Managers can approve orders up to ₹500,000
        return order.get("total_amount", 0) <= 500_000

    # ── Inventory delegation ──────────────────────────────────────────────

    def add_product(self, **kwargs) -> None:
        self.inventory.add_product(**kwargs)

    def update_product(self, product_id: int, **kwargs) -> None:
        self.inventory.update_product(product_id, **kwargs)

    def remove_product(self, product_id: int) -> None:
        self.inventory.delete_product(product_id)

    def trigger_restock(self, product_id: int, qty: int,
                        unit_price: float) -> int:
        restock = Restock()
        return restock.place_order(product_id, qty, unit_price,
                                   customer_ref=f"AUTO-MGR-{self.manager_id}")


# ─────────────────────────────────────────────────────────────────────────────
# SalesAnalytics
# ─────────────────────────────────────────────────────────────────────────────

class SalesAnalytics:

    def __init__(self):
        self._q = DBQueries()

    def kpis(self) -> dict:
        return self._q.get_kpis()

    def total_revenue(self) -> float:
        return self._q.total_revenue()

    def revenue_by_channel(self) -> list[dict]:
        return self._q.revenue_by_channel()

    def revenue_by_region(self) -> list[dict]:
        return self._q.revenue_by_region()

    def top_products(self, limit: int = 5) -> list[dict]:
        return self._q.top_products(limit)

    def monthly_trend(self) -> list[dict]:
        return self._q.monthly_revenue()

    def record_sale(self, order_id: int, product_id: int, region_id: int,
                    quantity_sold: int, revenue: float, channel: str) -> None:
        self._q.record_sale({
            "order_id":      order_id,
            "product_id":    product_id,
            "region_id":     region_id,
            "quantity_sold": quantity_sold,
            "revenue":       revenue,
            "channel":       channel,
        })

    def summary(self) -> dict:
        return {
            "kpis":             self.kpis(),
            "by_channel":       self.revenue_by_channel(),
            "by_region":        self.revenue_by_region(),
            "top_products":     self.top_products(),
            "monthly_trend":    self.monthly_trend(),
        }
