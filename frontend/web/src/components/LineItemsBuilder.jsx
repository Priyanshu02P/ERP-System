let rowSeq = 0;
function nextRowId() { rowSeq += 1; return `row-${Date.now()}-${rowSeq}`; }

/** Returns a fresh blank row keyed by field.key (all values start as ''). */
export function blankRow(fields, values = {}) {
  const row = { _id: nextRowId() };
  fields.forEach(f => { row[f.key] = values[f.key] !== undefined ? values[f.key] : ''; });
  return row;
}

/** Converts builder rows into the plain objects the API expects, applying
 *  `numeric` coercion and dropping optional empty fields (matching the
 *  original collectLineRows() behaviour). */
export function collectRows(rows, fields) {
  return rows.map(row => {
    const obj = {};
    fields.forEach(f => {
      const v = row[f.key];
      if (v === '' || v === undefined || v === null) {
        if (f.required !== false) obj[f.key] = f.numeric ? NaN : '';
        return;
      }
      obj[f.key] = f.numeric ? Number(v) : v;
    });
    return obj;
  });
}

export default function LineItemsBuilder({ label, fields, rows, setRows, addLabel = '+ Add line' }) {
  const updateCell = (rowId, key, value) => {
    setRows(rows.map(r => (r._id === rowId ? { ...r, [key]: value } : r)));
  };
  const removeRow = (rowId) => setRows(rows.filter(r => r._id !== rowId));
  const addRow = () => setRows([...rows, blankRow(fields)]);

  return (
    <div className="line-items-wrap">
      <div className="line-items-head">
        <span>{label}</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={addRow}>{addLabel}</button>
      </div>
      <div>
        {rows.map(row => (
          <div className="line-row" key={row._id}>
            {fields.map(f => (
              <div className="form-group line-field" key={f.key}>
                <label>{f.label}</label>
                {f.type === 'select' ? (
                  <select
                    value={row[f.key]}
                    required={f.required !== false}
                    onChange={(e) => updateCell(row._id, f.key, e.target.value)}
                  >
                    <option value="" disabled hidden>Select…</option>
                    {(f.options || []).map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={f.type || 'text'}
                    step={f.step}
                    min={f.min}
                    placeholder={f.placeholder || ''}
                    required={f.required !== false}
                    value={row[f.key]}
                    onChange={(e) => updateCell(row._id, f.key, e.target.value)}
                  />
                )}
              </div>
            ))}
            <button type="button" className="line-remove-btn" title="Remove line" onClick={() => removeRow(row._id)}>✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
