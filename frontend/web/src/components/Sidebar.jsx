const WORKSPACE_ITEMS = [
  { id: 'dashboard', icon: '◈', label: 'Dashboard' },
  { id: 'inventory', icon: '▦', label: 'Inventory' },
  { id: 'products', icon: '◫', label: 'Products' },
  { id: 'logs', icon: '☰', label: 'Activity Logs' },
];

const PROCUREMENT_ITEMS = [
  { id: 'proc-overview', icon: '⌘', label: 'Overview' },
  { id: 'requisitions', icon: '✎', label: 'Requisitions' },
  { id: 'rfqs', icon: '⇄', label: 'RFQs' },
  { id: 'quotations', icon: '❖', label: 'Quotations' },
  { id: 'purchase-orders', icon: '⎘', label: 'Purchase Orders' },
  { id: 'goods-receipts', icon: '⇩', label: 'Goods Receipts' },
  { id: 'quality-inspections', icon: '✓', label: 'Quality Checks' },
  { id: 'vendor-invoices', icon: '▤', label: 'Vendor Invoices' },
  { id: 'suppliers', icon: '⚑', label: 'Suppliers' },
];

const INTELLIGENCE_ITEMS = [
  { id: 'model-docs', icon: '✦', label: 'Model Docs' },
];

export default function Sidebar({ page, onNavigate }) {
  const NavGroup = ({ items }) => (
    <nav className="nav-menu">
      {items.map(item => (
        <a
          key={item.id}
          className={`nav-item${page === item.id ? ' active' : ''}`}
          onClick={() => onNavigate(item.id)}
        >
          <span className="nav-icon">{item.icon}</span>
          <span>{item.label}</span>
        </a>
      ))}
    </nav>
  );

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">IMS</div>
        <div className="brand-text">
          <span className="brand-title">Inventory Control</span>
          <span className="brand-sub">WAREHOUSE OPS</span>
        </div>
      </div>

      <div className="nav-group-label">Workspace</div>
      <NavGroup items={WORKSPACE_ITEMS} />

      <div className="nav-group-label">Procurement</div>
      <NavGroup items={PROCUREMENT_ITEMS} />

      <div className="nav-group-label">Intelligence</div>
      <NavGroup items={INTELLIGENCE_ITEMS} />

      <div className="sidebar-foot">
        <a className="nav-item" href="/docs" target="_blank" rel="noreferrer">
          <span className="nav-icon">⇱</span><span>API Docs</span>
        </a>
      </div>
    </aside>
  );
}
