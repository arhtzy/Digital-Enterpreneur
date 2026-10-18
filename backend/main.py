import os
import sys
from pathlib import Path
import asyncio
import logging

# Ensure backend directory is in sys.path
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
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

import database as db

if (CURRENT_DIR / ".env").exists():
    load_dotenv(dotenv_path=CURRENT_DIR / ".env")
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "7661609988"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("telegram_bot")

dp = Dispatcher()

# --- MENU UTAMA ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Lihat Katalog & Stok", callback_data="show_catalog")],
        [InlineKeyboardButton(text="💬 Hubungi Admin", url="https://t.me/username_admin_kamu")]
    ])
    await message.answer(
        f"Halo <b>{message.from_user.first_name}</b>! Selamat datang di Toko Digital Bot.\n\n"
        "Silakan pilih menu di bawah untuk melihat katalog dan transaksi otomatis 24/7:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# --- MENAMPILKAN KATALOG ---
@dp.callback_query(F.data == "show_catalog")
async def process_catalog(callback: types.CallbackQuery):
    products = await db.get_all_products()
    if not products:
        await callback.message.answer("Belum ada produk yang tersedia saat ini.")
        await callback.answer()
        return

    text = "🛒 <b>=== KATALOG PRODUK DIGITAL ===</b>\n\n"
    buttons = []

    for code, name, price in products:
        stock = await db.get_available_stock_count(code)
        stock_text = f"✅ {stock} unit" if stock > 0 else "❌ Habis"
        text += f"📦 <b>{name}</b>\n• Harga: <b>Rp{price:,}</b>\n• Stok: {stock_text}\n\n"
        if stock > 0:
            buttons.append([InlineKeyboardButton(text=f"Beli {name}", callback_data=f"buy_{code}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# --- PROSES CHECKOUT (PANGGIL BACKEND) ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    product_code = callback.data.split("_")[1]
    user_id = callback.from_user.id

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            res = await client.post(
                f"{BACKEND_URL}/api/checkout",
                params={"user_id": user_id, "product_code": product_code}
            )
            data = res.json()

            if res.status_code == 200:
                payment_url = data["payment_url"]
                ref = data["reference"]
                amount = data["amount"]
                prod_name = data.get("product_name", product_code)

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Bayar Sekarang", url=payment_url)]
                ])

                await callback.message.answer(
                    f"💳 <b>INSTRUKSI PEMBAYARAN</b>\n\n"
                    f"• Produk: <b>{prod_name}</b>\n"
                    f"• Ref Transaksi: <code>{ref}</code>\n"
                    f"• Total Bayar: <b>Rp{amount:,}</b>\n\n"
                    f"Silakan klik tombol di bawah untuk menyelesaikan pembayaran. Produk akan dikirim otomatis ke chat ini setelah pembayaran berhasil!",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            else:
                detail = data.get("detail", "Gagal memproses transaksi")
                await callback.message.answer(f"❌ {detail}")

        except Exception as e:
            logger.error(f"Error checkout: {e}")
            await callback.message.answer("❌ Terjadi kesalahan saat menghubungi server pembayaran.")

    await callback.answer()

# --- COMMAND ADMIN (ADD PRODUCT) ---
@dp.message(Command("addprod"))
async def cmd_add_product(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Akses ditolak. Anda bukan admin.")
        return
    try:
        args = message.text.split()[1:]
        if len(args) < 3:
            raise ValueError

        code = args[0]
        price = int(args[-1])
        name = " ".join(args[1:-1])

        await db.add_product(code, name, price)
        await message.answer(f"✅ Produk <b>{name}</b> (<code>{code}</code>) seharga Rp{price:,} berhasil ditambahkan!", parse_mode="HTML")
    except Exception:
        await message.answer("Format salah! Gunakan: `/addprod [kode] [nama produk] [harga]`")

@dp.message(Command("addstock"))
async def cmd_add_stock(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Akses ditolak. Anda bukan admin.")
        return
    try:
        _, code, data = message.text.split(" ", 2)
        await db.add_stock(code, data)
        await message.answer(f"✅ Stok baru untuk <code>{code}</code> berhasil dimasukkan!", parse_mode="HTML")
    except Exception:
        await message.answer("Format salah! Gunakan: `/addstock [kode] [data_akun_atau_lisensi]`")

# --- MAIN RUNNER ---
async def main():
    await db.init_db()
    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here" or BOT_TOKEN.startswith("your_"):
        logger.warning("⚠️ BOT_TOKEN belum dikonfigurasi di backend/.env! Bot Telegram tidak dapat dijalankan tanpa token valid.")
        print("\n============================================================")
        print("PERINGATAN: BOT_TOKEN belum diisi di backend/.env!")
        print("Silakan dapatkan token dari @BotFather di Telegram dan")
        print("masukkan ke dalam backend/.env (BOT_TOKEN=...)")
        print("============================================================\n")
        return

    bot = Bot(token=BOT_TOKEN)
    logger.info("🤖 Bot Telegram berhasil dinyalakan...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())