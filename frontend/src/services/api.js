import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/admin/api`,
  auth: {
    username: import.meta.env.VITE_ADMIN_USERNAME || 'admin',
    password: import.meta.env.VITE_ADMIN_PASSWORD || 'admin123',
  },
});

export const getDashboardData = () => api.get('/dashboard');
export const createCategory = (data) => api.post('/categories', data);
export const updateCategory = (id, data) => api.put(`/categories/${id}`, data);
export const deleteCategory = (id) => api.delete(`/categories/${id}`);

export const createProduct = (data) => api.post('/products', data);
export const updateProduct = (code, data) => api.put(`/products/${code}`, data);
export const deleteProduct = (code) => api.delete(`/products/${code}`);

export const bulkAddStock = (data) => api.post('/stocks/bulk', data);
export const deleteStock = (id) => api.delete(`/stocks/${id}`);

// CSV Upload & Templates
export const uploadStockCsv = (formData) => api.post('/stocks/upload-csv', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
});

export const uploadProductCsv = (formData) => api.post('/products/upload-csv', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
});

export const getStockCsvTemplateUrl = () => `${API_BASE_URL}/admin/api/templates/stock-csv`;
export const getProductCsvTemplateUrl = () => `${API_BASE_URL}/admin/api/templates/product-csv`;

export default api;