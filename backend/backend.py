"""Unified FastAPI backend for Digital Mart and Telegram Bot integration."""

from __future__ import annotations

import os
import sys
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

# Ensure backend directory is in sys.path regardless of execution working directory
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Ensure Windows terminal doesn't crash on utf-8 characters
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

import database as db
from admin_web import router as admin_router

if (CURRENT_DIR / ".env").exists():
    load_dotenv(dotenv_path=CURRENT_DIR / ".env")
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and migrate if needed
    await db.init_db()
    yield


app = FastAPI(
    title="Digital Mart API",
    description="Backend API & Admin Panel untuk Digital Mart Telegram Bot",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Admin Router
app.include_router(admin_router)


# =====================================================================
# HELPER: TELEGRAM BOT NOTIFICATION & VOUCHER DELIVERY
# =====================================================================

async def send_telegram_voucher(user_id: int, product_name: str, account_data: str, reference: str):
    """Sends the purchased digital item directly to the customer's Telegram chat."""
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    if not token or token == "your_telegram_bot_token_here" or token.startswith("your_"):
        print(f"[Telegram Demo Mode] User #{user_id} bought {product_name}. Item: {account_data}")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    text = (
        f"🎉 <b>PEMBAYARAN BERHASIL!</b>\n\n"
        f"Terima kasih telah berbelanja di <b>Digital Mart</b>.\n\n"
        f"📋 <b>Detail Pesanan:</b>\n"
        f"• Ref Transaksi: <code>{reference}</code>\n"
        f"• Produk: <b>{product_name}</b>\n\n"
        f"🔑 <b>Data Akun / Voucher:</b>\n"
        f"<code>{account_data}</code>\n\n"
        f"<i>Simpan data ini dengan aman. Jika ada kendala, hubungi admin!</i>"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
            if res.status_code != 200:
                print(f"[Telegram API Warning] Status {res.status_code}: {res.text}")
    except Exception as exc:
        print(f"[Telegram Delivery Error] Gagal mengirim voucher ke Telegram: {exc}")


# =====================================================================
# ROOT & CHECKOUT APIS (USED BY BOT & BUYERS)
# =====================================================================

@app.get("/")
def root():
    return RedirectResponse(url="/admin")


class CheckoutRequest(BaseModel):
    user_id: int
    product_code: str


@app.post("/api/checkout")
async def checkout(
    request: Request,
    user_id: Optional[int] = Query(None),
    product_code: Optional[str] = Query(None),
):
    """
    Called by Telegram Bot when user clicks 'Beli {name}'.
    Supports query parameters or JSON body.
    """
    uid = user_id
    pcode = product_code

    if uid is None or pcode is None:
        try:
            body = await request.json()
            uid = body.get("user_id")
            pcode = body.get("product_code")
        except Exception:
            pass

    if not uid or not pcode:
        raise HTTPException(status_code=400, detail="user_id dan product_code wajib diisi")

    # Verify product exists
    product = await db.get_product(pcode)
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan di katalog")

    # Verify stock available
    stock_count = await db.get_available_stock_count(pcode)
    if stock_count <= 0:
        raise HTTPException(status_code=400, detail=f"Maaf, stok untuk '{product['name']}' sedang habis")

    # Generate unique reference
    reference = f"INV-{secrets.token_hex(4).upper()}"

    # Create transaction
    await db.create_transaction(
        reference=reference,
        user_id=uid,
        product_code=pcode,
        amount=product["price"],
    )

    payment_url = f"{BACKEND_URL}/pay/{reference}"

    return {
        "status": "ok",
        "reference": reference,
        "amount": product["price"],
        "product_name": product["name"],
        "payment_url": payment_url,
    }


# =====================================================================
# PAYMENT SIMULATION PAGE & DEMO PAY (PERFECT FOR PRESENTATIONS)
# =====================================================================

@app.get("/pay/{reference}", response_class=HTMLResponse)
async def payment_page(reference: str):
    """Interactive checkout & payment simulation page for presentations and real users."""
    trx = await db.get_transaction(reference)
    if not trx:
        return HTMLResponse(
            "<h1>Transaksi Tidak Ditemukan</h1><p>Pastikan kode referensi benar.</p>",
            status_code=404,
        )

    is_paid = trx["status"] == "PAID"
    amount_str = f"Rp {trx['amount']:,}".replace(",", ".")

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pembayaran — {trx['reference']}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0d1117] text-slate-100 min-h-screen flex items-center justify-center p-4 font-sans">
  <div class="max-w-md w-full bg-[#161b22] border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
    <div class="text-center space-y-1">
      <div class="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600/20 text-indigo-400 mb-2 font-bold text-xl">
        🛒
      </div>
      <h1 class="text-xl font-bold text-white">Digital Mart Checkout</h1>
      <p class="text-xs text-slate-400">Selesaikan pembayaran untuk pesanan Anda</p>
    </div>

    <div class="bg-[#0d1117] border border-slate-800 rounded-xl p-4 space-y-3">
      <div class="flex justify-between items-center text-xs">
        <span class="text-slate-400">Kode Referensi:</span>
        <span class="font-mono font-bold text-indigo-400">{trx['reference']}</span>
      </div>
      <div class="flex justify-between items-center text-xs">
        <span class="text-slate-400">Produk:</span>
        <span class="font-semibold text-slate-200">{trx['product_name']}</span>
      </div>
      <div class="flex justify-between items-center text-xs">
        <span class="text-slate-400">User ID Telegram:</span>
        <span class="font-mono text-slate-300">#{trx['user_id']}</span>
      </div>
      <div class="border-t border-slate-800 pt-3 flex justify-between items-center">
        <span class="text-xs text-slate-400 font-semibold">Total Tagihan:</span>
        <span class="text-xl font-extrabold text-emerald-400">{amount_str}</span>
      </div>
    </div>

    <!-- Status Section -->
    <div id="status-card" class="text-center p-3 rounded-lg border {'bg-emerald-950/40 border-emerald-800 text-emerald-400' if is_paid else 'bg-amber-950/40 border-amber-800 text-amber-400'} text-xs font-semibold">
      Status: <span id="status-text">{'LUNAS (PAID)' if is_paid else 'MENUNGGU PEMBAYARAN'}</span>
    </div>

    <!-- QRIS Simulation Card -->
    <div class="text-center space-y-2">
      <p class="text-xs text-slate-400 font-medium">Scan QRIS Demo di bawah ini:</p>
      <div class="inline-block p-3 bg-white rounded-xl shadow-md">
        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={trx['reference']}" alt="QRIS" class="w-40 h-40">
      </div>
      <p class="text-[11px] text-slate-500">Mendukung GoPay, OVO, Dana, ShopeePay, BCA, Mandiri</p>
    </div>

    <!-- Action Buttons -->
    <div class="space-y-3 pt-2">
      <button id="pay-btn" onclick="executePayment()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition duration-200 shadow-lg shadow-emerald-600/30 text-sm flex items-center justify-center gap-2" {'disabled style="opacity: 0.5; cursor: not-allowed;"' if is_paid else ''}>
        ⚡ Simulasi Bayar Sekarang (1-Click Demo)
      </button>
      <p id="msg-box" class="text-xs text-center font-medium hidden"></p>
    </div>
  </div>

  <script>
    async function executePayment() {{
      const btn = document.getElementById('pay-btn');
      const msgBox = document.getElementById('msg-box');
      const statusText = document.getElementById('status-text');
      const statusCard = document.getElementById('status-card');

      btn.disabled = true;
      btn.innerText = 'Memproses pembayaran...';

      try {{
        const res = await fetch('/api/pay/{trx['reference']}', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }}
        }});
        const data = await res.json();

        if (res.ok) {{
          btn.innerText = '✅ Pembayaran Berhasil';
          statusCard.className = 'text-center p-3 rounded-lg border bg-emerald-950/40 border-emerald-800 text-emerald-400 text-xs font-semibold';
          statusText.innerText = 'LUNAS (PAID)';

          msgBox.className = 'text-xs text-center font-semibold text-emerald-400 block';
          msgBox.innerHTML = '🎉 Berhasil dibayar!<br>Data akun / voucher telah dikirim ke Telegram kamu.';
        }} else {{
          btn.disabled = false;
          btn.innerText = 'Coba Lagi';
          msgBox.className = 'text-xs text-center font-semibold text-rose-400 block';
          msgBox.innerText = data.detail || data.reason || 'Gagal memproses pembayaran';
        }}
      }} catch (err) {{
        btn.disabled = false;
        btn.innerText = 'Coba Lagi';
        msgBox.className = 'text-xs text-center font-semibold text-rose-400 block';
        msgBox.innerText = 'Terjadi kesalahan jaringan: ' + err.message;
      }}
    }}
  </script>
</body>
</html>
"""
    return HTMLResponse(html_content)


@app.post("/api/pay/{reference}")
async def demo_pay(reference: str):
    """Executes payment completion and notifies the Telegram user."""
    res = await db.complete_payment(reference)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("reason", "Pembayaran gagal"))

    if res.get("status") in ["ok", "already_paid"]:
        # Deliver to Telegram
        if res.get("status") == "ok":
            await send_telegram_voucher(
                user_id=res["user_id"],
                product_name=res["product_name"],
                account_data=res["account_data"],
                reference=reference,
            )
        return {
            "status": "ok",
            "message": "Pembayaran berhasil dan voucher telah dikirim!",
            "data": res,
        }

    return {"status": "ok"}


# =====================================================================
# WEBHOOK SAWERIA (FOR REAL INTEGRATION)
# =====================================================================

@app.post("/api/webhook/saweria")
async def saweria_webhook(request: Request):
    """Handles Saweria donation webhook for automated digital product checkout."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "detail": "Invalid JSON body"}, status_code=400)

    # Saweria sends invoice reference in 'msg' field
    invoice_ref = data.get("msg") or data.get("reference") or data.get("invoice_ref") or ""
    invoice_ref = str(invoice_ref).strip()
    amount = data.get("amount", 0)

    if not invoice_ref:
        return {"status": "ignored", "reason": "Pesan kosong / tanpa referensi invoice"}

    res = await db.complete_payment(invoice_ref, amount=int(amount) if amount else None)
    if res.get("status") == "ok":
        await send_telegram_voucher(
            user_id=res["user_id"],
            product_name=res["product_name"],
            account_data=res["account_data"],
            reference=invoice_ref,
        )
        return {"status": "ok", "delivered": True}
    elif res.get("status") == "already_paid":
        return {"status": "ok", "delivered": False, "note": "Sudah dibayar sebelumnya"}
    else:
        return {"status": "ignored", "reason": res.get("reason", "Invoice tidak ditemukan")}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print("\n" + "=" * 60)
    print(">> DIGITAL MART BACKEND RUNNING")
    print(f"-> Admin Panel: http://127.0.0.1:{port}/admin")
    print(f"-> API Docs:    http://127.0.0.1:{port}/docs")
    print("=" * 60 + "\n")
    uvicorn.run("backend:app", host="127.0.0.1", port=port, reload=True)