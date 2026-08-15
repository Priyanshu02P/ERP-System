import { useMemo, useState } from 'react';
import { useAppData } from '../state/AppDataContext';
import { byId } from '../utils/format';
import { TypeBadge } from '../components/Badges';

export default function Products() {
  const { products, units } = useAppData();
  const [search, setSearch] = useState('');
  const [fType, setFType] = useState('');
  const unitsById = useMemo(() => byId(units), [units]);

  const filtered = products.filter(p => {
    if (fType && p.product_type !== fType) return false;
    if (search) {
      const hay = `${p.code} ${p.name} ${p.part_number || ''}`.toLowerCase();
      if (!hay.includes(search.trim().toLowerCase())) return false;
    }
    return true;
  });

  return (
    <section className="page active">
      <div className="page-header">
        <div>
          <h1>Products</h1>
          <p>Master catalog of raw materials, work-in-progress, and finished goods.</p>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>
          <input type="text" placeholder="Search by product name, code, or part number…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select value={fType} onChange={(e) => setFType(e.target.value)}>
          <option value="">All product types</option>
          <option value="RAW">Raw material</option>
          <option value="WIP">Work in progress</option>
          <option value="FG">Finished good</option>
        </select>
        <div className="toolbar-spacer"></div>
        <span className="result-count">{filtered.length} of {products.length} products</span>
      </div>

      <div className="products-grid">
        {filtered.length === 0 ? (
          <div className="empty-state" style={{ gridColumn: '1/-1' }}>
            <div className="empty-icon">◫</div><p>No products match your search.</p>
          </div>
        ) : (
          filtered.map(p => {
            const unit = unitsById[p.unit_id];
            return (
              <div className="product-card" key={p.id}>
                <img src={p.image_url || ''} alt={p.name} onError={(e) => { e.currentTarget.style.opacity = '0.15'; }} />
                <div className="pc-name">{p.name}</div>
                <div className="pc-meta">{p.code}{p.part_number ? ' · ' + p.part_number : ''}</div>
                <div className="pc-desc">{p.description || ''}</div>
                <div className="pc-foot">
                  <TypeBadge type={p.product_type} />
                  <span className="pc-meta">{unit?.code || ''}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
