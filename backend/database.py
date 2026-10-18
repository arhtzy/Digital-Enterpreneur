"""SQLite data access for the digital-store bot and admin dashboard."""

from __future__ import annotations

import csv
import io
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional, List, Dict
import aiosqlite
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
if (BASE_DIR / ".env").exists():
    load_dotenv(dotenv_path=BASE_DIR / ".env")
load_dotenv()

env_db = os.getenv("DATABASE_URL", "toko_digital.db")
if os.path.isabs(env_db):
    DB_NAME = str(Path(env_db))
else:
    DB_NAME = str((BASE_DIR / env_db).resolve())

DEFAULT_CATEGORY_NAME = "Uncategorized"


def get_sync_connection() -> sqlite3.Connection:
    """Returns a synchronous SQLite connection for quick scripts/backups."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


async def _column_names(db: aiosqlite.Connection, table: str) -> set[str]:
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        return {row[1] for row in await cursor.fetchall()}


async def _ensure_default_category(db: aiosqlite.Connection) -> int:
    async with db.execute(
        "SELECT id FROM categories WHERE name = ?", (DEFAULT_CATEGORY_NAME,)
    ) as cursor:
        row = await cursor.fetchone()
    if row:
        return int(row[0])

    cursor = await db.execute(
        "INSERT INTO categories (name, icon_url) VALUES (?, ?)",
        (DEFAULT_CATEGORY_NAME, None),
    )
    return int(cursor.lastrowid)


async def _migrate_from_bot_db_if_needed(db: aiosqlite.Connection) -> None:
    """Non-destructively imports categories, products, and stocks from legacy bot.db if present."""
    bot_db_path = BASE_DIR / "bot.db"
    if not bot_db_path.exists():
        return

    # Check if target already has products
    async with db.execute("SELECT COUNT(*) FROM products") as cur:
        count = (await cur.fetchone())[0]
        if count > 0:
            return  # Already has products, no migration needed

    try:
        legacy = sqlite3.connect(str(bot_db_path))
        legacy.row_factory = sqlite3.Row
        cur = legacy.cursor()

        # Check tables in bot.db
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        cat_id_map: Dict[int, int] = {}
        if "categories" in tables:
            cur.execute("SELECT id, name, icon_url FROM categories")
            for c in cur.fetchall():
                try:
                    insert_cur = await db.execute(
                        "INSERT INTO categories (name, icon_url) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET icon_url=excluded.icon_url",
                        (c["name"], c["icon_url"]),
                    )
                    cat_id_map[c["id"]] = insert_cur.lastrowid
                except Exception:
                    pass

        if "products" in tables:
            cur.execute("SELECT code, category_id, name, price, icon_url, description FROM products")
            for p in cur.fetchall():
                target_cat_id = cat_id_map.get(p["category_id"])
                if not target_cat_id and p["category_id"]:
                    target_cat_id = p["category_id"]
                if not target_cat_id:
                    target_cat_id = await _ensure_default_category(db)

                await db.execute(
                    """
                    INSERT INTO products (code, category_id, name, price, description, icon_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code) DO NOTHING
                    """,
                    (p["code"], target_cat_id, p["name"], p["price"], p["description"] or "", p["icon_url"] or ""),
                )

        if "stock_items" in tables:
            cur.execute("SELECT product_code, account_data, is_sold FROM stock_items")
            for s in cur.fetchall():
                await db.execute(
                    "INSERT INTO stocks (product_code, data, is_sold) VALUES (?, ?, ?)",
                    (s["product_code"], s["account_data"], s["is_sold"] or 0),
                )

        legacy.close()
        await db.commit()
    except Exception as exc:
        print(f"Warning: Legacy migration from bot.db encountered an issue: {exc}")


async def init_db() -> None:
    """Create the current schema and non-destructively migrate legacy databases."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon_url TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                code TEXT PRIMARY KEY,
                category_id INTEGER,
                name TEXT NOT NULL,
                price INTEGER NOT NULL CHECK(price >= 0),
                description TEXT,
                icon_url TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                data TEXT NOT NULL,
                is_sold INTEGER NOT NULL DEFAULT 0 CHECK(is_sold IN (0, 1)),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_code) REFERENCES products(code)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                reference TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_code TEXT NOT NULL,
                amount INTEGER NOT NULL CHECK(amount >= 0),
                status TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK(status IN ('PENDING', 'PAID', 'EXPIRED', 'IGNORED', 'FAILED')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_code) REFERENCES products(code)
            )
            """
        )

        product_columns = await _column_names(db, "products")
        for column, definition in {
            "category_id": "INTEGER",
            "description": "TEXT",
            "icon_url": "TEXT",
        }.items():
            if column not in product_columns:
                await db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")

        stock_columns = await _column_names(db, "stocks")
        if "created_at" not in stock_columns:
            await db.execute("ALTER TABLE stocks ADD COLUMN created_at TIMESTAMP")

        default_category_id = await _ensure_default_category(db)
        await db.execute(
            "UPDATE products SET category_id = ? WHERE category_id IS NULL",
            (default_category_id,),
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_stocks_product_sold ON stocks(product_code, is_sold)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC)"
        )
        await db.commit()

        # Check and migrate legacy bot.db data if appropriate
        await _migrate_from_bot_db_if_needed(db)


# =====================================================================
# DASHBOARD STATS & UNIFIED DATA
# =====================================================================

async def get_dashboard_data() -> dict:
    """Returns a unified dashboard dictionary that fulfills both React and Jinja2 views."""
    await init_db()
    async with aiosqlite.connect(DB_NAME) as conn:
        conn.row_factory = aiosqlite.Row

        # 1. Total revenue
        async with conn.execute("SELECT COALESCE(SUM(amount), 0) AS val FROM transactions WHERE status = 'PAID'") as cur:
            revenue = int((await cur.fetchone())["val"])

        # 2. Total paid transactions
        async with conn.execute("SELECT COUNT(*) AS val FROM transactions WHERE status = 'PAID'") as cur:
            paid_count = int((await cur.fetchone())["val"])

        # 3. Total ready stock
        async with conn.execute("SELECT COUNT(*) AS val FROM stocks WHERE is_sold = 0") as cur:
            available_stock = int((await cur.fetchone())["val"])

        # 4. Categories list with counts
        async with conn.execute("""
            SELECT c.id, c.name, c.icon_url,
                   COUNT(DISTINCT p.code) AS product_count,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 0) AS available_stock
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            LEFT JOIN stocks s ON s.product_code = p.code
            GROUP BY c.id ORDER BY c.name COLLATE NOCASE
        """) as cur:
            categories = [dict(row) for row in await cur.fetchall()]

        # 5. Products list with stock counters
        async with conn.execute("""
            SELECT p.code, p.category_id, p.name, p.price, p.description, p.icon_url,
                   c.name AS category_name,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 0) AS stock_count,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 0) AS available_stock,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 1) AS sold_stock
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN stocks s ON s.product_code = p.code
            GROUP BY p.code ORDER BY p.name COLLATE NOCASE
        """) as cur:
            products = [dict(row) for row in await cur.fetchall()]

        # 6. Transactions list
        async with conn.execute("""
            SELECT t.reference, t.user_id, t.product_code, t.amount, t.status, t.created_at,
                   p.name AS product_name, p.icon_url
            FROM transactions t
            LEFT JOIN products p ON p.code = t.product_code
            ORDER BY t.created_at DESC LIMIT 100
        """) as cur:
            transactions = [dict(row) for row in await cur.fetchall()]

    return {
        "summary": {
            "revenue": revenue,
            "paid_transactions": paid_count,
            "available_stock": available_stock,
        },
        "recent_transactions": transactions[:10],
        "categories": categories,
        "products": products,
        "transactions": transactions,
    }


# =====================================================================
# CATEGORIES CRUD
# =====================================================================

async def get_categories() -> list[dict]:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, icon_url FROM categories ORDER BY name COLLATE NOCASE") as cur:
            return [dict(row) for row in await cur.fetchall()]


async def add_category(name: str, icon_url: Optional[str] = None) -> int:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "INSERT INTO categories (name, icon_url) VALUES (?, ?)",
            (name.strip(), icon_url.strip() if icon_url else None),
        )
        await db.commit()
        return int(cur.lastrowid)


async def update_category(category_id: int, name: str, icon_url: Optional[str] = None) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "UPDATE categories SET name = ?, icon_url = ? WHERE id = ?",
            (name.strip(), icon_url.strip() if icon_url else None, category_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_category(category_id: int) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        # Check products
        async with db.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (category_id,)) as cur:
            if (await cur.fetchone())[0] > 0:
                raise ValueError("Kategori masih memiliki produk, pindahkan produk terlebih dahulu")
        cur = await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()
        return cur.rowcount > 0


# =====================================================================
# PRODUCTS CRUD
# =====================================================================

async def get_all_products() -> list[tuple[str, str, int]]:
    """Legacy helper for Telegram Bot: returns list of (code, name, price)."""
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT code, name, price FROM products ORDER BY name COLLATE NOCASE"
        ) as cursor:
            return await cursor.fetchall()


async def get_products_list() -> list[dict]:
    """Returns products with stock counts and category names for admin."""
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT p.code, p.category_id, p.name, p.price, p.description, p.icon_url,
                   c.name AS category_name,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 0) AS stock_count,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 0) AS available_stock,
                   COUNT(s.id) FILTER (WHERE s.is_sold = 1) AS sold_stock
            FROM products p
            LEFT JOIN categories c ON c.id = p.category_id
            LEFT JOIN stocks s ON s.product_code = p.code
            GROUP BY p.code ORDER BY p.name COLLATE NOCASE
        """) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def get_product(code: str) -> Optional[dict]:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT code, category_id, name, price, description, icon_url FROM products WHERE code = ?",
            (code,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def add_product(
    code: str,
    name: str,
    price: int,
    category_id: Optional[int] = None,
    description: Optional[str] = None,
    icon_url: Optional[str] = None,
) -> None:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        if category_id is None:
            category_id = await _ensure_default_category(db)
        await db.execute(
            """
            INSERT INTO products (code, category_id, name, price, description, icon_url)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                category_id = excluded.category_id,
                name = excluded.name,
                price = excluded.price,
                description = COALESCE(excluded.description, products.description),
                icon_url = COALESCE(excluded.icon_url, products.icon_url)
            """,
            (code.strip(), category_id, name.strip(), price, description, icon_url),
        )
        await db.commit()


async def update_product(
    code: str,
    name: str,
    price: int,
    category_id: int,
    description: Optional[str] = None,
    icon_url: Optional[str] = None,
) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            """
            UPDATE products SET name = ?, price = ?, category_id = ?, description = ?, icon_url = ?
            WHERE code = ?
            """,
            (name.strip(), price, category_id, description, icon_url, code),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_product(code: str) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        for tbl in ("stocks", "transactions"):
            async with db.execute(f"SELECT COUNT(*) FROM {tbl} WHERE product_code = ?", (code,)) as cur:
                if (await cur.fetchone())[0] > 0:
                    raise ValueError(f"Produk tidak bisa dihapus karena masih memiliki riwayat di {tbl}")
        cur = await db.execute("DELETE FROM products WHERE code = ?", (code,))
        await db.commit()
        return cur.rowcount > 0


# =====================================================================
# STOCKS CRUD
# =====================================================================

async def get_available_stock_count(product_code: str) -> int:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM stocks WHERE product_code = ? AND is_sold = 0",
            (product_code,),
        ) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0


async def get_stocks(product_code: Optional[str] = None, sold: str = "all") -> list[dict]:
    await init_db()
    filters, params = [], []
    if product_code:
        filters.append("s.product_code = ?")
        params.append(product_code)
    if sold == "ready":
        filters.append("s.is_sold = 0")
    elif sold == "sold":
        filters.append("s.is_sold = 1")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"""
            SELECT s.id, s.product_code, s.data, s.is_sold, s.created_at, p.name AS product_name
            FROM stocks s JOIN products p ON p.code = s.product_code
            {where} ORDER BY s.created_at DESC, s.id DESC
            """,
            tuple(params),
        ) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def add_stock(product_code: str, data: str) -> int:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "INSERT INTO stocks (product_code, data, is_sold) VALUES (?, ?, 0)",
            (product_code.strip(), data.strip()),
        )
        await db.commit()
        return int(cur.lastrowid)


async def add_bulk_stocks(product_code: str, items: List[str]) -> int:
    valid_items = [item.strip() for item in items if item.strip()]
    if not valid_items:
        return 0
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.executemany(
            "INSERT INTO stocks (product_code, data, is_sold) VALUES (?, ?, 0)",
            [(product_code.strip(), it) for it in valid_items],
        )
        await db.commit()
        return len(valid_items)


async def delete_stock(stock_id: int) -> bool:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("DELETE FROM stocks WHERE id = ?", (stock_id,))
        await db.commit()
        return cur.rowcount > 0


# =====================================================================
# CSV IMPORT FUNCTIONALITY (STOCK & PRODUCTS)
# =====================================================================

def _sniff_delimiter(sample: str) -> str:
    for delim in [",", ";", "\t", "|"]:
        if delim in sample:
            return delim
    return ","


async def import_stocks_from_csv(csv_content: str, default_product_code: Optional[str] = None) -> dict:
    """
    Imports stock items from a CSV string.
    Supports columns:
      - product_code / kode_produk / code
      - data / account_data / akun / voucher / lisensi
    If single-column CSV is provided without headers, uses default_product_code.
    """
    if not csv_content.strip():
        raise ValueError("File CSV kosong")

    await init_db()

    # Normalize newlines and strip BOM
    content = csv_content.lstrip("\ufeff")
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("File CSV tidak memiliki baris data")

    delimiter = _sniff_delimiter(lines[0])
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    raw_rows = list(reader)
    if not raw_rows:
        raise ValueError("Tidak ada data yang dapat dibaca dari CSV")

    # Detect header row
    header = [h.strip().lower() for h in raw_rows[0]]
    prod_code_idx = None
    data_idx = None

    for i, col in enumerate(header):
        if col in ["product_code", "product", "kode", "kode_produk", "code", "kode_barang"]:
            prod_code_idx = i
        elif col in ["data", "account_data", "akun", "voucher", "lisensi", "stok", "item", "stock"]:
            data_idx = i

    start_idx = 1 if (prod_code_idx is not None or data_idx is not None) else 0

    # Fallback column detection if no recognizable header
    if prod_code_idx is None and data_idx is None:
        first_row_len = len(raw_rows[0])
        if first_row_len == 1:
            data_idx = 0
            start_idx = 0
        elif first_row_len >= 2:
            prod_code_idx = 0
            data_idx = 1
            start_idx = 0

    inserted_count = 0
    errors = []
    records_to_insert = []

    async with aiosqlite.connect(DB_NAME) as db:
        # Get set of all known product codes
        async with db.execute("SELECT code FROM products") as cur:
            valid_codes = {row[0] for row in await cur.fetchall()}

        for row_num, row in enumerate(raw_rows[start_idx:], start=start_idx + 1):
            if not row or not any(cell.strip() for cell in row):
                continue

            target_code = default_product_code
            target_data = ""

            if prod_code_idx is not None and prod_code_idx < len(row):
                val = row[prod_code_idx].strip()
                if val:
                    target_code = val

            if data_idx is not None and data_idx < len(row):
                target_data = row[data_idx].strip()
            elif len(row) == 1:
                target_data = row[0].strip()

            if not target_data:
                continue

            if not target_code:
                errors.append(f"Baris {row_num}: Kode produk tidak ditentukan")
                continue

            if target_code not in valid_codes:
                errors.append(f"Baris {row_num}: Kode produk '{target_code}' tidak ditemukan di katalog")
                continue

            records_to_insert.append((target_code, target_data))

        if records_to_insert:
            await db.executemany(
                "INSERT INTO stocks (product_code, data, is_sold) VALUES (?, ?, 0)",
                records_to_insert,
            )
            await db.commit()
            inserted_count = len(records_to_insert)

    return {
        "inserted": inserted_count,
        "errors": errors,
        "total_rows": len(raw_rows) - start_idx,
    }


async def import_products_from_csv(csv_content: str) -> dict:
    """
    Imports or updates products from a CSV string.
    Expected/supported columns:
      - code / kode
      - name / nama
      - price / harga
      - category / kategori / category_name
      - description / deskripsi (optional)
      - icon_url / icon / logo (optional)
    """
    if not csv_content.strip():
        raise ValueError("File CSV kosong")

    await init_db()
    content = csv_content.lstrip("\ufeff")
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("File CSV tidak memiliki baris data")

    delimiter = _sniff_delimiter(lines[0])
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = list(reader)
    if len(rows) < 2:
        raise ValueError("File CSV harus memiliki minimal header dan 1 baris data")

    header = [h.strip().lower() for h in rows[0]]

    # Map header fields
    col_map = {}
    for i, col in enumerate(header):
        if col in ["code", "kode", "product_code"]:
            col_map["code"] = i
        elif col in ["name", "nama", "product_name", "nama_produk"]:
            col_map["name"] = i
        elif col in ["price", "harga", "biaya"]:
            col_map["price"] = i
        elif col in ["category", "kategori", "category_name"]:
            col_map["category"] = i
        elif col in ["description", "deskripsi", "desc", "keterangan"]:
            col_map["description"] = i
        elif col in ["icon_url", "icon", "logo", "image_url", "gambar"]:
            col_map["icon_url"] = i

    if "code" not in col_map or "name" not in col_map or "price" not in col_map:
        raise ValueError("Kolom wajib 'code', 'name', dan 'price' harus ada dalam header CSV")

    inserted_count = 0
    updated_count = 0
    errors = []

    async with aiosqlite.connect(DB_NAME) as db:
        # Load category lookup
        cat_map = {}
        async with db.execute("SELECT id, name FROM categories") as cur:
            for row in await cur.fetchall():
                cat_map[row[1].lower()] = row[0]

        default_cat_id = await _ensure_default_category(db)

        for row_num, row in enumerate(rows[1:], start=2):
            if not row or not any(cell.strip() for cell in row):
                continue

            try:
                code = row[col_map["code"]].strip()
                name = row[col_map["name"]].strip()
                price_str = row[col_map["price"]].strip().replace(".", "").replace(",", "").replace("Rp", "").strip()
                price = int(price_str)
            except Exception as e:
                errors.append(f"Baris {row_num}: Format salah ({e})")
                continue

            if not code or not name:
                errors.append(f"Baris {row_num}: Kode dan nama tidak boleh kosong")
                continue

            # Category resolution
            category_id = default_cat_id
            if "category" in col_map and col_map["category"] < len(row):
                cat_name = row[col_map["category"]].strip()
                if cat_name:
                    cat_key = cat_name.lower()
                    if cat_key in cat_map:
                        category_id = cat_map[cat_key]
                    else:
                        # Create new category automatically
                        ins = await db.execute(
                            "INSERT INTO categories (name, icon_url) VALUES (?, ?)",
                            (cat_name, f"https://cdn.simpleicons.org/{code}"),
                        )
                        category_id = ins.lastrowid
                        cat_map[cat_key] = category_id

            desc = row[col_map["description"]].strip() if "description" in col_map and col_map["description"] < len(row) else None
            icon = row[col_map["icon_url"]].strip() if "icon_url" in col_map and col_map["icon_url"] < len(row) else None
            if not icon:
                icon = f"https://cdn.simpleicons.org/{code}"

            # Check if exists
            async with db.execute("SELECT 1 FROM products WHERE code = ?", (code,)) as cur:
                exists = await cur.fetchone() is not None

            await db.execute(
                """
                INSERT INTO products (code, category_id, name, price, description, icon_url)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    category_id = excluded.category_id,
                    name = excluded.name,
                    price = excluded.price,
                    description = COALESCE(excluded.description, products.description),
                    icon_url = COALESCE(excluded.icon_url, products.icon_url)
                """,
                (code, category_id, name, price, desc, icon),
            )

            if exists:
                updated_count += 1
            else:
                inserted_count += 1

        await db.commit()

    return {
        "inserted": inserted_count,
        "updated": updated_count,
        "errors": errors,
        "total": inserted_count + updated_count,
    }


# =====================================================================
# TRANSACTIONS & CHECKOUT
# =====================================================================

async def create_transaction(reference: str, user_id: int, product_code: str, amount: int) -> dict:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO transactions (reference, user_id, product_code, amount, status)
            VALUES (?, ?, ?, ?, 'PENDING')
            """,
            (reference, user_id, product_code, amount),
        )
        await db.commit()
    return {
        "reference": reference,
        "user_id": user_id,
        "product_code": product_code,
        "amount": amount,
        "status": "PENDING",
    }


async def get_transaction(reference: str) -> Optional[dict]:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT t.reference, t.user_id, t.product_code, t.amount, t.status, t.created_at,
                   p.name AS product_name, p.icon_url, p.description
            FROM transactions t
            LEFT JOIN products p ON p.code = t.product_code
            WHERE t.reference = ?
            """,
            (reference,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def complete_payment(reference: str, amount: Optional[int] = None) -> dict:
    """
    Marks a transaction as PAID, deducts 1 ready stock item, and returns the delivered stock data.
    """
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row

        # Fetch transaction
        async with db.execute(
            "SELECT reference, user_id, product_code, amount, status FROM transactions WHERE reference = ?",
            (reference,),
        ) as cur:
            trx = await cur.fetchone()

        if not trx:
            return {"status": "error", "reason": "Transaksi tidak ditemukan"}

        if trx["status"] == "PAID":
            # Already paid, find associated stock or message
            return {"status": "already_paid", "reference": reference}

        actual_amount = amount if amount is not None else trx["amount"]
        product_code = trx["product_code"]

        # Find 1 available stock item
        async with db.execute(
            "SELECT id, data FROM stocks WHERE product_code = ? AND is_sold = 0 ORDER BY id ASC LIMIT 1",
            (product_code,),
        ) as cur:
            stock_row = await cur.fetchone()

        stock_data = stock_row["data"] if stock_row else "Maaf, stok habis saat pembayaran. Hubungi admin untuk klaim."

        # Mark stock sold if found
        if stock_row:
            await db.execute("UPDATE stocks SET is_sold = 1 WHERE id = ?", (stock_row["id"],))

        # Update transaction status
        await db.execute(
            "UPDATE transactions SET status = 'PAID', amount = ? WHERE reference = ?",
            (actual_amount, reference),
        )
        await db.commit()

        # Fetch product name
        async with db.execute("SELECT name FROM products WHERE code = ?", (product_code,)) as cur:
            prod_row = await cur.fetchone()
            product_name = prod_row["name"] if prod_row else product_code

        return {
            "status": "ok",
            "reference": reference,
            "user_id": trx["user_id"],
            "product_code": product_code,
            "product_name": product_name,
            "account_data": stock_data,
            "has_stock": stock_row is not None,
        }


async def fetch_all(query: str, parameters: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
    await init_db()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, parameters) as cur:
            return await cur.fetchall()
