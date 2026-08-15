import { useEffect, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import ActionModal from './components/ActionModal';
import DetailModal from './components/DetailModal';
import { AppDataProvider, useAppData } from './state/AppDataContext';
import { ToastProvider } from './state/ToastContext';
import { OverlayProvider } from './state/OverlayContext';

import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import Products from './pages/Products';
import Logs from './pages/Logs';
import ProcurementOverview from './pages/ProcurementOverview';
import Requisitions from './pages/Requisitions';
import RFQs from './pages/RFQs';
import Quotations from './pages/Quotations';
import PurchaseOrders from './pages/PurchaseOrders';
import GoodsReceipts from './pages/GoodsReceipts';
import QualityInspections from './pages/QualityInspections';
import VendorInvoices from './pages/VendorInvoices';
import Suppliers from './pages/Suppliers';

function Shell() {
  const { init, loading } = useAppData();
  const [page, setPage] = useState('dashboard');
  const [navParams, setNavParams] = useState(null);
  const inventoryRef = useRef(null);

  useEffect(() => { init(); }, [init]);

  const navigate = (id, params) => {
    setPage(id);
    setNavParams(params || null);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
        Loading inventory system…
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={navigate} />
      <main className="main">
        {page === 'dashboard' && <Dashboard onNavigate={navigate} onOpenReceive={() => inventoryRef.current?.openReceive()} />}
        {page === 'inventory' && <Inventory ref={inventoryRef} />}
        {page === 'products' && <Products />}
        {page === 'logs' && <Logs />}
        {page === 'proc-overview' && <ProcurementOverview onNavigate={navigate} />}
        {page === 'requisitions' && <Requisitions onNavigate={navigate} />}
        {page === 'rfqs' && <RFQs onNavigate={navigate} navParams={navParams} />}
        {page === 'quotations' && <Quotations onNavigate={navigate} navParams={navParams} />}
        {page === 'purchase-orders' && <PurchaseOrders onNavigate={navigate} navParams={navParams} />}
        {page === 'goods-receipts' && <GoodsReceipts onNavigate={navigate} navParams={navParams} />}
        {page === 'quality-inspections' && <QualityInspections onNavigate={navigate} navParams={navParams} />}
        {page === 'vendor-invoices' && <VendorInvoices onNavigate={navigate} navParams={navParams} />}
        {page === 'suppliers' && <Suppliers />}
      </main>
      <ActionModal />
      <DetailModal />
    </div>
  );
}

export default function App() {
  return (
    <AppDataProvider>
      <ToastProvider>
        <OverlayProvider>
          <Shell />
        </OverlayProvider>
      </ToastProvider>
    </AppDataProvider>
  );
}
