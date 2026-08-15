import { byId } from './format';

export function productOptions(products, units) {
  const unitsById = byId(units);
  return products.map(p => ({ value: String(p.id), label: `${p.code} — ${p.name} (${unitsById[p.unit_id]?.code || ''})` }));
}

export function supplierOptions(suppliers) {
  return suppliers.map(s => ({ value: String(s.id), label: `${s.code} — ${s.name}` }));
}

export function manufacturerOptions(manufacturers) {
  return manufacturers.map(m => ({ value: String(m.id), label: `${m.code} — ${m.name}` }));
}

export function locationOptionsFlat(locations, warehouses) {
  const warehousesById = byId(warehouses);
  return locations.map(l => ({ value: String(l.id), label: `${warehousesById[l.warehouse_id]?.code || ''} · ${l.location_code} (${l.category})` }));
}

export function productLabel(products, id) {
  const p = byId(products)[id];
  return p ? `${p.code} — ${p.name}` : `#${id}`;
}
