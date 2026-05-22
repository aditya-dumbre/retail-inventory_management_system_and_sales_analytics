"""
DBConnect and DBQueries classes — handles all database connectivity and query abstraction.
Backend: MySQL (mysql-connector-python)
"""

import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager


# ── Connection config — edit to match your MySQL server ───────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "Sammy@1212",
    "database": "retail_db",
    "port":     3306,
}


class DBConnect:
   
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pool = pooling.MySQLConnectionPool(
                pool_name="retail_pool",
                pool_size=5,
                **DB_CONFIG,
            )
        return cls._instance

    @contextmanager
    def get_connection(self):
        conn = self._pool.get_connection()
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self):
        """Create all tables if they don't exist, then seed demo data."""
        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    product_id    INT AUTO_INCREMENT PRIMARY KEY,
                    name          VARCHAR(150) NOT NULL,
                    sku           VARCHAR(50)  UNIQUE NOT NULL,
                    category      VARCHAR(80)  NOT NULL,
                    quantity      INT          NOT NULL DEFAULT 0,
                    unit_price    DECIMAL(12,2) NOT NULL,
                    reorder_level INT          NOT NULL DEFAULT 10,
                    supplier      VARCHAR(150),
                    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
                    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS manager (
                    manager_id    INT AUTO_INCREMENT PRIMARY KEY,
                    username      VARCHAR(80)  UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name     VARCHAR(150) NOT NULL,
                    email         VARCHAR(150) UNIQUE NOT NULL,
                    role          VARCHAR(40)  NOT NULL DEFAULT 'staff',
                    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS regions (
                    region_id   INT AUTO_INCREMENT PRIMARY KEY,
                    region_name VARCHAR(80)  UNIQUE NOT NULL,
                    country     VARCHAR(80)  NOT NULL,
                    manager_id  INT,
                    FOREIGN KEY (manager_id) REFERENCES manager(manager_id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id     INT AUTO_INCREMENT PRIMARY KEY,
                    order_type   ENUM('B2B','B2C','RESTOCK') NOT NULL,
                    product_id   INT  NOT NULL,
                    quantity     INT  NOT NULL,
                    unit_price   DECIMAL(12,2) NOT NULL,
                    total_amount DECIMAL(14,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
                    status       ENUM('pending','confirmed','shipped','delivered','cancelled')
                                 NOT NULL DEFAULT 'pending',
                    region_id    INT,
                    customer_ref VARCHAR(100),
                    order_date   DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notes        TEXT,
                    FOREIGN KEY (product_id) REFERENCES inventory(product_id),
                    FOREIGN KEY (region_id)  REFERENCES regions(region_id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id       INT AUTO_INCREMENT PRIMARY KEY,
                    order_id      INT  NOT NULL,
                    product_id    INT  NOT NULL,
                    region_id     INT,
                    quantity_sold INT  NOT NULL,
                    revenue       DECIMAL(14,2) NOT NULL,
                    sale_date     DATETIME DEFAULT CURRENT_TIMESTAMP,
                    channel       ENUM('B2B','B2C') NOT NULL,
                    FOREIGN KEY (order_id)   REFERENCES orders(order_id),
                    FOREIGN KEY (product_id) REFERENCES inventory(product_id),
                    FOREIGN KEY (region_id)  REFERENCES regions(region_id)
                )
            """)

            for ddl in [
                "CREATE INDEX idx_orders_product ON orders(product_id)",
                "CREATE INDEX idx_orders_status  ON orders(status)",
                "CREATE INDEX idx_sales_date     ON sales(sale_date)",
                "CREATE INDEX idx_sales_product  ON sales(product_id)",
                "CREATE INDEX idx_sales_region   ON sales(region_id)",
            ]:
                try:
                    cur.execute(ddl)
                except Exception:
                    pass  # index already exists

        self._seed_demo_data()

    def _seed_demo_data(self):
        """Insert demo rows only when tables are empty."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM manager")
            if cur.fetchone()[0] > 0:
                return

            cur.execute("""
                INSERT INTO manager (username, password_hash, full_name, email, role) VALUES
                  ('admin',    'pbkdf2:sha256:admin', 'Admin User', 'admin@retail.com',  'admin'),
                  ('mgr_west', 'pbkdf2:sha256:pass',  'Jane West',  'jane@retail.com',   'manager'),
                  ('mgr_east', 'pbkdf2:sha256:pass',  'John East',  'john@retail.com',   'manager')
            """)

            cur.execute("""
                INSERT INTO regions (region_name, country, manager_id) VALUES
                  ('North',  'India',  2),
                  ('South',  'India',  3),
                  ('East',   'India',  2),
                  ('West',   'India',  3),
                  ('Export', 'Global', 1)
            """)

            cur.execute("""
                INSERT INTO inventory (name, sku, category, quantity, unit_price, reorder_level, supplier) VALUES
                  ('Laptop Pro 15',   'LP-001', 'Electronics', 45,  85000, 10, 'TechWorld'),
                  ('Wireless Mouse',  'WM-002', 'Accessories', 200,  1200, 30, 'PeriphHub'),
                  ('USB-C Hub 7port', 'UH-003', 'Accessories', 130,  3500, 20, 'PeriphHub'),
                  ('4K Monitor 27"',  'MN-004', 'Electronics',  60, 32000,  8, 'ScreenCo'),
                  ('Mech Keyboard',   'KB-005', 'Accessories',  95,  7500, 15, 'TypeMaster'),
                  ('Office Chair',    'OC-006', 'Furniture',    30, 18000,  5, 'ComfortZone'),
                  ('Standing Desk',   'SD-007', 'Furniture',    18, 45000,  5, 'ComfortZone'),
                  ('Webcam HD 1080p', 'WC-008', 'Electronics',  75,  4500, 12, 'VisionTech'),
                  ('Noise Cancel HP', 'NC-009', 'Audio',        55, 12000, 10, 'SoundWave'),
                  ('Printer Laser',   'PL-010', 'Electronics',  22, 28000,  6, 'PrintPro')
            """)

            cur.execute("""
                INSERT INTO orders (order_type, product_id, quantity, unit_price, status, region_id, customer_ref) VALUES
                  ('B2C',     1,   2,  85000, 'delivered', 1, 'CUST-001'),
                  ('B2C',     2,   5,   1200, 'delivered', 2, 'CUST-002'),
                  ('B2B',     1,  10,  80000, 'delivered', 5, 'BIZ-001'),
                  ('B2B',     4,   8,  30000, 'shipped',   3, 'BIZ-002'),
                  ('B2C',     5,   3,   7500, 'delivered', 4, 'CUST-003'),
                  ('B2C',     9,   4,  12000, 'delivered', 1, 'CUST-004'),
                  ('B2B',     3,  20,   3200, 'confirmed', 2, 'BIZ-003'),
                  ('RESTOCK', 2, 100,    800, 'delivered', NULL, 'SUP-WM-002'),
                  ('B2C',     8,   6,   4500, 'pending',   3, 'CUST-005'),
                  ('B2B',     6,  15,  16000, 'shipped',   5, 'BIZ-004')
            """)

            cur.execute("""
                INSERT INTO sales (order_id, product_id, region_id, quantity_sold, revenue, channel) VALUES
                  (1,  1, 1,  2,  170000, 'B2C'),
                  (2,  2, 2,  5,    6000, 'B2C'),
                  (3,  1, 5, 10,  800000, 'B2B'),
                  (4,  4, 3,  8,  240000, 'B2B'),
                  (5,  5, 4,  3,   22500, 'B2C'),
                  (6,  9, 1,  4,   48000, 'B2C'),
                  (10, 6, 5, 15,  240000, 'B2B')
            """)


class DBQueries:
    """All SQL query methods — never executed outside this class."""

    def __init__(self):
        self._db = DBConnect()

    def _fetchall(self, conn, sql, params=()):
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchall()

    def _fetchone(self, conn, sql, params=()):
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchone()

    # ── Inventory ──────────────────────────────────────────────────────────

    def get_all_inventory(self):
        with self._db.get_connection() as conn:
            return self._fetchall(conn,
                "SELECT * FROM inventory ORDER BY category, name")

    def get_product(self, product_id):
        with self._db.get_connection() as conn:
            return self._fetchone(conn,
                "SELECT * FROM inventory WHERE product_id=%s", (product_id,))

    def add_product(self, data: dict):
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO inventory (name, sku, category, quantity, unit_price, reorder_level, supplier)
                VALUES (%(name)s, %(sku)s, %(category)s, %(quantity)s,
                        %(unit_price)s, %(reorder_level)s, %(supplier)s)
            """, data)

    def update_product(self, product_id: int, data: dict):
        data["product_id"] = product_id
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE inventory
                SET name=%(name)s, sku=%(sku)s, category=%(category)s,
                    quantity=%(quantity)s, unit_price=%(unit_price)s,
                    reorder_level=%(reorder_level)s, supplier=%(supplier)s
                WHERE product_id=%(product_id)s
            """, data)

    def delete_product(self, product_id: int):
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM inventory WHERE product_id=%s", (product_id,))

    def get_low_stock(self):
        with self._db.get_connection() as conn:
            return self._fetchall(conn,
                "SELECT * FROM inventory WHERE quantity <= reorder_level ORDER BY quantity")

    def adjust_stock(self, product_id: int, delta: int):
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE inventory SET quantity = quantity + %s WHERE product_id = %s",
                (delta, product_id))

    # ── Orders ─────────────────────────────────────────────────────────────

    def get_all_orders(self, order_type=None):
        sql = """
            SELECT o.*, i.name product_name, r.region_name
            FROM orders o
            JOIN inventory i ON o.product_id = i.product_id
            LEFT JOIN regions r ON o.region_id = r.region_id
        """
        params = ()
        if order_type:
            sql += " WHERE o.order_type = %s"
            params = (order_type,)
        sql += " ORDER BY o.order_date DESC"
        with self._db.get_connection() as conn:
            return self._fetchall(conn, sql, params)

    def get_order(self, order_id):
        with self._db.get_connection() as conn:
            return self._fetchone(conn, """
                SELECT o.*, i.name product_name, r.region_name
                FROM orders o
                JOIN inventory i ON o.product_id = i.product_id
                LEFT JOIN regions r ON o.region_id = r.region_id
                WHERE o.order_id = %s
            """, (order_id,))

    def create_order(self, data: dict):
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO orders (order_type, product_id, quantity, unit_price,
                                    status, region_id, customer_ref, notes)
                VALUES (%(order_type)s, %(product_id)s, %(quantity)s, %(unit_price)s,
                        %(status)s, %(region_id)s, %(customer_ref)s, %(notes)s)
            """, data)
            return cur.lastrowid

    def update_order_status(self, order_id: int, status: str):
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE orders SET status=%s WHERE order_id=%s", (status, order_id))

    # ── Sales Analytics ────────────────────────────────────────────────────

    def record_sale(self, data: dict):
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sales (order_id, product_id, region_id, quantity_sold, revenue, channel)
                VALUES (%(order_id)s, %(product_id)s, %(region_id)s,
                        %(quantity_sold)s, %(revenue)s, %(channel)s)
            """, data)

    def total_revenue(self):
        with self._db.get_connection() as conn:
            row = self._fetchone(conn, "SELECT COALESCE(SUM(revenue), 0) AS total FROM sales")
            return float(row["total"])

    def revenue_by_channel(self):
        with self._db.get_connection() as conn:
            return self._fetchall(conn,
                "SELECT channel, SUM(revenue) revenue, COUNT(*) orders FROM sales GROUP BY channel")

    def revenue_by_region(self):
        with self._db.get_connection() as conn:
            return self._fetchall(conn, """
                SELECT r.region_name, SUM(s.revenue) revenue, SUM(s.quantity_sold) units
                FROM sales s
                JOIN regions r ON s.region_id = r.region_id
                GROUP BY r.region_name
                ORDER BY revenue DESC
            """)

    def top_products(self, limit=5):
        with self._db.get_connection() as conn:
            return self._fetchall(conn, """
                SELECT i.name, i.sku, SUM(s.revenue) revenue, SUM(s.quantity_sold) units
                FROM sales s
                JOIN inventory i ON s.product_id = i.product_id
                GROUP BY i.product_id, i.name, i.sku
                ORDER BY revenue DESC
                LIMIT %s
            """, (limit,))

    def monthly_revenue(self):
        with self._db.get_connection() as conn:
            return self._fetchall(conn, """
                SELECT DATE_FORMAT(sale_date, '%Y-%m') AS month, SUM(revenue) revenue
                FROM sales
                GROUP BY month
                ORDER BY month
            """)

    def get_all_regions(self):
        with self._db.get_connection() as conn:
            return self._fetchall(conn, "SELECT * FROM regions")

    def get_kpis(self):
        with self._db.get_connection() as conn:
            total_rev    = self._fetchone(conn, "SELECT COALESCE(SUM(revenue),0) v FROM sales")["v"]
            total_orders = self._fetchone(conn, "SELECT COUNT(*) v FROM orders WHERE order_type != 'RESTOCK'")["v"]
            low_stock    = self._fetchone(conn, "SELECT COUNT(*) v FROM inventory WHERE quantity <= reorder_level")["v"]
            pending      = self._fetchone(conn, "SELECT COUNT(*) v FROM orders WHERE status='pending'")["v"]
            return {
                "total_revenue":   float(total_rev or 0),
                "total_orders":    total_orders,
                "low_stock_count": low_stock,
                "pending_orders":  pending,
            }

    # ── Auth ───────────────────────────────────────────────────────────────

    def get_manager_by_username(self, username: str):
        with self._db.get_connection() as conn:
            return self._fetchone(conn,
                "SELECT * FROM manager WHERE username = %s", (username,))
