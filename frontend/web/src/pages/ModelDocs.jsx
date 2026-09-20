import { useState } from 'react';
import { MODULES, OVERVIEW, GLOSSARY, STATUS } from '../data/modelDocs';

/* ------------------------------------------------------------------ small building blocks */

const TONE_VAR = {
  accent: 'var(--accent)', warning: 'var(--warning)', danger: 'var(--danger)',
  info: 'var(--info)', text: 'var(--text-main)', neutral: 'var(--text-muted)',
};

function StatusBadge({ status }) {
  const s = STATUS[status];
  return (
    <span className={`pbadge pbadge-${s.tone}`} title={s.blurb}>
      <span className="md-dot" />{s.label}
    </span>
  );
}

function Tile({ label, value, hint }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-val">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </div>
  );
}

function Details({ title, open, children }) {
  return (
    <details className="md-details" open={open}>
      <summary>{title}</summary>
      <div className="md-details-body">{children}</div>
    </details>
  );
}

function Note({ children }) {
  return children ? <p className="md-note">{children}</p> : null;
}

/* ------------------------------------------------------------------ charts */

function BarList({ rows }) {
  const max = Math.max(...rows.map(r => r.value)) || 1;
  return (
    <div className="md-bars">
      {rows.map((r, i) => (
        <div className="md-bar-row" key={i}>
          <div className="md-bar-label">{r.label}</div>
          <div className="md-bar-track">
            <div className="md-bar-fill" style={{ width: `${Math.max((r.value / max) * 100, 1.5)}%`, background: TONE_VAR[r.tone || 'accent'] }} />
          </div>
          <div className="md-bar-val mono">{r.display}</div>
        </div>
      ))}
    </div>
  );
}

function PairBars({ series, rows }) {
  const max = Math.max(...rows.flatMap(r => r.values)) || 1;
  return (
    <div>
      <div className="md-legend">
        {series.map(s => (
          <span key={s.name}><i style={{ background: TONE_VAR[s.tone] }} />{s.name}</span>
        ))}
      </div>
      <div className="md-bars">
        {rows.map((r, i) => (
          <div className="md-pair-row" key={i}>
            <div className="md-bar-label">{r.label}</div>
            <div className="md-pair-bars">
              {r.values.map((v, j) => (
                <div className="md-pair-line" key={j}>
                  <div className="md-bar-track">
                    <div className="md-bar-fill" style={{ width: `${Math.max((v / max) * 100, 1.5)}%`, background: TONE_VAR[series[j].tone] }} />
                  </div>
                  <div className="md-bar-val mono">{r.displays[j]}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function niceScale(lo, hi) {
  const span = hi - lo || 1;
  const raw = span / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw);
  const min = Math.floor((lo - span * 0.1) / step) * step;
  const max = Math.ceil((hi + span * 0.05) / step) * step;
  const ticks = [];
  for (let v = min; v <= max + step / 2; v += step) ticks.push(v);
  return { min, max, ticks };
}

const kfmt = v => (Math.abs(v) >= 1000 ? `${+(v / 1000).toFixed(1)}k` : `${v}`);

function LineChart({ xLabels, series }) {
  const W = 720, H = 270, P = { l: 52, r: 16, t: 14, b: 30 };
  const all = series.flatMap(s => s.values);
  const { min, max, ticks } = niceScale(Math.min(...all), Math.max(...all));
  const x = i => P.l + (i * (W - P.l - P.r)) / (xLabels.length - 1);
  const y = v => P.t + (1 - (v - min) / (max - min)) * (H - P.t - P.b);
  return (
    <div>
      <div className="md-legend">
        {series.map(s => (
          <span key={s.name}><i style={{ background: TONE_VAR[s.tone] }} />{s.name}</span>
        ))}
      </div>
      <svg className="md-line" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Line chart of ${series.map(s => s.name).join(', ')} by month`}>
        {ticks.map(t => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} className="md-grid" />
            <text x={P.l - 8} y={y(t) + 4} textAnchor="end" className="md-axis">{kfmt(t)}</text>
          </g>
        ))}
        {xLabels.map((l, i) => (
          <text key={l} x={x(i)} y={H - 8} textAnchor="middle" className="md-axis">{l}</text>
        ))}
        {series.map(s => (
          <g key={s.name}>
            <polyline
              fill="none" stroke={TONE_VAR[s.tone]} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round"
              strokeDasharray={s.dashed ? '6 5' : undefined}
              points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
            />
            {!s.dashed && s.values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r="2.6" fill={TONE_VAR[s.tone]} />)}
          </g>
        ))}
      </svg>
    </div>
  );
}

function DataTable({ cols, rows }) {
  return (
    <div className="table-container md-table">
      <table>
        <thead>
          <tr>{cols.map(c => <th key={c.key} className={c.num ? 'md-num' : ''}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={r._hl ? 'md-row-hl' : ''}>
              {cols.map(c => <td key={c.key} className={c.num ? 'md-num mono' : ''}>{r[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Block({ block }) {
  switch (block.type) {
    case 'line': return <><LineChart xLabels={block.xLabels} series={block.series} /><Note>{block.note}</Note></>;
    case 'pairs': return <><PairBars series={block.series} rows={block.rows} /><Note>{block.note}</Note></>;
    case 'bars': return <><BarList rows={block.rows} /><Note>{block.note}</Note></>;
    case 'table': return <><DataTable cols={block.cols} rows={block.rows} /><Note>{block.note}</Note></>;
    case 'list': return <ul className="md-list">{block.items.map((t, i) => <li key={i}>{t}</li>)}</ul>;
    case 'text': return <p className="md-para">{block.body}</p>;
    default: return null;
  }
}

/* ------------------------------------------------------------------ model card */

function Chips({ items }) {
  return <div className="md-chips">{items.map((t, i) => <span className="md-chip" key={i}>{t}</span>)}</div>;
}

function ModelCard({ m }) {
  const hasStats = m.highlights && m.highlights.length > 0;
  return (
    <article className="card md-model" id={m.id}>
      <div className="md-model-head">
        <div>
          <h3>{m.name}</h3>
          <p className="md-tagline">{m.tagline}</p>
        </div>
        <StatusBadge status={m.status} />
      </div>
      <p className="md-dataset"><span>Data</span>{m.dataset}</p>

      <div className="md-cols">
        <div>
          <h4>What it does</h4>
          {m.what.map((p, i) => <p className="md-para" key={i}>{p}</p>)}
        </div>
        <div>
          <h4>Inputs</h4>
          <ul className="md-list">{m.inputs.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <h4>Outputs</h4>
          <ul className="md-list">{m.outputs.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      </div>

      {m.howTested && (
        <div className="md-how"><h4>How it was tested</h4><p className="md-para">{m.howTested}</p></div>
      )}

      {hasStats && (
        <>
          <h4 className="md-section">Key statistics</h4>
          <div className="stats-row md-tiles">{m.highlights.map(h => <Tile key={h.label} {...h} />)}</div>
        </>
      )}

      {m.status === 'pending' && (
        <div className="md-empty">
          <strong>No statistics yet.</strong> This pipeline has never been run, so there are no accuracy figures to show. Nothing on this page should be read as a result.
        </div>
      )}

      {m.blocks && m.blocks.length > 0 && (
        <>
          <h4 className="md-section">Detailed statistics</h4>
          {m.blocks.map((b, i) => (
            <Details key={i} title={b.title} open={i === 0}><Block block={b} /></Details>
          ))}
        </>
      )}

      {m.metrics && (
        <div className="md-plan">
          <h4 className="md-section">{m.status === 'results' ? 'Evaluation' : 'What will be measured once it is run'}</h4>
          {m.testDesign && <p className="md-para">{m.testDesign}</p>}
          {m.candidates && (<><h5>Candidates compared</h5><Chips items={m.candidates} /></>)}
          {m.selection && (<><h5>Used to pick the winner</h5><p className="md-para">{m.selection}</p></>)}
          <h5>Metrics that will be reported</h5>
          <Chips items={m.metrics} />
        </div>
      )}

      <div className="md-limits">
        <h4>Limitations and things to know</h4>
        <ul className="md-list">{m.limits.map((t, i) => <li key={i}>{t}</li>)}</ul>
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ views */

function ModuleView({ mod, onNavigate }) {
  const jump = id => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  return (
    <div className="md-stack">
      <div className="card md-module-head">
        <div>
          <h2>
            {mod.name}
            {mod.planned && <span className="pbadge pbadge-info" style={{ marginLeft: '0.7rem', verticalAlign: 'middle' }}>Module not yet in this ERP</span>}
          </h2>
          <p className="md-para">{mod.summary}</p>
        </div>
        {(mod.pages.length > 0 || mod.models.length > 2) && (
          <div className="md-module-links">
            {mod.pages.length > 0 && (
              <div>
                <span className="md-links-label">Related pages</span>
                {mod.pages.map(p => (
                  <button key={p.id} className="btn btn-secondary btn-sm" onClick={() => onNavigate(p.id)}>{p.label} →</button>
                ))}
              </div>
            )}
            {mod.models.length > 2 && (
              <div>
                <span className="md-links-label">Jump to</span>
                {mod.models.map(m => (
                  <button key={m.id} className="btn btn-ghost btn-sm" onClick={() => jump(m.id)}>{m.name}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {mod.shared && (
        <div className="card">
          <h3 className="md-h3">{mod.sharedTitle}</h3>
          <ul className="md-list">{mod.shared.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}

      {mod.models.map(m => <ModelCard key={m.id} m={m} />)}
    </div>
  );
}

function OverviewView({ onOpen }) {
  const byId = Object.fromEntries(MODULES.map(m => [m.id, m]));
  return (
    <div className="md-stack">
      <p className="md-para md-intro">{OVERVIEW.intro}</p>

      <div className="md-callout" role="note">
        <strong>{OVERVIEW.notice.title}</strong>
        <p>{OVERVIEW.notice.body}</p>
      </div>

      <div className="card">
        <h3 className="md-h3">Models and statistics by module</h3>
        <div className="table-container md-table">
          <table>
            <thead>
              <tr><th>Module</th><th>Models</th><th>Data used</th><th>Status</th><th>Statistics available</th></tr>
            </thead>
            <tbody>
              {OVERVIEW.coverage.map(row => {
                const mod = byId[row.module];
                const statuses = [...new Set(mod.models.map(m => m.status))];
                return (
                  <tr key={row.module}>
                    <td><button className="btn btn-ghost btn-sm md-link" onClick={() => onOpen(mod.id)}>{mod.name} →</button></td>
                    <td>
                      <div className="md-model-list">
                        {mod.models.map(m => <span key={m.id}>{m.name}</span>)}
                      </div>
                    </td>
                    <td className="md-cell-text">{row.trainedOn}</td>
                    <td><div className="md-status-stack">{statuses.map(s => <StatusBadge key={s} status={s} />)}</div></td>
                    <td className="md-cell-text">{row.stats}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3 className="md-h3">What the status badges mean</h3>
        <div className="md-legend-list">
          {Object.entries(STATUS).map(([k, s]) => (
            <div key={k}><StatusBadge status={k} /><span>{s.blurb}</span></div>
          ))}
        </div>
      </div>

      <div className="card">
        <Details title="Glossary: the measures used on this page">
          <dl className="md-glossary">
            {GLOSSARY.map(([term, def]) => (
              <div key={term}><dt>{term}</dt><dd>{def}</dd></div>
            ))}
          </dl>
        </Details>
      </div>
    </div>
  );
}

export default function ModelDocs({ onNavigate }) {
  const [tab, setTab] = useState('overview');
  const tabs = [{ id: 'overview', label: 'Overview' }, ...MODULES.map(m => ({ id: m.id, label: m.short, count: m.models.length }))];
  const active = MODULES.find(m => m.id === tab);

  const select = id => { setTab(id); window.scrollTo({ top: 0 }); };

  return (
    <section className="page active md-page">
      <div className="page-header">
        <div>
          <h1>Model docs</h1>
          <p>What each analytics model does, how it was tested, and the statistics available, grouped by ERP module.</p>
        </div>
      </div>

      <div className="tabs-row md-tabs" role="tablist">
        {tabs.map(t => (
          <button
            key={t.id} role="tab" aria-selected={tab === t.id}
            className={`tab-btn${tab === t.id ? ' active' : ''}`}
            onClick={() => select(t.id)}
          >
            {t.label}{t.count !== undefined && <span className="md-count">{t.count}</span>}
          </button>
        ))}
      </div>

      {active ? <ModuleView key={active.id} mod={active} onNavigate={onNavigate} /> : <OverviewView onOpen={select} />}
    </section>
  );
}
