import React, { useState, useEffect } from 'react';
import {
  Plus,
  Upload,
  FileSpreadsheet,
  Download,
  CheckCircle2,
  Clock,
  XCircle,
  ShoppingBag,
  Trash2,
  ExternalLink,
  Layers,
  RefreshCw,
  Box,
  AlertCircle
} from 'lucide-react';
import {
  getDashboardData,
  createCategory,
  deleteCategory,
  createProduct,
  deleteProduct,
  bulkAddStock,
  uploadStockCsv,
  uploadProductCsv,
  getStockCsvTemplateUrl,
  getProductCsvTemplateUrl,
  API_BASE_URL
} from './services/api';

export default function App() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeModal, setActiveModal] = useState(null); // 'product' | 'category' | 'stock' | 'csv'

  // Filter States
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [csvTab, setCsvTab] = useState('stock'); // 'stock' | 'product'

  // CSV Upload States
  const [csvFile, setCsvFile] = useState(null);
  const [csvProductCode, setCsvProductCode] = useState('');
  const [csvPreview, setCsvPreview] = useState([]);
  const [csvUploading, setCsvUploading] = useState(false);

  // Form States
  const [catForm, setCatForm] = useState({ name: '', icon_url: '' });
  const [prodForm, setProdForm] = useState({
    code: '',
    category_id: '',
    name: '',
    price: '',
    icon_url: '',
    description: '',
  });
  const [stockForm, setStockForm] = useState({
    product_code: '',
    items_raw: '',
    mode: 'manual', // 'manual' | 'csv'
  });

  const refreshData = async () => {
    try {
      setRefreshing(true);
      const res = await getDashboardData();
      setDashboardData(res.data);
    } catch (err) {
      console.error('Gagal mengambil data dashboard:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, []);

  // Handle Create Category
  const handleAddCategory = async (e) => {
    e.preventDefault();
    if (!catForm.name.trim()) {
      alert('Nama kategori tidak boleh kosong');
      return;
    }
    try {
      const payload = {
        name: catForm.name.trim(),
        icon_url: catForm.icon_url.trim() || 'https://cdn.simpleicons.org/steam',
      };
      await createCategory(payload);
      setCatForm({ name: '', icon_url: '' });
      setActiveModal(null);
      await refreshData();
      alert('✅ Kategori berhasil dibuat!');
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Gagal membuat kategori';
      alert('❌ ' + errMsg);
    }
  };

  // Handle Delete Category
  const handleDeleteCategory = async (id, name) => {
    if (!confirm(`Hapus kategori "${name}"?`)) return;
    try {
      await deleteCategory(id);
      await refreshData();
      alert('✅ Kategori berhasil dihapus!');
    } catch (err) {
      alert('❌ ' + (err.response?.data?.detail || 'Gagal menghapus kategori'));
    }
  };

  // Handle Create Product
  const handleAddProduct = async (e) => {
    e.preventDefault();
    if (!prodForm.code || !prodForm.name || !prodForm.price) {
      alert('Kode, Nama, dan Harga wajib diisi!');
      return;
    }
    try {
      const payload = {
        code: prodForm.code.trim().toLowerCase(),
        category_id: prodForm.category_id ? parseInt(prodForm.category_id) : null,
        name: prodForm.name.trim(),
        price: parseInt(prodForm.price),
        icon_url: prodForm.icon_url.trim() || `https://cdn.simpleicons.org/${prodForm.code}`,
        description: prodForm.description.trim(),
      };
      await createProduct(payload);
      setProdForm({
        code: '',
        category_id: '',
        name: '',
        price: '',
        icon_url: '',
        description: '',
      });
      setActiveModal(null);
      await refreshData();
      alert('✅ Produk berhasil disimpan!');
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Gagal membuat produk';
      alert('❌ ' + errMsg);
    }
  };

  // Handle Delete Product
  const handleDeleteProduct = async (code, name) => {
    if (!confirm(`Hapus produk "${name}" (${code})?`)) return;
    try {
      await deleteProduct(code);
      await refreshData();
      alert('✅ Produk berhasil dihapus!');
    } catch (err) {
      alert('❌ ' + (err.response?.data?.detail || 'Gagal menghapus produk'));
    }
  };

  // Handle Bulk Add Stock (Manual)
  const handleAddStock = async (e) => {
    e.preventDefault();
    if (!stockForm.product_code || !stockForm.items_raw.trim()) {
      alert('Kode produk dan data stok wajib diisi!');
      return;
    }
    try {
      const items = stockForm.items_raw
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0);

      await bulkAddStock({
        product_code: stockForm.product_code.trim(),
        items: items,
      });

      setStockForm({ product_code: '', items_raw: '', mode: 'manual' });
      setActiveModal(null);
      await refreshData();
      alert(`✅ Berhasil menambahkan ${items.length} stok!`);
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Gagal menambahkan stok';
      alert('❌ ' + errMsg);
    }
  };

  // Handle CSV File Selection & Preview
  const handleCsvFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.csv')) {
      alert('Harap pilih file berekstensi .csv');
      return;
    }

    setCsvFile(file);

    // Read first few lines for preview
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target.result;
      const lines = text.split('\n').filter((l) => l.trim().length > 0);
      const previewLines = lines.slice(0, 5).map((line) => line.split(','));
      setCsvPreview(previewLines);
    };
    reader.readAsText(file);
  };

  // Handle CSV Upload Submission
  const handleUploadCsvSubmit = async (e) => {
    e.preventDefault();
    if (!csvFile) {
      alert('Silakan pilih file CSV terlebih dahulu!');
      return;
    }

    try {
      setCsvUploading(true);
      const formData = new FormData();
      formData.append('file', csvFile);

      if (csvTab === 'stock') {
        if (csvProductCode) {
          formData.append('product_code', csvProductCode);
        }
        const res = await uploadStockCsv(formData);
        alert(`✅ ${res.data.message || 'Stok CSV berhasil diimpor!'}`);
      } else {
        const res = await uploadProductCsv(formData);
        alert(`✅ ${res.data.message || 'Katalog Produk CSV berhasil diproses!'}`);
      }

      setCsvFile(null);
      setCsvPreview([]);
      setCsvProductCode('');
      setActiveModal(null);
      await refreshData();
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Gagal mengupload CSV';
      alert('❌ ' + errMsg);
    } finally {
      setCsvUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center space-y-4">
        <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
        <p className="text-lg font-medium tracking-tight">Memuat Digital Mart Dashboard...</p>
      </div>
    );
  }

  const categories = dashboardData?.categories || [];
  const products = dashboardData?.products || [];
  const transactions = dashboardData?.transactions || [];

  const filteredTransactions = transactions.filter((trx) => {
    if (statusFilter === 'ALL') return true;
    return trx.status === statusFilter;
  });

  const totalRevenue = dashboardData?.summary?.revenue ?? transactions
    .filter((t) => t.status === 'PAID')
    .reduce((acc, curr) => acc + (curr.amount || 0), 0);

  const successfulTrxCount = dashboardData?.summary?.paid_transactions ?? transactions.filter((t) => t.status === 'PAID').length;
  const totalAvailableStock = dashboardData?.summary?.available_stock ?? products.reduce((acc, curr) => acc + (curr.stock_count || 0), 0);

  return (
    <div className="min-h-screen bg-[#0d1117] text-slate-100 p-4 md:p-8 font-sans selection:bg-indigo-500/30">
      {/* Header Bar */}
      <header className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8 pb-6 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-indigo-600/30">
            <ShoppingBag className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">Digital Mart</h1>
              <span className="bg-indigo-950 text-indigo-400 border border-indigo-800/50 text-[10px] font-semibold px-2 py-0.5 rounded-full">
                Live Admin
              </span>
            </div>
            <p className="text-xs text-slate-400">Panel Manajemen Katalog, Stok & Transaksi Telegram</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => refreshData()}
            title="Refresh Data"
            className="p-2.5 rounded-lg bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-slate-300 transition"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
          </button>

          <button
            onClick={() => {
              setCsvTab('stock');
              setActiveModal('csv');
            }}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-semibold px-4 py-2.5 rounded-lg transition duration-200 shadow-md shadow-indigo-600/20"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Upload CSV
          </button>

          <button
            onClick={() => setActiveModal('stock')}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2.5 rounded-lg transition duration-200 shadow-md shadow-emerald-600/20"
          >
            <Plus className="w-4 h-4" />
            Isi Stok
          </button>

          <button
            onClick={() => setActiveModal('product')}
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2.5 rounded-lg transition duration-200 shadow-md shadow-indigo-600/20"
          >
            <Plus className="w-4 h-4" />
            Tambah Produk
          </button>

          <a
            href={`${API_BASE_URL}/admin`}
            target="_blank"
            rel="noreferrer"
            title="Buka Admin Template FastAPI"
            className="hidden sm:flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium px-3 py-2.5 rounded-lg border border-slate-700 transition"
          >
            <span>FastAPI UI</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto space-y-8">
        {/* Welcome & Stats Banner */}
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between sm:items-end gap-2">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">Selamat Datang, Admin</h2>
              <p className="text-xs text-slate-400">Ringkasan operasional dan inventaris toko digital Anda.</p>
            </div>
            <div className="text-xs text-slate-400">
              Total Produk Aktif: <strong className="text-white">{products.length}</strong> | Total Kategori: <strong className="text-white">{categories.length}</strong>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-[#161b22] border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-medium text-slate-400">Total Pendapatan</p>
                  <p className="text-2xl font-extrabold text-emerald-400 mt-1">
                    Rp {totalRevenue.toLocaleString('id-ID')}
                  </p>
                </div>
                <div className="p-2.5 rounded-xl bg-emerald-950/60 border border-emerald-800/40 text-emerald-400">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-3">Akumulasi transaksi sukses (PAID)</p>
            </div>

            <div className="bg-[#161b22] border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-medium text-slate-400">Transaksi Berhasil</p>
                  <p className="text-2xl font-extrabold text-white mt-1">{successfulTrxCount}</p>
                </div>
                <div className="p-2.5 rounded-xl bg-indigo-950/60 border border-indigo-800/40 text-indigo-400">
                  <Clock className="w-5 h-5" />
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-3">Pesanan checkout selesai otomatis</p>
            </div>

            <div className="bg-[#161b22] border border-slate-800/80 rounded-2xl p-5 relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs font-medium text-slate-400">Stok Tersedia</p>
                  <p className="text-2xl font-extrabold text-white mt-1">{totalAvailableStock}</p>
                </div>
                <div className="p-2.5 rounded-xl bg-blue-950/60 border border-blue-800/40 text-blue-400">
                  <Box className="w-5 h-5" />
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-3">Unit akun/lisensi siap dikirim</p>
            </div>
          </div>
        </section>

        {/* Catalog & Inventory Table */}
        <section className="bg-[#161b22] border border-slate-800/80 rounded-2xl p-6 space-y-4">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Box className="w-4 h-4 text-indigo-400" />
                Katalog Produk & Stok
              </h3>
              <p className="text-xs text-slate-400">Pantau ketersediaan voucher dan akun digital per produk.</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setCsvTab('product');
                  setActiveModal('csv');
                }}
                className="text-xs bg-slate-800 hover:bg-slate-700 text-indigo-300 px-3 py-1.5 rounded-lg border border-slate-700 flex items-center gap-1.5 transition"
              >
                <Upload className="w-3.5 h-3.5" />
                Import Produk CSV
              </button>
              <button
                onClick={() => setActiveModal('product')}
                className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                Tambah Produk
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                  <th className="pb-3">PRODUK</th>
                  <th className="pb-3">KATEGORI</th>
                  <th className="pb-3">HARGA</th>
                  <th className="pb-3 text-center">STOK READY</th>
                  <th className="pb-3 text-right">AKSI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {products.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="py-8 text-center text-slate-500">
                      Belum ada produk di katalog. Gunakan tombol "Tambah Produk" atau "Upload CSV".
                    </td>
                  </tr>
                ) : (
                  products.map((p) => {
                    const readyCount = p.available_stock ?? p.stock_count ?? 0;
                    return (
                      <tr key={p.code} className="hover:bg-slate-800/30 transition">
                        <td className="py-3.5">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 p-1 flex items-center justify-center shrink-0">
                              <img
                                src={p.icon_url || `https://cdn.simpleicons.org/${p.code}`}
                                alt={p.name}
                                className="w-full h-full object-contain"
                                onError={(e) => {
                                  e.target.onerror = null;
                                  e.target.src = 'https://cdn.simpleicons.org/steam';
                                }}
                              />
                            </div>
                            <div>
                              <div className="font-semibold text-slate-100">{p.name}</div>
                              <div className="text-[11px] font-mono text-slate-500">{p.code}</div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3.5 text-slate-400">
                          <span className="bg-slate-800/80 px-2 py-0.5 rounded text-[11px] border border-slate-700">
                            {p.category_name || 'Uncategorized'}
                          </span>
                        </td>
                        <td className="py-3.5 font-bold text-slate-200">
                          Rp {(p.price || 0).toLocaleString('id-ID')}
                        </td>
                        <td className="py-3.5 text-center">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                              readyCount > 0
                                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
                                : 'bg-rose-950 text-rose-400 border border-rose-800/50'
                            }`}
                          >
                            {readyCount} Unit Ready
                          </span>
                        </td>
                        <td className="py-3.5 text-right space-x-2">
                          <button
                            onClick={() => {
                              setStockForm({ ...stockForm, product_code: p.code });
                              setActiveModal('stock');
                            }}
                            className="text-xs text-emerald-400 hover:text-emerald-300 font-medium hover:underline"
                          >
                            + Isi Stok
                          </button>
                          <button
                            onClick={() => handleDeleteProduct(p.code, p.name)}
                            className="text-xs text-rose-400 hover:text-rose-300 font-medium hover:underline"
                          >
                            Hapus
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Transactions & Categories Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Recent Transactions (2 cols) */}
          <div className="lg:col-span-2 bg-[#161b22] border border-slate-800/80 rounded-2xl p-6 space-y-4">
            <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Clock className="w-4 h-4 text-indigo-400" />
                  Transaksi Terbaru
                </h3>
                <p className="text-xs text-slate-400">Daftar checkout yang dipicu dari Bot Telegram.</p>
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-[#0d1117] text-slate-200 text-xs rounded-lg px-3 py-1.5 border border-slate-700 focus:outline-none focus:border-indigo-500"
              >
                <option value="ALL">Semua Status</option>
                <option value="PAID">Lunas (PAID)</option>
                <option value="PENDING">Menunggu (PENDING)</option>
                <option value="EXPIRED">Kedaluwarsa (EXPIRED)</option>
              </select>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                    <th className="pb-3">PESANAN</th>
                    <th className="pb-3">PELANGGAN</th>
                    <th className="pb-3">STATUS</th>
                    <th className="pb-3 text-right">TOTAL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {filteredTransactions.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="py-8 text-center text-slate-500">
                        Tidak ada transaksi dengan status ini.
                      </td>
                    </tr>
                  ) : (
                    filteredTransactions.map((trx) => (
                      <tr key={trx.reference} className="hover:bg-slate-800/30 transition">
                        <td className="py-3.5">
                          <div className="font-semibold text-slate-100">
                            {trx.product_name || trx.product_code}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[11px] text-slate-500 font-mono">{trx.reference}</span>
                            {trx.status === 'PENDING' && (
                              <a
                                href={`${API_BASE_URL}/pay/${trx.reference}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 hover:underline"
                                title="Buka Halaman Simulasi Pembayaran"
                              >
                                <span>Bayar Demo</span>
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 font-mono text-slate-400">Telegram #{trx.user_id}</td>
                        <td className="py-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide ${
                              trx.status === 'PAID'
                                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
                                : trx.status === 'PENDING'
                                ? 'bg-amber-950 text-amber-400 border border-amber-800/50'
                                : 'bg-rose-950 text-rose-400 border border-rose-800/50'
                            }`}
                          >
                            {trx.status}
                          </span>
                        </td>
                        <td className="py-3.5 text-right font-bold text-slate-200">
                          Rp {(trx.amount || 0).toLocaleString('id-ID')}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Categories Sidebar (1 col) */}
          <div className="bg-[#161b22] border border-slate-800/80 rounded-2xl p-6 space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-400" />
                  Kategori
                </h3>
                <p className="text-xs text-slate-400">Grup katalog produk.</p>
              </div>
              <button
                onClick={() => setActiveModal('category')}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300"
              >
                + Buat Baru
              </button>
            </div>

            <div className="space-y-2.5">
              {categories.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">Belum ada kategori.</p>
              ) : (
                categories.map((cat) => {
                  const catProductCount = products.filter((p) => p.category_id === cat.id).length;
                  return (
                    <div
                      key={cat.id || cat.name}
                      className="flex items-center justify-between p-3 rounded-xl bg-[#0d1117] border border-slate-800/80 hover:border-slate-700 transition"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center p-1.5 shrink-0">
                          <img
                            src={cat.icon_url || 'https://cdn.simpleicons.org/steam'}
                            alt={cat.name}
                            className="w-full h-full object-contain"
                            onError={(e) => {
                              e.target.onerror = null;
                              e.target.src = 'https://cdn.simpleicons.org/steam';
                            }}
                          />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-200">{cat.name}</p>
                          <p className="text-[10px] text-slate-400">{catProductCount} Produk</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {cat.name !== 'Uncategorized' && catProductCount === 0 && (
                          <button
                            onClick={() => handleDeleteCategory(cat.id, cat.name)}
                            title="Hapus Kategori"
                            className="text-slate-500 hover:text-rose-400 p-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Quick Templates Card */}
            <div className="mt-6 pt-5 border-t border-slate-800/80 space-y-2">
              <p className="text-xs font-bold text-slate-300">Format Template CSV:</p>
              <div className="flex flex-col gap-2">
                <a
                  href={getStockCsvTemplateUrl()}
                  download="template_stok.csv"
                  className="flex items-center justify-between text-[11px] text-indigo-400 hover:text-indigo-300 bg-indigo-950/40 border border-indigo-900/60 p-2.5 rounded-lg transition"
                >
                  <span className="flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5" />
                    Unduh Template CSV Stok
                  </span>
                  <span className="text-[10px] text-slate-500">.csv</span>
                </a>
                <a
                  href={getProductCsvTemplateUrl()}
                  download="template_produk.csv"
                  className="flex items-center justify-between text-[11px] text-blue-400 hover:text-blue-300 bg-blue-950/40 border border-blue-900/60 p-2.5 rounded-lg transition"
                >
                  <span className="flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5" />
                    Unduh Template CSV Produk
                  </span>
                  <span className="text-[10px] text-slate-500">.csv</span>
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ========================================================= */}
      {/* MODAL: UPLOAD CSV (STOCK & PRODUCTS)                      */}
      {/* ========================================================= */}
      {activeModal === 'csv' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#161b22] border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-5 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-white">Import Data via CSV</h3>
              </div>
              <button
                onClick={() => {
                  setActiveModal(null);
                  setCsvFile(null);
                  setCsvPreview([]);
                }}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            {/* Tab Selector */}
            <div className="flex border-b border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setCsvTab('stock');
                  setCsvFile(null);
                  setCsvPreview([]);
                }}
                className={`flex-1 pb-2.5 text-xs font-semibold text-center transition border-b-2 ${
                  csvTab === 'stock'
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                📦 Upload Stok Akun
              </button>
              <button
                type="button"
                onClick={() => {
                  setCsvTab('product');
                  setCsvFile(null);
                  setCsvPreview([]);
                }}
                className={`flex-1 pb-2.5 text-xs font-semibold text-center transition border-b-2 ${
                  csvTab === 'product'
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                🛍️ Upload Katalog Produk
              </button>
            </div>

            <form onSubmit={handleUploadCsvSubmit} className="space-y-4">
              {csvTab === 'stock' && (
                <div>
                  <label className="block text-xs text-slate-300 font-medium mb-1">
                    Produk Target (Opsional jika ada kolom di CSV)
                  </label>
                  <select
                    value={csvProductCode}
                    onChange={(e) => setCsvProductCode(e.target.value)}
                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">-- Otomatis Dari Kolom product_code di CSV --</option>
                    {products.map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.name} ({p.code})
                      </option>
                    ))}
                  </select>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Format kolom didukung: <code>product_code,data</code> atau cukup <code>data</code> jika memilih produk target di atas.
                  </p>
                </div>
              )}

              {csvTab === 'product' && (
                <p className="text-[11px] text-slate-400 bg-indigo-950/30 border border-indigo-900/50 p-2.5 rounded-lg">
                  Format header CSV yang didukung: <code>code,name,price,category,description,icon_url</code>. Kategori baru akan otomatis dibuat jika belum ada!
                </p>
              )}

              {/* File Input Dropzone */}
              <div>
                <label className="block text-xs text-slate-300 font-medium mb-1">
                  Pilih Berkas CSV
                </label>
                <div className="border-2 border-dashed border-slate-700 rounded-xl p-5 text-center bg-[#0d1117]/60 hover:border-indigo-500 transition">
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    required
                    onChange={handleCsvFileChange}
                    className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer"
                  />
                  {csvFile && (
                    <p className="text-[11px] text-emerald-400 mt-2 font-medium">
                      ✓ File dipilih: {csvFile.name} ({(csvFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                </div>
              </div>

              {/* CSV Preview */}
              {csvPreview.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[11px] font-semibold text-slate-400">Pratinjau Data (5 Baris Pertama):</p>
                  <div className="bg-[#0d1117] border border-slate-800 rounded-lg p-2.5 overflow-x-auto max-h-32 text-[10px] font-mono text-slate-300">
                    {csvPreview.map((row, idx) => (
                      <div key={idx} className="border-b border-slate-800/60 pb-1 mb-1 last:border-0">
                        {row.join(' | ')}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Template Download Link */}
              <div className="flex justify-between items-center text-xs pt-1">
                <span className="text-slate-400">Belum punya formatnya?</span>
                <a
                  href={csvTab === 'stock' ? getStockCsvTemplateUrl() : getProductCsvTemplateUrl()}
                  download={csvTab === 'stock' ? 'template_stok.csv' : 'template_produk.csv'}
                  className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium hover:underline"
                >
                  <Download className="w-3.5 h-3.5" />
                  Unduh Contoh CSV
                </a>
              </div>

              <button
                type="submit"
                disabled={csvUploading}
                className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 disabled:opacity-50 text-white text-xs font-semibold py-3 rounded-xl transition duration-200 shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
              >
                {csvUploading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Mengunggah dan Memproses...</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    <span>Upload & Simpan ke Database</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL: TAMBAH KATEGORI                                    */}
      {/* ========================================================= */}
      {activeModal === 'category' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#161b22] border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">Tambah Kategori Baru</h3>
              <button
                onClick={() => setActiveModal(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleAddCategory} className="space-y-4">
              <div>
                <label className="block text-xs text-slate-300 mb-1">Nama Kategori</label>
                <input
                  type="text"
                  required
                  placeholder="Misal: Streaming, Gaming, VPN, AI Tools"
                  value={catForm.name}
                  onChange={(e) => setCatForm({ ...catForm, name: e.target.value })}
                  className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-300 mb-1">URL Ikon / Logo (Opsional)</label>
                <input
                  type="text"
                  placeholder="https://cdn.simpleicons.org/netflix"
                  value={catForm.icon_url}
                  onChange={(e) => setCatForm({ ...catForm, icon_url: e.target.value })}
                  className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-xl transition"
              >
                Simpan Kategori
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL: TAMBAH PRODUK                                      */}
      {/* ========================================================= */}
      {activeModal === 'product' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#161b22] border border-slate-800 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">Tambah Produk Baru</h3>
                <p className="text-[11px] text-slate-400">
                  Katalog produk digital yang dapat dibeli pelanggan di Telegram.
                </p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleAddProduct} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-slate-300 mb-1">Kode Produk (Unik)</label>
                  <input
                    type="text"
                    required
                    placeholder="misal: spotify-1m"
                    value={prodForm.code}
                    onChange={(e) => setProdForm({ ...prodForm, code: e.target.value })}
                    className="w-full bg-[#0d1117] border border-slate-700 font-mono rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                  <span className="text-[10px] text-slate-500">Huruf kecil tanpa spasi</span>
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs text-slate-300">Kategori</label>
                    <button
                      type="button"
                      onClick={() => setActiveModal('category')}
                      className="text-[10px] text-indigo-400 hover:underline"
                    >
                      + Buat Baru
                    </button>
                  </div>
                  <select
                    value={prodForm.category_id}
                    onChange={(e) => setProdForm({ ...prodForm, category_id: e.target.value })}
                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">Pilih Kategori</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">Nama Produk</label>
                <input
                  type="text"
                  required
                  placeholder="Misal: Spotify Premium 1 Bulan"
                  value={prodForm.name}
                  onChange={(e) => setProdForm({ ...prodForm, name: e.target.value })}
                  className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-slate-300 mb-1">Harga (Rp)</label>
                  <input
                    type="number"
                    required
                    min="0"
                    placeholder="35000"
                    value={prodForm.price}
                    onChange={(e) => setProdForm({ ...prodForm, price: e.target.value })}
                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-300 mb-1">URL Logo (Opsional)</label>
                  <input
                    type="text"
                    placeholder="https://cdn.simpleicons.org/spotify"
                    value={prodForm.icon_url}
                    onChange={(e) => setProdForm({ ...prodForm, icon_url: e.target.value })}
                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-300 mb-1">Deskripsi Produk (Opsional)</label>
                <textarea
                  rows="2"
                  placeholder="Keterangan garansi, format akun, cara redeem, dsb..."
                  value={prodForm.description}
                  onChange={(e) => setProdForm({ ...prodForm, description: e.target.value })}
                  className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                ></textarea>
              </div>

              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setActiveModal('csv');
                    setCsvTab('product');
                  }}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-medium hover:underline flex items-center gap-1"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5" />
                  Atau import banyak produk via CSV
                </button>
              </div>

              <button
                type="submit"
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-xl transition shadow-lg shadow-indigo-600/30"
              >
                Simpan Produk
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL: ISI STOK                                           */}
      {/* ========================================================= */}
      {activeModal === 'stock' && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-[#161b22] border border-slate-800 rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">Upload Stok Akun / Lisensi</h3>
                <p className="text-[11px] text-slate-400">Tambahkan persediaan akun/voucher yang siap dikirim.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddStock} className="space-y-4">
              <div>
                <label className="block text-xs text-slate-300 mb-1">Pilih Produk Target</label>
                {products.length > 0 ? (
                  <select
                    required
                    value={stockForm.product_code}
                    onChange={(e) => setStockForm({ ...stockForm, product_code: e.target.value })}
                    className="w-full bg-[#0d1117] border border-slate-700 rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">-- Pilih Produk ({products.length} Tersedia) --</option>
                    {products.map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.name} ({p.code}) — Ready: {p.available_stock ?? p.stock_count ?? 0}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    required
                    placeholder="Ketik kode produk (misal: steam-50k)"
                    value={stockForm.product_code}
                    onChange={(e) => setStockForm({ ...stockForm, product_code: e.target.value })}
                    className="w-full bg-[#0d1117] border border-slate-700 font-mono rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                )}
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs text-slate-300 font-medium">
                    Data Stok (1 Baris = 1 Unit)
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveModal('csv');
                      setCsvTab('stock');
                      setCsvProductCode(stockForm.product_code);
                    }}
                    className="text-[11px] text-emerald-400 hover:text-emerald-300 hover:underline flex items-center gap-1"
                  >
                    <FileSpreadsheet className="w-3 h-3" />
                    Upload via File CSV
                  </button>
                </div>
                <textarea
                  rows="5"
                  required
                  placeholder={'user1@mail.com:pass123\nuser2@mail.com:pass456\nSTEAM-XXXX-YYYY-ZZZZ'}
                  value={stockForm.items_raw}
                  onChange={(e) => setStockForm({ ...stockForm, items_raw: e.target.value })}
                  className="w-full bg-[#0d1117] border border-slate-700 font-mono rounded-xl p-2.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                ></textarea>
                <p className="text-[10px] text-slate-500 mt-1">
                  Format dapat berupa <code>email:password</code>, kode voucher, atau tautan akun.
                </p>
              </div>

              <button
                type="submit"
                className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2.5 rounded-xl transition shadow-lg shadow-emerald-600/30"
              >
                Upload Stok Manual
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}