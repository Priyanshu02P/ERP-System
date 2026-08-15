import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { api } from '../api';

const AppDataCtx = createContext(null);

export function AppDataProvider({ children }) {
  const [products, setProducts] = useState([]);
  const [manufacturers, setManufacturers] = useState([]);
  const [units, setUnits] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [locations, setLocations] = useState([]);

  const [inventory, setInventory] = useState([]);
  const [logs, setLogs] = useState([]);

  const [suppliers, setSuppliers] = useState([]);
  const [purchaseRequisitions, setPurchaseRequisitions] = useState([]);
  const [rfqs, setRfqs] = useState([]);
  const [quotations, setQuotations] = useState([]);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [goodsReceipts, setGoodsReceipts] = useState([]);
  const [qualityInspections, setQualityInspections] = useState([]);
  const [vendorInvoices, setVendorInvoices] = useState([]);
  const [procKPIs, setProcKPIs] = useState(null);
  const [reorderSuggestions, setReorderSuggestions] = useState([]);

  const [loading, setLoading] = useState(true);

  // logs list filters are query params on the backend, so keep the last
  // used filter around for callers that just want to "refresh".
  const logFilterRef = useRef({ action: '', search: '' });

  const loadReferenceData = useCallback(async () => {
    const [p, m, u, w, l] = await Promise.all([
      api('/products?limit=500'),
      api('/manufacturers?limit=500'),
      api('/units?limit=500'),
      api('/warehouses?limit=500'),
      api('/locations?limit=1000'),
    ]);
    setProducts(p); setManufacturers(m); setUnits(u); setWarehouses(w); setLocations(l);
  }, []);

  const loadInventory = useCallback(async () => {
    const inv = await api('/inventory?limit=500');
    setInventory(inv);
    return inv;
  }, []);

  const loadLogs = useCallback(async (filter) => {
    if (filter) logFilterRef.current = filter;
    const { action, search } = logFilterRef.current;
    const params = new URLSearchParams({ limit: '300' });
    if (action) params.set('action', action);
    if (search) params.set('search', search);
    const l = await api(`/logs?${params.toString()}`);
    setLogs(l);
    return l;
  }, []);

  const loadSuppliers = useCallback(async () => {
    const s = await api('/suppliers?limit=500');
    setSuppliers(s);
    return s;
  }, []);

  const loadPRs = useCallback(async () => {
    const pr = await api('/purchase-requisitions?limit=500');
    setPurchaseRequisitions(pr);
    return pr;
  }, []);

  const loadRFQs = useCallback(async () => {
    const r = await api('/rfqs?limit=500');
    setRfqs(r);
    return r;
  }, []);

  const loadQuotations = useCallback(async () => {
    const q = await api('/quotations?limit=500');
    setQuotations(q);
    return q;
  }, []);

  const loadPOs = useCallback(async () => {
    const po = await api('/purchase-orders?limit=500');
    setPurchaseOrders(po);
    return po;
  }, []);

  const loadGRNs = useCallback(async () => {
    const g = await api('/goods-receipts?limit=500');
    setGoodsReceipts(g);
    return g;
  }, []);

  const loadQCs = useCallback(async () => {
    const q = await api('/quality-inspections?limit=500');
    setQualityInspections(q);
    return q;
  }, []);

  const loadInvoices = useCallback(async () => {
    const v = await api('/vendor-invoices?limit=500');
    setVendorInvoices(v);
    return v;
  }, []);

  const loadProcurementOverview = useCallback(async () => {
    const [kpis, suggestions] = await Promise.all([
      api('/procurement/kpis'),
      api('/procurement/reorder-suggestions'),
    ]);
    setProcKPIs(kpis);
    setReorderSuggestions(suggestions);
  }, []);

  const loadProcurementData = useCallback(async () => {
    await loadSuppliers();
    await Promise.all([loadPRs(), loadRFQs()]);
    await loadQuotations();
    await loadPOs();
    await loadGRNs();
    await Promise.all([loadQCs(), loadInvoices(), loadProcurementOverview()]);
  }, [loadSuppliers, loadPRs, loadRFQs, loadQuotations, loadPOs, loadGRNs, loadQCs, loadInvoices, loadProcurementOverview]);

  const init = useCallback(async () => {
    setLoading(true);
    await loadReferenceData();
    await Promise.all([loadInventory(), loadLogs({ action: '', search: '' })]);
    await loadProcurementData();
    setLoading(false);
  }, [loadReferenceData, loadInventory, loadLogs, loadProcurementData]);

  const triggerSeed = useCallback(async (clean) => {
    const result = await api(`/search/seed?clean=${clean}`, { method: 'POST' });
    await loadReferenceData();
    await Promise.all([loadInventory(), loadLogs()]);
    return result;
  }, [loadReferenceData, loadInventory, loadLogs]);

  const value = {
    products, manufacturers, units, warehouses, locations,
    inventory, logs,
    suppliers, purchaseRequisitions, rfqs, quotations,
    purchaseOrders, goodsReceipts, qualityInspections, vendorInvoices,
    procKPIs, reorderSuggestions,
    loading,
    loadReferenceData, loadInventory, loadLogs,
    loadSuppliers, loadPRs, loadRFQs, loadQuotations, loadPOs,
    loadGRNs, loadQCs, loadInvoices, loadProcurementOverview,
    loadProcurementData, init, triggerSeed,
  };

  return <AppDataCtx.Provider value={value}>{children}</AppDataCtx.Provider>;
}

export function useAppData() {
  return useContext(AppDataCtx);
}
