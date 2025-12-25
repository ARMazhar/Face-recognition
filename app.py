from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from flask import Flask, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "store.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    description: str
    price: int
    image_url: str


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price INTEGER NOT NULL,
                image_url TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """
        )

        cursor = connection.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        if count == 0:
            connection.executemany(
                """
                INSERT INTO products (name, description, price, image_url)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "هدست بی‌سیم",
                        "کیفیت صدای شفاف با عمر باتری ۲۰ ساعته",
                        1450000,
                        "https://images.unsplash.com/photo-1518441988334-5d2fede6e7e4?auto=format&fit=crop&w=600&q=80",
                    ),
                    (
                        "لپ‌تاپ سبک",
                        "مناسب برای کارهای روزمره و سفر",
                        24800000,
                        "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=600&q=80",
                    ),
                    (
                        "ساعت هوشمند",
                        "ردیابی فعالیت‌های ورزشی و اعلان‌ها",
                        3950000,
                        "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=600&q=80",
                    ),
                ],
            )


@app.before_request
def ensure_database() -> None:
    if not DB_PATH.exists():
        init_db()


def fetch_products() -> Iterable[Product]:
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM products").fetchall()
    return [
        Product(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            price=row["price"],
            image_url=row["image_url"],
        )
        for row in rows
    ]


def fetch_product(product_id: int) -> Product | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    if row is None:
        return None
    return Product(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        price=row["price"],
        image_url=row["image_url"],
    )


def get_cart() -> dict[str, int]:
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart


def save_cart(cart: dict[str, int]) -> None:
    session["cart"] = cart


@app.route("/")
def index() -> str:
    products = fetch_products()
    cart = get_cart()
    cart_size = sum(cart.values())
    return render_template("index.html", products=products, cart_size=cart_size)


@app.route("/products/<int:product_id>")
def product_detail(product_id: int) -> str:
    product = fetch_product(product_id)
    if product is None:
        return render_template("not_found.html"), 404
    return render_template("product.html", product=product)


@app.route("/cart")
def view_cart() -> str:
    cart = get_cart()
    products = []
    total = 0
    for product_id, quantity in cart.items():
        product = fetch_product(int(product_id))
        if product is None:
            continue
        item_total = product.price * quantity
        total += item_total
        products.append(
            {
                "product": product,
                "quantity": quantity,
                "item_total": item_total,
            }
        )
    return render_template("cart.html", items=products, total=total)


@app.route("/cart/add", methods=["POST"])
def add_to_cart() -> str:
    product_id = request.form.get("product_id")
    if not product_id:
        return redirect(url_for("index"))
    cart = get_cart()
    cart[product_id] = cart.get(product_id, 0) + 1
    save_cart(cart)
    return redirect(url_for("view_cart"))


@app.route("/cart/remove", methods=["POST"])
def remove_from_cart() -> str:
    product_id = request.form.get("product_id")
    if not product_id:
        return redirect(url_for("view_cart"))
    cart = get_cart()
    if product_id in cart:
        cart.pop(product_id)
    save_cart(cart)
    return redirect(url_for("view_cart"))


@app.route("/checkout", methods=["POST"])
def checkout() -> str:
    cart = get_cart()
    if not cart:
        return redirect(url_for("index"))
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO orders (created_at) VALUES (datetime('now'))"
        )
    session.pop("cart", None)
    return render_template("checkout.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
