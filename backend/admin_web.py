"""Admin HTML view and JSON API for the digital-store backend."""

from __future__ import annotations

import os
import sys
import secrets
from pathlib import Path
from typing import Literal, Optional, List, Union

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from fastapi import APIRouter, Depends, HTTPException, Response, Request, UploadFile, File, Form, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import database as db

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    valid = secrets.compare_digest(credentials.username, username) and secrets.compare_digest(
        credentials.password, password
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon_url: Optional[str] = ""


class ProductIn(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    category_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=160)
    price: int = Field(ge=0)
    description: Optional[str] = ""
    icon_url: Optional[str] = ""


class BulkStockIn(BaseModel):
    product_code: str = Field(min_length=2, max_length=80)
    items: Optional[List[str]] = None
    data: Optional[str] = None


# =====================================================================
# HTML DASHBOARD VIEW
# =====================================================================

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _: str = Depends(require_admin)) -> HTMLResponse:
    await db.init_db()
    data = await db.get_dashboard_data()

    stats = {
        "total_income": data["summary"]["revenue"],
        "total_sales": data["summary"]["paid_transactions"],
        "total_stock": data["summary"]["available_stock"],
        "recent_transactions": data["recent_transactions"],
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "stats": stats,
            "categories": data["categories"],
            "products": data["products"],
        },
    )


# =====================================================================
# UNIFIED JSON DASHBOARD API
# =====================================================================

@router.get("/api/dashboard")
async def dashboard_data(_: str = Depends(require_admin)) -> dict:
    """Returns data compatible with both React Frontend and Jinja2 Dashboard."""
    return await db.get_dashboard_data()


# =====================================================================
# CATEGORIES API
# =====================================================================

@router.get("/api/categories")
async def list_categories(_: str = Depends(require_admin)) -> list[dict]:
    return await db.get_categories()


@router.post("/api/categories", status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryIn, _: str = Depends(require_admin)) -> dict:
    try:
        cat_id = await db.add_category(payload.name, payload.icon_url)
        return {"status": "ok", "id": cat_id, "message": "Kategori ditambahkan"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/api/categories/{category_id}")
async def update_category(category_id: int, payload: CategoryIn, _: str = Depends(require_admin)) -> dict:
    try:
        success = await db.update_category(category_id, payload.name, payload.icon_url)
        if not success:
            raise HTTPException(404, "Kategori tidak ditemukan")
        return {"status": "ok", "message": "Kategori diperbarui"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/api/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, _: str = Depends(require_admin)) -> Response:
    try:
        success = await db.delete_category(category_id)
        if not success:
            raise HTTPException(404, "Kategori tidak ditemukan")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))


# =====================================================================
# PRODUCTS API
# =====================================================================

@router.get("/api/products")
async def list_products(_: str = Depends(require_admin)) -> list[dict]:
    return await db.get_products_list()


@router.post("/api/products", status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductIn, _: str = Depends(require_admin)) -> dict:
    try:
        # Check if already exists
        existing = await db.get_product(payload.code)
        if existing:
            raise HTTPException(status_code=400, detail=f"Kode produk '{payload.code}' sudah digunakan")

        await db.add_product(
            code=payload.code,
            name=payload.name,
            price=payload.price,
            category_id=payload.category_id,
            description=payload.description,
            icon_url=payload.icon_url,
        )
        return {"status": "ok", "message": "Produk ditambahkan"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/api/products/{code}")
async def update_product(code: str, payload: ProductIn, _: str = Depends(require_admin)) -> dict:
    try:
        cat_id = payload.category_id or 1
        success = await db.update_product(
            code=code,
            name=payload.name,
            price=payload.price,
            category_id=cat_id,
            description=payload.description,
            icon_url=payload.icon_url,
        )
        if not success:
            raise HTTPException(404, "Produk tidak ditemukan")
        return {"status": "ok", "message": "Produk diperbarui"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/api/products/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(code: str, _: str = Depends(require_admin)) -> Response:
    try:
        success = await db.delete_product(code)
        if not success:
            raise HTTPException(404, "Produk tidak ditemukan")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))


# =====================================================================
# STOCKS API
# =====================================================================

@router.get("/api/stocks")
async def list_stocks(
    product_code: Optional[str] = None,
    sold: Literal["all", "ready", "sold"] = "all",
    _: str = Depends(require_admin),
) -> list[dict]:
    return await db.get_stocks(product_code=product_code, sold=sold)


@router.post("/api/stocks/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_insert_stock(payload: BulkStockIn, _: str = Depends(require_admin)) -> dict:
    product = await db.get_product(payload.product_code)
    if not product:
        raise HTTPException(404, f"Produk dengan kode '{payload.product_code}' tidak ditemukan")

    items = []
    if payload.items:
        items = [line.strip() for line in payload.items if line.strip()]
    elif payload.data:
        items = [line.strip() for line in payload.data.splitlines() if line.strip()]

    if not items:
        raise HTTPException(422, "Masukkan setidaknya satu baris stok")

    count = await db.add_bulk_stocks(payload.product_code, items)
    return {"status": "ok", "message": f"{count} stok berhasil diimpor", "count": count, "inserted": count}


@router.delete("/api/stocks/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock_item(stock_id: int, _: str = Depends(require_admin)) -> Response:
    success = await db.delete_stock(stock_id)
    if not success:
        raise HTTPException(404, "Stok tidak ditemukan")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =====================================================================
# CSV UPLOAD ENDPOINTS (STOCK & PRODUCTS)
# =====================================================================

@router.post("/api/stocks/upload-csv", status_code=status.HTTP_201_CREATED)
async def upload_stock_csv(
    file: Optional[UploadFile] = File(None),
    product_code: Optional[str] = Form(None),
    raw_csv: Optional[str] = Form(None),
    _: str = Depends(require_admin),
) -> dict:
    """
    Accepts CSV upload for stock accounts/vouchers.
    Can be uploaded via multipart file or passed as raw text.
    """
    csv_text = ""
    if file:
        content_bytes = await file.read()
        try:
            csv_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            csv_text = content_bytes.decode("latin-1")
    elif raw_csv:
        csv_text = raw_csv

    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="File CSV tidak ditemukan atau kosong")

    try:
        result = await db.import_stocks_from_csv(csv_text, default_product_code=product_code)
        return {
            "status": "ok",
            "message": f"Berhasil mengimpor {result['inserted']} unit stok!",
            "inserted": result["inserted"],
            "errors": result["errors"],
            "total_rows": result["total_rows"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/products/upload-csv", status_code=status.HTTP_201_CREATED)
async def upload_product_csv(
    file: Optional[UploadFile] = File(None),
    raw_csv: Optional[str] = Form(None),
    _: str = Depends(require_admin),
) -> dict:
    """
    Accepts CSV upload for products catalog.
    Can be uploaded via multipart file or passed as raw text.
    """
    csv_text = ""
    if file:
        content_bytes = await file.read()
        try:
            csv_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            csv_text = content_bytes.decode("latin-1")
    elif raw_csv:
        csv_text = raw_csv

    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="File CSV tidak ditemukan atau kosong")

    try:
        result = await db.import_products_from_csv(csv_text)
        return {
            "status": "ok",
            "message": f"Berhasil memproses {result['total']} produk ({result['inserted']} baru, {result['updated']} diperbarui)!",
            "inserted": result["inserted"],
            "updated": result["updated"],
            "errors": result["errors"],
            "total": result["total"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# =====================================================================
# CSV TEMPLATE DOWNLOAD ENDPOINTS
# =====================================================================

@router.get("/api/templates/stock-csv")
async def download_stock_csv_template(_: str = Depends(require_admin)):
    content = (
        "product_code,data\n"
        "steam-50k,STEAM-KEY-AAAA-BBBB-CCCC\n"
        "steam-50k,STEAM-KEY-DDDD-EEEE-FFFF\n"
        "spotify-1m,user1@email.com:password123\n"
    )
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=template_stok.csv"},
    )


@router.get("/api/templates/product-csv")
async def download_product_csv_template(_: str = Depends(require_admin)):
    content = (
        "code,name,price,category,description,icon_url\n"
        "steam-50k,Steam Wallet IDR 50.000,50000,Gaming,Voucher Steam Wallet 50.000,https://cdn.simpleicons.org/steam\n"
        "steam-100k,Steam Wallet IDR 100.000,100000,Gaming,Voucher Steam Wallet 100.000,https://cdn.simpleicons.org/steam\n"
        "spotify-1m,Spotify Premium 1 Bulan,35000,Streaming,Akun Spotify Premium 1 Bulan,https://cdn.simpleicons.org/spotify\n"
        "netflix-1m,Netflix Premium 1 Bulan,45000,Streaming,Akun Netflix UHD 1 Bulan,https://cdn.simpleicons.org/netflix\n"
    )
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=template_produk.csv"},
    )


# =====================================================================
# TRANSACTIONS API
# =====================================================================

@router.get("/api/transactions")
async def list_transactions(_: str = Depends(require_admin)) -> list[dict]:
    data = await db.get_dashboard_data()
    return data["transactions"]
