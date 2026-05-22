"""
Flask application — Views layer.
Routes delegate to controllers; controllers delegate to models.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, session)
from models.db import DBConnect, DBQueries
from controllers.controllers import InventoryController, OrdersController, AnalyticsController

app = Flask(__name__)
app.secret_key = "retail-secret-2024"

# Initialise DB on startup
DBConnect().initialize_schema()

inv_ctrl = InventoryController()
ord_ctrl = OrdersController()
ana_ctrl = AnalyticsController()
_q       = DBQueries()


# ─────────────────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f):
    """Redirect to login if the user is not in session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def _check_password(stored_hash: str, password: str) -> bool:
    """
    Simple check against the seeded demo hashes (format: 'pbkdf2:sha256:<plain>').
    In production, replace with werkzeug.security.check_password_hash.
    """
    # Demo hashes store the plaintext after the last colon
    parts = stored_hash.split(":")
    return parts[-1] == password


# ─────────────────────────────────────────────────────────────────────────────
# Login / Logout
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        manager = _q.get_manager_by_username(username)

        if manager and _check_password(manager["password_hash"], password):
            session["user_id"]   = manager["manager_id"]
            session["username"]  = manager["username"]
            session["full_name"] = manager["full_name"]
            session["role"]      = manager["role"]
            flash(f"Welcome back, {manager['full_name']}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")
        return render_template("login.html", prefill_username=username)

    return render_template("login.html")


@app.route("/logout")
def logout():
    name = session.get("full_name", "")
    session.clear()
    flash(f"You have been signed out{', ' + name if name else ''}.", "success")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    data = ana_ctrl.dashboard()
    return render_template("dashboard.html", **data)


# ─────────────────────────────────────────────────────────────────────────────
# Inventory routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/inventory")
@login_required
def inventory_list():
    data = inv_ctrl.list_products()
    return render_template("inventory/list.html", **data)

@app.route("/inventory/add", methods=["GET", "POST"])
@login_required
def inventory_add():
    if request.method == "POST":
        result, code = inv_ctrl.create_product(request.form)
        if code == 201:
            flash(result["message"], "success")
            return redirect(url_for("inventory_list"))
        flash("; ".join(result.get("errors", [result.get("error", "")])), "danger")
    return render_template("inventory/add.html")

@app.route("/inventory/<int:product_id>")
@login_required
def inventory_detail(product_id):
    data = inv_ctrl.product_detail(product_id)
    if "error" in data:
        flash(data["error"], "danger")
        return redirect(url_for("inventory_list"))
    return render_template("inventory/detail.html", **data)

@app.route("/inventory/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def inventory_edit(product_id):
    if request.method == "POST":
        result, code = inv_ctrl.edit_product(product_id, request.form)
        if code == 200:
            flash(result["message"], "success")
            return redirect(url_for("inventory_list"))
        flash(str(result), "danger")
    data = inv_ctrl.product_detail(product_id)
    return render_template("inventory/edit.html", **data)

@app.route("/inventory/<int:product_id>/delete", methods=["POST"])
@login_required
def inventory_delete(product_id):
    result, code = inv_ctrl.remove_product(product_id)
    flash(result.get("message", result.get("error")), "success" if code == 200 else "danger")
    return redirect(url_for("inventory_list"))

@app.route("/inventory/low-stock")
@login_required
def low_stock():
    data = inv_ctrl.low_stock_report()
    return render_template("inventory/low_stock.html", **data)


# ─────────────────────────────────────────────────────────────────────────────
# Orders routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/orders")
@login_required
def orders_list():
    order_type = request.args.get("type")
    data = ord_ctrl.list_orders(order_type)
    return render_template("orders/list.html", order_type=order_type, **data)

@app.route("/orders/create/<order_type>", methods=["GET", "POST"])
@login_required
def orders_create(order_type):
    order_type = order_type.upper()
    if order_type not in ("B2B", "B2C", "RESTOCK"):
        flash("Invalid order type", "danger")
        return redirect(url_for("orders_list"))
    if request.method == "POST":
        result, code = ord_ctrl.create_order(order_type, request.form)
        if code == 201:
            flash(result["message"], "success")
            return redirect(url_for("orders_list"))
        flash(result.get("error", str(result)), "danger")
    data = ord_ctrl.list_orders()
    return render_template("orders/create.html", order_type=order_type, **data)

@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    data = ord_ctrl.order_detail(order_id)
    if "error" in data:
        flash(data["error"], "danger")
        return redirect(url_for("orders_list"))
    return render_template("orders/detail.html", **data)

@app.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def order_status(order_id):
    status = request.form.get("status")
    result, code = ord_ctrl.change_status(order_id, status)
    flash(result.get("message", result.get("error")), "success" if code == 200 else "danger")
    return redirect(url_for("order_detail", order_id=order_id))


# ─────────────────────────────────────────────────────────────────────────────
# Analytics routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/analytics")
@login_required
def analytics():
    data = ana_ctrl.dashboard()
    return render_template("analytics/dashboard.html", **data)

@app.route("/api/analytics/channels")
@login_required
def api_channels():
    return jsonify(ana_ctrl.channel_breakdown())

@app.route("/api/analytics/regions")
@login_required
def api_regions():
    return jsonify(ana_ctrl.region_breakdown())

@app.route("/api/analytics/top-products")
@login_required
def api_top_products():
    return jsonify(ana_ctrl.top_products())

@app.route("/api/analytics/monthly")
@login_required
def api_monthly():
    return jsonify(ana_ctrl.monthly_trend())


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
