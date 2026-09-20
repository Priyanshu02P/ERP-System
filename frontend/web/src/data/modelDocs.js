/**
 * Content for the "Model Docs" page, grouped by ERP module.
 *
 * Every number shown on the page comes from ./modelStats.json, which was extracted directly from the
 * model projects' output files (hospital_demand/outputs/*.csv and the executed notebook cells).
 * Edit prose here; refresh numbers by regenerating modelStats.json - never type a statistic by hand.
 *
 * Model status:
 *   results  - the model was trained and evaluated; statistics are available
 *   partial  - pipeline is built and the dataset analysed, but the model was never trained
 *   pending  - pipeline is built but has not been run at all (no statistics exist)
 */
import stats from './modelStats.json';

const { wms, maintenance: pm, quality: qa } = stats;

// ---------- formatting helpers ----------
const MINUS = '\u2212';
const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
const spct = (x, d = 1) => `${x > 0 ? '+' : x < 0 ? MINUS : ''}${Math.abs(x * 100).toFixed(d)}%`;
const int = (x) => Number(x).toLocaleString('en-US');
const pln = (x) => (x >= 1e6 ? `PLN ${(x / 1e6).toFixed(2)}M` : `PLN ${Math.round(x / 1e3).toLocaleString('en-US')}k`);
const dec = (x, d = 1) => Number(x).toFixed(d);

export const STATUS = {
  results: { label: 'Results available', tone: 'good', blurb: 'Trained and evaluated. Statistics are shown.' },
  partial: { label: 'Dataset analysed \u00b7 not trained', tone: 'progress', blurb: 'Pipeline built and data explored, but the model has not been trained, so there are no accuracy figures.' },
  pending: { label: 'Built \u00b7 not yet run', tone: 'neutral', blurb: 'Pipeline is complete but has never been run. No statistics exist yet.' },
};

// ================================================================== WMS
const K = wms.kpi;
const seg = wms.segments;
const S_SHORT = {
  S0: 'S0 \u00b7 Current process (ledger replay)',
  S1: 'S1 \u00b7 Financial plan + legacy safety stock',
  S2: 'S2 \u00b7 Forecast + legacy safety stock',
  S3: 'S3 \u00b7 Forecast + calibrated buffers, 99% service',
  S4: 'S4 \u00b7 As S3, batched orders (about half the POs)',
  S5: 'S5 \u00b7 Pure newsvendor service level (no floor)',
};
const F_SHORT = {
  'PlanBlend(Pooled+GBM,w=0.4)': 'Plan-blend: pooled seasonal + LightGBM + corrected plan',
  'Ensemble(Pooled+GBM)': 'Ensemble: pooled seasonal + LightGBM',
  GlobalGBM: 'LightGBM across all SKUs',
  Pooled: 'Pooled seasonal-level model',
  MovingAvg12: '12-month moving average',
  'PlanPhased(bias-corrected)': 'Financial plan, bias-corrected and phased by season',
  'FinancialPlan(flat)': 'Financial plan, spread evenly over the year',
  'HoltWinters(ETS)': 'Holt-Winters (ETS)',
  SeasonalNaive12: 'Seasonal naive (same month last year)',
  MovingAvg3: '3-month moving average',
};
const stratBySid = Object.fromEntries(wms.strategies.map((s) => [s.name.slice(0, 2), s]));
const S3 = stratBySid.S3;
const S0 = stratBySid.S0;
const champ = wms.models.find((m) => m.model === wms.run.champion);
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const stress = (scn, sid) => wms.stress.find((r) => r.scenario === scn && r.strategy.startsWith(sid));
const stressScenarios = [...new Set(wms.stress.map((r) => r.scenario))];
const leadShock = stress('Supplier lead time +1 month (policy unaware)', 'S3');
const grades = wms.reliability.grades;
const staleMonths = 9; // data ends Dec-2025; validation_report.csv freshness check reports 9 months at run time (2026-09-19)

const WMS_MODULE = {
  id: 'wms',
  name: 'Warehouse (WMS)',
  short: 'WMS',
  icon: '\u25a6',
  summary:
    'Two models work as a pair to answer \u201chow much will we need, and how much should we hold?\u201d. The demand forecast predicts monthly units per SKU. The replenishment planner turns those forecasts, plus lead time, shelf life and a service target, into order-up-to levels and order quantities. Both were built and tested on a sample hospital-pharmacy dataset.',
  pages: [
    { id: 'inventory', label: 'Inventory' },
    { id: 'products', label: 'Products' },
  ],
  models: [
    {
      id: 'wms-demand',
      name: 'Demand forecast',
      tagline: 'How many units of each SKU will we use next month, and over the next year?',
      status: 'results',
      dataset: `Sample data: hospital drug sales, ${wms.run.n_skus} SKUs, ${wms.run.train_period.slice(0, 4)}\u2013${wms.run.holdout_period.slice(0, 4)} (${wms.run.currency})`,
      what: [
        'Predicts monthly unit demand for every SKU up to 12 months ahead. The champion model blends three signals: a seasonal pattern pooled across SKUs, a gradient-boosting model (LightGBM) trained on all SKUs together, and the annual financial plan \u2014 after correcting the plan\u2019s systematic bias and spreading it across months by season.',
        `The plan is consistently too low: it under-plans ${pct(K['plan_underplanned_skus_%'], 0)} of SKUs and misses actual value by ${pct(Math.abs(K['plan_var_vs_actual_%']), 1)}. The blend keeps the plan\u2019s useful growth signal but removes that bias.`,
      ],
      inputs: [
        'Monthly sales per SKU (24 months of training history)',
        'Month-end inventory (used to spot months where a stock-out capped sales)',
        'Annual financial plan in units',
        'Product parameters: price, lead time, shelf life',
      ],
      outputs: [
        '12-month unit and value forecast per SKU',
        'Reliability grade per SKU: A automate, B monitor, C human review',
        'Rolling accuracy and bias monitor with alerts',
      ],
      howTested: `Trained on ${wms.run.train_period} and tested on the untouched ${wms.run.holdout_period.slice(0, 4)} year, forecasting 1\u20134 months ahead from rolling start points. Settings were tuned on an inner 2024 window only. The champion was then chosen using the 2025 hold-out (lowest error among models within 2% of the lowest simulated cost), so reported gains are mildly optimistic.`,
      highlights: [
        { label: 'Annual SKU error (WAPE)', value: pct(K.forecast_WAPE_sku_annual), hint: `financial plan: ${pct(K.plan_WAPE_sku_annual)}` },
        { label: 'SKUs within \u00b110% of actual', value: pct(K['forecast_hit_rate_10%'], 0), hint: `financial plan: ${pct(K['plan_hit_rate_10%'], 0)}` },
        { label: 'Total value vs actual', value: spct(K['forecast_var_vs_actual_%']), hint: `financial plan: ${spct(K['plan_var_vs_actual_%'])}` },
        { label: 'Monthly SKU error (WAPE)', value: pct(champ.wape), hint: 'close to the ~21.8% noise floor' },
      ],
      blocks: [
        {
          type: 'line',
          title: `Monthly units, ${wms.run.holdout_period.slice(0, 4)}: plan vs forecast vs actual`,
          xLabels: MONTHS,
          series: [
            { name: 'Financial plan (spread evenly)', values: wms.monthly.map((m) => m.plan), tone: 'warning', dashed: true },
            { name: 'Forecast (made Dec 2024)', values: wms.monthly.map((m) => m.forecast), tone: 'accent' },
            { name: 'Actual', values: wms.monthly.map((m) => m.actual), tone: 'text' },
          ],
          note: 'Whole portfolio, all SKUs. The flat plan cannot follow the June\u2013August peak; the forecast follows it but still runs a little low.',
        },
        {
          type: 'pairs',
          title: 'Annual SKU error (WAPE) by ABC class \u2014 lower is better',
          series: [{ name: 'Financial plan', tone: 'warning' }, { name: 'Forecast', tone: 'accent' }],
          rows: seg.map((s) => ({
            label: `${s.segment} \u00b7 ${s.n_skus} SKUs`,
            values: [s.plan_wape, s.forecast_wape],
            displays: [pct(s.plan_wape), pct(s.forecast_wape)],
          })),
          note: 'ABC class ranks SKUs by annual value: A is the highest-value group.',
        },
        {
          type: 'table',
          title: 'Plan vs forecast: headline comparison',
          cols: [{ key: 'metric', label: 'Measure' }, { key: 'plan', label: 'Financial plan', num: true }, { key: 'fc', label: 'Forecast', num: true }],
          rows: [
            { metric: 'Total value vs actual', plan: spct(K['plan_var_vs_actual_%']), fc: spct(K['forecast_var_vs_actual_%']) },
            { metric: 'Annual SKU error (WAPE)', plan: pct(K.plan_WAPE_sku_annual), fc: pct(K.forecast_WAPE_sku_annual) },
            { metric: 'Annual SKU error, value-weighted', plan: pct(K.plan_WAPE_sku_annual_PLNweighted), fc: pct(K.forecast_WAPE_sku_annual_PLNweighted) },
            { metric: 'SKUs within \u00b110% of actual', plan: pct(K['plan_hit_rate_10%']), fc: pct(K['forecast_hit_rate_10%']) },
            { metric: 'SKUs within \u00b120% of actual', plan: pct(K['plan_hit_rate_20%']), fc: pct(K['forecast_hit_rate_20%']) },
            { metric: 'Monthly portfolio error (MAPE)', plan: pct(K.monthly_portfolio_MAPE_plan), fc: pct(K.monthly_portfolio_MAPE_forecast_rolling) },
            { metric: 'Monthly SKU error (WAPE)', plan: pct(K.monthly_sku_WAPE_plan), fc: pct(champ.wape) },
          ],
          note: `Error reduction vs the plan on annual SKU error: ${pct(K['forecast_value_added_annual_sku_WAPE_%'])}. Annual rows use the 12-month-ahead forecast made at the end of 2024. Monthly rows use the rolling 1\u20134 month forecast.`,
        },
        {
          type: 'table',
          title: 'Model leaderboard (2025 hold-out, 1\u20134 months ahead)',
          cols: [
            { key: 'model', label: 'Model' },
            { key: 'wape', label: 'WAPE', num: true },
            { key: 'bias', label: 'Bias', num: true },
            { key: 'cost', label: 'Sim. total cost', num: true },
            { key: 'rc', label: 'Rank: cost', num: true },
            { key: 'rw', label: 'Rank: WAPE', num: true },
          ],
          rows: wms.models.map((m) => ({
            model: F_SHORT[m.model] || m.model,
            wape: pct(m.wape),
            bias: spct(m.bias),
            cost: pln(m.total_cost),
            rc: m.rank_cost,
            rw: m.rank_wape,
            _hl: m.model === wms.run.champion,
          })),
          note: 'WAPE = total absolute error \u00f7 total actual demand. Bias below zero means forecasts run under actual demand. \u201cSim. total cost\u201d is what each model costs when it drives the same ordering policy in the simulator. Highlighted row is the champion.',
        },
        {
          type: 'bars',
          title: 'SKU reliability grades',
          rows: [
            { label: 'A \u00b7 automate', value: grades.A, display: `${grades.A} SKUs`, tone: 'accent' },
            { label: 'B \u00b7 monitor', value: grades.B, display: `${grades.B} SKUs`, tone: 'warning' },
            { label: 'C \u00b7 human review', value: grades.C, display: `${grades.C} SKUs`, tone: 'danger' },
          ],
          note: `Grade depends on how many risk flags a SKU raises. Flags raised (a SKU can have several): ${Object.entries(wms.reliability.reasons).map(([k, v]) => `${k} (${v})`).join('; ')}.`,
        },
        {
          type: 'text',
          title: 'Model health monitoring',
          body: `Rolling 3-month WAPE and bias were tracked for ${wms.health.months} months (${wms.health.first} to ${wms.health.last}). Rolling WAPE stayed between ${pct(wms.health.roll_wape_min)} and ${pct(wms.health.roll_wape_max)}, and ${wms.health.alerts === 0 ? 'no alerts fired' : `${wms.health.alerts} alerts fired`}. An alert fires when bias exceeds \u00b18% or WAPE exceeds 1.25\u00d7 its reference level.`,
        },
      ],
      limits: [
        `Monthly error per SKU is about ${pct(champ.wape, 0)}, close to the ~22% floor for a benchmark with perfect knowledge of level and seasonality. Gains come from an unbiased level, not sharper monthly forecasts.`,
        'The data records sales, not demand. In 182 product-months (109 SKUs) stock hit zero, so true demand was higher than what was recorded.',
        'Summer peaks are under-forecast: one-month bias was about \u22126% to \u221210% in June and August in both 2024 and 2025.',
        'Only 36 months of history. SKUs with under 12 months of history are not supported (never validated).',
        `${grades.C} SKUs are graded C (frequent spikes, level shifts or low forecastability) and should be reviewed by a person.`,
        `Data ends ${wms.run.data_through}. It was ${staleMonths} months old at the time of the run, so refresh it before acting on any figure here.`,
      ],
    },
    {
      id: 'wms-replenish',
      name: 'Replenishment planner',
      tagline: 'When should we order, and how much, so we rarely run out without over-stocking?',
      status: 'results',
      dataset: `Sample data: hospital drug ledger, ${wms.run.n_skus} SKUs, FY2025 replay (${wms.run.currency})`,
      what: [
        'Turns the forecast into an order-up-to level per SKU: expected demand over the protection period (lead time plus one review month) plus a safety buffer sized from the forecast\u2019s own past errors, aiming at a 99% service target. Levels are capped so stock does not outlive shelf life.',
        'A monthly simulator (lead times, first-in-first-out batches, shelf-life expiry, lost sales) replays 2025 under six different policies so they can be compared on cost, not just on forecast error.',
      ],
      inputs: [
        'Demand forecast per SKU',
        'Lead time, shelf life, storage cost and price per SKU',
        'Current stock on hand (open purchase orders are not in the data and are assumed to be zero)',
        'Cost assumptions: stock-out = 3\u00d7 price, capital 1% per month, 25 PLN per PO, expiry = 100% of price',
      ],
      outputs: [
        'Order-up-to level and safety stock per SKU',
        `Recommended order quantities (latest run: ${wms.reorder.as_of})`,
        'Service-level vs cost curve; stress-test results',
      ],
      howTested: 'FY2025 replay: each policy runs through the same simulator on 2025 demand. Months where stock hit zero are lifted to expected demand. Total cost = holding + capital + expiry + stock-out penalty + ordering. The cost figures depend on the assumed unit costs above; they are assumptions, not measured data.',
      highlights: [
        { label: 'Total cost vs current process', value: spct(S3.vs_current), hint: `${pln(S3.total_cost)} vs ${pln(S0.total_cost)} (S3)` },
        { label: 'Average stock value', value: pln(S3.avg_inventory), hint: `current process: ${pln(S0.avg_inventory)}` },
        { label: 'Stock-out product-months', value: pct(S3.stockout_pm, 2), hint: `current: ${pct(S0.stockout_pm, 2)} (a lower bound)` },
        { label: 'Fill rate', value: pct(S3.fill_rate, 2), hint: 'S3, cost-optimal policy' },
      ],
      blocks: [
        {
          type: 'bars',
          title: 'Total simulated cost by policy, FY2025',
          rows: wms.strategies.map((s) => {
            const sid = s.name.slice(0, 2);
            return {
              label: S_SHORT[sid] || s.name,
              value: s.total_cost,
              display: `${pln(s.total_cost)}${sid === 'S0' ? '' : ` (${spct(s.vs_current)})`}`,
              tone: sid === 'S0' ? 'neutral' : s.vs_current < 0 ? 'accent' : 'warning',
            };
          }),
          note: 'Percentages are vs the current process (S0). S0 is replayed from the real ledger; its stock-out rate is a lower bound because history is censored by stock-outs. The project recommends S4 for critical items and S3 elsewhere.',
        },
        {
          type: 'table',
          title: 'Policy comparison in detail',
          cols: [
            { key: 'name', label: 'Policy' },
            { key: 'fill', label: 'Fill rate', num: true },
            { key: 'so', label: 'Stock-out product-months', num: true },
            { key: 'inv', label: 'Avg stock', num: true },
            { key: 'orders', label: 'POs', num: true },
          ],
          rows: wms.strategies.map((s) => ({
            name: S_SHORT[s.name.slice(0, 2)] || s.name,
            fill: pct(s.fill_rate, 2),
            so: pct(s.stockout_pm, 2),
            inv: pln(s.avg_inventory),
            orders: int(s.orders),
          })),
        },
        {
          type: 'table',
          title: 'Service level vs cost',
          cols: [
            { key: 'sl', label: 'Target service level', num: true },
            { key: 'cost', label: 'Total cost', num: true },
            { key: 'fill', label: 'Fill rate', num: true },
            { key: 'so', label: 'Stock-out product-months', num: true },
          ],
          rows: wms.frontier.map((f) => ({ sl: pct(f.service, 1), cost: pln(f.total_cost), fill: pct(f.fill_rate, 2), so: pct(f.stockout_pm, 2), _hl: f.service === 0.99 })),
          note: 'Cost is nearly flat between 98% and 99.5%, and rises sharply at 99.9%. That flat region is why the ranking of policies holds up even if the assumed stock-out penalty is wrong.',
        },
        {
          type: 'table',
          title: 'Stress tests (FY2025 replay)',
          cols: [
            { key: 'scn', label: 'Scenario' },
            { key: 's0', label: 'S0 current', num: true },
            { key: 's1', label: 'S1 plan-driven', num: true },
            { key: 's3', label: 'S3 cost-optimal', num: true },
            { key: 'fill', label: 'S3 fill rate', num: true },
          ],
          rows: stressScenarios.map((scn) => {
            const a = stress(scn, 'S0'); const b = stress(scn, 'S1'); const c = stress(scn, 'S3');
            return { scn, s0: a ? pln(a.total_cost) : '\u2014', s1: b ? pln(b.total_cost) : '\u2014', s3: c ? pln(c.total_cost) : '\u2014', fill: c ? pct(c.fill_rate, 1) : '\u2014' };
          }),
          note: 'S0 is a replay of history, so it cannot be stressed on lead time (shown as \u2014).',
        },
        {
          type: 'table',
          title: 'Buffer calibration: does the safety stock cover what it promises?',
          cols: [
            { key: 'n', label: 'Target coverage', num: true },
            { key: 'r', label: 'Realised coverage', num: true },
            { key: 'w', label: 'Test windows', num: true },
          ],
          rows: wms.calibration.map((c) => ({ n: pct(c.nominal, 0), r: pct(c.realised, 1), w: int(c.windows) })),
          note: 'Realised coverage should be at or above target. At 98% and 99% it lands slightly below (97.8% and 98.7%), so actual service could fall 0.2\u20130.3 points short of target.',
        },
        {
          type: 'text',
          title: `Latest recommendation run (${wms.reorder.as_of})`,
          body: `${wms.reorder.skus_to_order} of ${wms.reorder.n_skus} SKUs were flagged for an order, worth ${pln(wms.reorder.order_value_pln)}. This assumes no open purchase orders and is based on data that ends ${wms.run.data_through} \u2014 it is stale and must not be used to place orders without refreshing.`,
        },
      ],
      limits: [
        `Supplier lead-time shocks are the biggest risk: if lead times grow by one month and the policy is not told, S3\u2019s fill rate drops to ${pct(leadShock.fill_rate, 1)} and stock-outs reach ${pct(leadShock.stockout_pm, 0)} of product-months.`,
        'Cost figures rely on assumed unit costs. Replace them with finance and clinical numbers and re-run before treating PLN totals as real.',
        'Assumes no back-orders, no minimum order quantities or pack sizes, and no open purchase orders.',
        'History never writes off expired stock, so expiry cost is understated for the current process.',
        'One simulated year on one hold-out path; cost differences under 2% between candidates are noise.',
        `The ${wms.reorder.as_of} order list was already ${staleMonths} months out of date when it was generated. Refresh the data and enter open purchase orders before using it.`,
      ],
    },
  ],
};

// ================================================================== Procurement
const PROC_DATASET = 'Public Kaggle procurement KPI dataset (file not included in the project upload)';
const SHARED_VALIDATION = [
  'Orders are sorted by date. The latest 20% of purchase orders are a hold-out that each model touches only once.',
  'The earlier 80% uses five rolling-origin folds. A training row is only used if its outcome (delivery date) was known before the fold\u2019s first test order, so there is no look-ahead.',
  'Supplier-history features use only outcomes known before each PO\u2019s order date. Labels that depend on statistics (for example \u201cdelayed\u201d) are computed from the training fold only.',
  'Every model is compared with simple baselines. A model that does not beat the baseline in most folds should not be used.',
  'Every run is logged to an Excel experiment log: metrics, per-fold losses, data fingerprint and library versions.',
];

const PROC_MODULE = {
  id: 'procurement',
  name: 'Procurement',
  short: 'Procurement',
  icon: '\u2318',
  summary:
    'Six models look at buying from different angles: how late an order will be, how many units will arrive defective, whether an order will breach compliance, whether a price looks wrong, how much will be spent, and which suppliers are getting riskier. All six use the same time-aware validation design. The pipelines are complete but have never been run, so there are no results yet.',
  pages: [
    { id: 'proc-overview', label: 'Overview' },
    { id: 'suppliers', label: 'Suppliers' },
    { id: 'purchase-orders', label: 'Purchase Orders' },
  ],
  sharedTitle: 'Validation design shared by all six models',
  shared: SHARED_VALIDATION,
  models: [
    {
      id: 'proc-leadtime',
      name: 'Lead time & delay',
      tagline: 'When will this order really arrive, and will it be late?',
      status: 'pending',
      dataset: PROC_DATASET,
      what: [
        'At the moment a PO is created, predicts three things: the expected lead time in days; a median (P50) and a pessimistic (P90) lead time for buffers and promise dates; and the probability that the order is late.',
        '\u201cLate\u201d means the lead time exceeds that supplier\u2019s usual 75th percentile, or a fixed SLA in days if you set one. Use it to set realistic promise dates and to flag orders that need a follow-up call.',
      ],
      inputs: ['Supplier and item category', 'Quantity, order value, unit price and price gap vs negotiated price', 'Order month and weekday', 'The supplier\u2019s own past lead times (only outcomes known at order date)'],
      outputs: ['Expected lead time (days)', 'P50 and P90 lead time (days)', 'Probability the PO is late'],
      candidates: ['Global-mean and supplier-history baselines', 'Ridge regression', 'Gradient boosting (two depths)', 'Quantile gradient boosting (P50, P90)', 'Logistic regression', 'Calibrated gradient-boosting classifier'],
      selection: 'MAE (lead time) \u00b7 pinball loss (P50/P90) \u00b7 PR-AUC (late-order flag)',
      metrics: ['MAE, RMSE, bias', 'Pinball loss and coverage of P50/P90', 'PR-AUC, ROC-AUC, Brier score', 'Cost per PO at the best threshold (a missed late order is weighted 3\u00d7 a needless chase-up, an editable placeholder)', 'Recall at 50% precision', 'Share of late POs caught in the top 10% of scores'],
      limits: [
        'Only delivered orders have a lead time, so the newest orders lean toward short lead times. Hold-out numbers will look slightly better than reality.',
        'The 3:1 cost weighting is a placeholder. Set it to your real cost of a missed delay vs an unnecessary chase-up.',
      ],
    },
    {
      id: 'proc-defect',
      name: 'Defect rate',
      tagline: 'How many units of this order will arrive defective?',
      status: 'pending',
      dataset: PROC_DATASET,
      what: [
        'Predicts the expected defect rate of a PO before it is delivered (defective units \u00f7 quantity) and multiplies it by quantity to give expected defective units. It helps decide which POs deserve heavier inspection, forecast chargebacks, and support supplier quality conversations.',
        'Suppliers or categories with few orders are handled with empirical-Bayes shrinkage, which pulls thin data toward the supplier and then the global rate. It is compared against Ridge and gradient boosting.',
      ],
      inputs: ['Supplier and item category', 'Quantity, order value, price gap, season', 'The supplier\u2019s past defect rates and lead times'],
      outputs: ['Expected defect rate per PO', 'Expected defective units per PO'],
      candidates: ['Global-rate and supplier-history baselines', 'Hierarchical shrinkage (three settings)', 'Ridge regression', 'Gradient boosting (two depths)'],
      selection: 'Binomial deviance (a proper score for rates, weighted by order quantity)',
      metrics: ['Weighted MAE and RMSE', 'Aggregate bias (expected vs actual defective units)', 'Capture@20%: share of all defective units sitting in the riskiest 20% of POs', 'Calibration by supplier and by risk quintile'],
      limits: [
        'Training needs a count of defective units per PO. In this ERP the closest field is the rejected quantity recorded at Quality Checks.',
        'Small suppliers and categories give noisy estimates; the shrinkage design exists for exactly this reason.',
      ],
    },
    {
      id: 'proc-compliance',
      name: 'Compliance breach',
      tagline: 'Which orders are most likely to breach compliance and deserve an audit?',
      status: 'pending',
      dataset: PROC_DATASET,
      what: [
        'Estimates the probability that a PO will turn out non-compliant, using only what is known at order time. It ranks orders so audit and documentation checks go to the riskiest first, and it puts a number on supplier compliance risk for contract reviews.',
        'The notebook also produces a threshold table (how many POs get flagged, and how many breaches that catches) and a permutation-importance chart showing which inputs matter.',
      ],
      inputs: ['Supplier and item category', 'Order size, price gap, season', 'The supplier\u2019s past non-compliance, defect and lead-time history'],
      outputs: ['Probability of non-compliance per PO', 'Audit-workload vs recall table', 'Feature importance'],
      candidates: ['Class-prior and supplier-history baselines', 'Logistic regression (two strengths)', 'Gradient boosting', 'Calibrated gradient boosting'],
      selection: 'PR-AUC (breaches are usually the minority class)',
      metrics: ['ROC-AUC, Brier score, log-loss', 'Recall at 50% precision', 'Capture@10%: share of breaches found by auditing the riskiest 10% of POs', 'Cost per PO (a missed breach is weighted 5\u00d7 an unnecessary audit, an editable placeholder)'],
      limits: [
        'With very few suppliers, the simple baselines may win. The notebook treats that as a legitimate result and warns when there are fewer than 30 breaches.',
        'The ERP does not record a compliance flag today. One would have to be captured before this model can be trained on live data.',
      ],
    },
    {
      id: 'proc-price',
      name: 'Price anomaly detection',
      tagline: 'Which orders have an unusual price or quantity?',
      status: 'pending',
      dataset: PROC_DATASET,
      what: [
        'An unsupervised detector that ranks POs by how unusual their price gap vs the negotiated price, unit price (relative to its category) and quantity are. It produces a review queue for maverick buying, contract non-compliance and data-entry mistakes, sized to what analysts can review (default: the top 5% of POs).',
        'Because there are no confirmed anomalies to learn from, it is tested by injecting fake ones and checking how many are recovered.',
      ],
      inputs: ['Unit price and negotiated price (price gap)', 'Quantity and order value', 'Item category and supplier'],
      outputs: ['Anomaly score per PO', 'Ranked review queue within the alert budget'],
      candidates: ['Robust z-score on price gap only', 'Robust z-score on price gap, price and quantity', 'Isolation Forest (two settings)', 'Local Outlier Factor'],
      selection: 'PR-AUC on injected anomalies',
      metrics: ['ROC-AUC', 'Precision and recall within the 5% alert budget', 'Clean alert rate: on normal data the alert rate should stay near 5%'],
      testDesign: 'In each validation window, 5% of POs are turned into synthetic anomalies: overpay (price \u00d71.25\u20132.0), underpay (\u00d70.4\u20130.75) or quantity spike (\u00d75\u201312).',
      limits: [
        'The injected anomaly sizes are a stress test, not a claim about real overpayment. The real test is an analyst reviewing the top-ranked POs; confirmed cases should be fed back as labels.',
        'It needs both a unit price and a negotiated price. The ERP has no separate negotiated-price field today, so a source would have to be defined (for example, quotation rate vs PO rate).',
      ],
    },
    {
      id: 'proc-spend',
      name: 'Spend forecast',
      tagline: 'How much will we spend over the next few months?',
      status: 'pending',
      dataset: PROC_DATASET,
      what: [
        'Forecasts total monthly spend (and optionally spend per item category) for the next 3 months, with 90% prediction intervals. Cancelled orders are excluded. It supports budgeting, cash planning and volume-based negotiation.',
      ],
      inputs: ['Monthly order value from the PO history'],
      outputs: ['Spend forecast per month for the next 3 months', '90% prediction interval'],
      candidates: ['Naive', 'Seasonal naive', '6-month moving average', 'ETS: simple, damped trend, damped trend with seasonality', 'ARIMA(1,1,1)'],
      selection: 'MASE (error scaled by a naive forecast; below 1 beats naive)',
      metrics: ['sMAPE, MAE, RMSE, bias', '90% interval coverage'],
      testDesign: 'Rolling-origin back-test: refit at each origin, forecast 3 months, compare to actuals. The last 6 origins are the hold-out, and development windows end before it begins.',
      limits: [
        'About three years of monthly data is roughly 36 points. Seasonal models need at least two full yearly cycles; otherwise the code silently falls back to non-seasonal versions.',
        'If the last month in the data is incomplete, drop it (there is a switch for this) or the forecast will start too low.',
      ],
    },
    {
      id: 'proc-supplier-risk',
      name: 'Supplier risk score',
      tagline: 'Which suppliers are becoming riskier next quarter?',
      status: 'pending',
      dataset: PROC_DATASET,
      what: [
        'Combines each supplier\u2019s quarterly KPIs into one 0\u2013100 risk percentile and a band: Green up to 50, Amber 50\u201380, Red above 80. Contribution bars show why a supplier is red. Expert weights (to be agreed with the business): defect rate 35%, non-compliance 25%, average lead time 15%, lead-time variability 15%, cancellation rate 10%.',
        'Rates are shrunk toward the pooled rate and smoothed across quarters so a quarter with two POs does not swing the score.',
      ],
      inputs: ['Per-supplier, per-quarter defect rate, non-compliance rate, lead-time level and variability, cancellation rate'],
      outputs: ['Risk percentile 0\u2013100 and Green / Amber / Red band per supplier', 'Contribution of each KPI to the score', 'Risk trend by quarter'],
      candidates: ['Last-quarter persistence (naive)', 'Expert-weights scorecard', 'Equal-weights scorecard', 'Learned non-negative weights (logistic)'],
      selection: 'Spearman rank correlation between score and realised next-quarter risk',
      metrics: ['ROC-AUC and PR-AUC for \u201cadverse next quarter\u201d (above the training-period 75th percentile)', 'Top-pick hit rate: is the highest-scored supplier among the two worst next quarter?', 'Mean per-origin rank correlation'],
      testDesign: 'Expanding-window back-test by quarter: at each quarter, score every supplier using only earlier data, then compare with what actually happened the following quarter.',
      limits: [
        'Designed for a tiny sample (around 5 suppliers over about 12 quarters). Treat any result as directional and re-run on a full ERP extract.',
        'Price gap is left out on purpose because its sign depends on how unit and negotiated prices are defined.',
        'The ERP does not record a compliance flag today, and the score uses a non-compliance rate.',
      ],
    },
  ],
};

// ================================================================== Quality
const dsplit = qa.dataset.splits;
const prev = qa.dataset.notok_prevalence;
const cond = qa.conditions;
const tot = (k) => dsplit.train[k] + dsplit.valid[k] + dsplit.test[k];
const totalBoxes = tot('bad') + tot('good') + tot('defect');
const bpi = qa.dataset.boxes_per_image;

const QUALITY_MODULE = {
  id: 'quality',
  name: 'Quality (QA)',
  short: 'Quality',
  icon: '\u2713',
  summary:
    'One model that inspects photographs of welds. It finds each weld, judges it, and decides whether the image can be passed automatically, rejected automatically, or should go to a person. The pipeline and data preparation are done, but the model itself has not been trained, so there are dataset statistics only.',
  pages: [{ id: 'quality-inspections', label: 'Quality Checks' }],
  models: [
    {
      id: 'qa-weld',
      name: 'Weld defect inspection',
      tagline: 'Is this weld OK, and if we are not sure, who should look at it?',
      status: 'partial',
      dataset: `Public Kaggle welding-defect image set: ${int(tot('images'))} images, ${int(totalBoxes)} labelled welds`,
      what: [
        'Finds weld regions in an image and classifies each as Good Weld, Bad Weld or Defect. A safety-first decision layer then gives every image a single verdict: PASS, REJECT or REVIEW (send to a person).',
        'The layer is tuned to miss as few faulty welds as possible. An image is auto-passed only if its risk score is low enough that at most 2% of truly faulty validation images would slip through. It is auto-rejected only where precision is at least 90%. Everything in between, or any image where no weld is found, goes to a human. Confidence scores are recalibrated only when their calibration error exceeds 0.05.',
        'Two approaches are compared on identical data: (A) a single YOLO11s detector with three classes, and (B) a YOLO weld finder followed by an EfficientNet-B0 classifier applied to each weld crop. Both are trained on the raw data and on a filtered version. Focal loss is used because the classes are imbalanced.',
      ],
      inputs: ['A photograph of a weld (640\u00d7640 pixels)'],
      outputs: ['Each weld\u2019s class (Good, Bad, Defect) and confidence', 'Image verdict: PASS, REJECT or REVIEW, with a confidence value', 'Human-review queue and a gallery of failure cases'],
      candidates: ['A: YOLO11s, 3 classes (raw and filtered data)', 'B: YOLO weld detector + EfficientNet-B0 crop classifier (raw and filtered data)'],
      selection: 'Lowest human-review rate at the 2% miss target, measured on validation data only',
      metrics: ['mAP@0.5 per class and overall', 'Precision, recall, F1 and class accuracy', 'Image-level AUROC for faulty vs OK', 'Miss rate on faulty images, with a 95% confidence interval', 'Human-review rate and auto-reject precision', 'Calibration error (ECE)', 'Speed per image', 'All of the above sliced by boxes per image (1, 2, 3\u20136, 7\u201310, 10+) and by weld size'],
      testDesign: `Two filters are tested: drop training images with more than ${cond.max_boxes_train} welds, and drop welds smaller than about 40\u00d740 pixels (area below ${cond.area_thr} of the image). Every model is evaluated on both the raw and the filtered validation and test sets.`,
      highlights: [
        { label: 'Images', value: int(tot('images')), hint: `train ${int(dsplit.train.images)} \u00b7 val ${int(dsplit.valid.images)} \u00b7 test ${int(dsplit.test.images)}` },
        { label: 'Labelled welds', value: int(totalBoxes), hint: 'Bad Weld, Good Weld and Defect boxes' },
        { label: 'Images with a faulty weld', value: pct(prev.train.share, 0), hint: `train \u00b7 val ${pct(prev.valid.share, 0)} \u00b7 test ${pct(prev.test.share, 0)}` },
        { label: 'Model accuracy', value: 'Not trained', hint: 'no performance figures exist yet' },
      ],
      blocks: [
        {
          type: 'table',
          title: 'Dataset by split (as delivered)',
          cols: [
            { key: 'split', label: 'Split' },
            { key: 'img', label: 'Images', num: true },
            { key: 'bad', label: 'Bad Weld', num: true },
            { key: 'good', label: 'Good Weld', num: true },
            { key: 'def', label: 'Defect', num: true },
            { key: 'notok', label: 'Images with a faulty weld', num: true },
          ],
          rows: [['train', 'Train'], ['valid', 'Validation'], ['test', 'Test']].map(([k, label]) => ({
            split: label, img: int(dsplit[k].images), bad: int(dsplit[k].bad), good: int(dsplit[k].good), def: int(dsplit[k].defect),
            notok: `${prev[k].notok} (${pct(prev[k].share, 0)})`,
          })),
          note: 'Counts are welds (boxes) per class. Faulty means Bad Weld or Defect.',
        },
        {
          type: 'table',
          title: 'Images by number of welds in the image (as delivered)',
          cols: [{ key: 'split', label: 'Split' }, ...['1', '2', '3-6', '7-10', '10+'].map((b) => ({ key: b, label: b === '10+' ? '10+ welds' : `${b} weld${b === '1' ? '' : 's'}`, num: true }))],
          rows: [['train', 'Train'], ['valid', 'Validation'], ['test', 'Test']].map(([k, label]) => ({ split: label, ...Object.fromEntries(Object.entries(bpi[k]).map(([b, v]) => [b, int(v)])) })),
        },
        {
          type: 'table',
          title: 'Effect of the two filters',
          cols: [
            { key: 'split', label: 'Split' },
            { key: 'ri', label: 'Images (raw)', num: true },
            { key: 'fi', label: 'Images (filtered)', num: true },
            { key: 'rb', label: 'Welds (raw)', num: true },
            { key: 'fb', label: 'Welds (filtered)', num: true },
          ],
          rows: [['train', 'Train'], ['valid', 'Validation'], ['test', 'Test']].map(([k, label]) => ({
            split: label, ri: int(cond.table.raw[k].images), fi: int(cond.table.filt[k].images), rb: int(cond.table.raw[k].boxes), fb: int(cond.table.filt[k].boxes),
          })),
          note: `On the training set the crowding filter removes ${cond.cond1_images_removed} images and the size filter removes ${cond.cond2_boxes_removed} small welds. The raw training count is 838 here because 1 image that also appeared in validation or test was removed. Class imbalance is ${dec(qa.imbalance.raw, 2)}\u00d7 (largest vs smallest class), above the ${dec(qa.imbalance.threshold, 1)}\u00d7 trigger, so focal loss is used.`,
        },
        {
          type: 'list',
          title: 'Data-quality flags found during analysis',
          items: [
            `Frames from the same ${qa.dataset.source_videos} source videos appear in the training, validation and test sets. Near-duplicate frames will make future test scores look better than they would on genuinely new welds.`,
            `${qa.dataset.leak_images_removed} source image appeared in both training and validation/test; it was removed from training.`,
            `Training images include augmentation copies: on average ${dec(qa.dataset.train_copies_per_original_mean, 2)} files per original, up to ${qa.dataset.train_copies_per_original_max}.`,
            `The test set has only ${dsplit.test.images} images (${prev.test.notok} with a faulty weld), so miss-rate estimates will come with wide confidence intervals.`,
          ],
        },
      ],
      limits: [
        'The model has not been trained. There are no accuracy, miss-rate or review-rate figures, and none should be quoted.',
        'Removing tiny welds from the labels tells the model that small real welds are background. The size-slice results will show how much that costs.',
        'Scores will be optimistic while frames from the same videos sit in both training and test data.',
        'Trained on one public image set, not photographs from your own fabrication line.',
      ],
    },
  ],
};

// ================================================================== Maintenance
const cvf = pm.cv.folds;
const conf = pm.confidence_rows;
const confTotal = conf.HIGH + conf.MEDIUM + conf.LOW;
const lt = pm.lead_time;
const impTop3 = pm.importance_top.slice(0, 3).reduce((a, b) => a + b.importance, 0);
const sensorName = (f) => { const m = f.match(/^s_(\d+)_(rmean|rstd)$/); return m ? `Sensor ${m[1]} \u00b7 ${m[2] === 'rmean' ? '5-cycle average' : '5-cycle variability'}` : f; };

const MAINT_MODULE = {
  id: 'maintenance',
  name: 'Maintenance',
  short: 'Maintenance',
  icon: '\u2699',
  planned: true,
  summary:
    'This ERP does not have a maintenance module yet. The predictive-maintenance model is documented here so it has a home when one is added. It was built and tested on NASA\u2019s public turbofan-engine benchmark, not on your machines.',
  pages: [],
  models: [
    {
      id: 'pm-rul',
      name: 'Predictive maintenance (remaining useful life)',
      tagline: 'How much life is left in this machine, and how likely is it to fail soon?',
      status: 'results',
      dataset: `Benchmark data: ${pm.dataset.name}, ${pm.dataset.engines} engines`,
      what: [
        `Reads a machine\u2019s sensor history and estimates (1) its Remaining Useful Life (RUL) in operating cycles, with an uncertainty spread, and (2) the probability that it will fail within the next ${pm.dataset.fail_window} cycles. Two Random Forests do the work \u2014 one for RUL, one for failure probability \u2014 fed with each sensor\u2019s ${pm.dataset.roll_window}-cycle rolling average and variability.`,
        'The two outputs combine into a risk tier with a suggested action. CRITICAL (failure probability 75%+ or RUL of 15 or fewer): inspect and replace immediately. HIGH (40%+ or 30 or fewer): schedule maintenance in the next window. MODERATE (15%+ or 60 or fewer): plan for the next downtime and order parts. LOW: routine monitoring. These thresholds are illustrative and should be tuned to the cost of an unplanned failure vs unnecessary maintenance.',
      ],
      inputs: [`${21 - pm.dataset.sensors_dropped.length} informative sensor channels (${pm.dataset.sensors_dropped.length} constant channels dropped) and 3 operating settings`, `${pm.dataset.roll_window}-cycle rolling average and variability of each sensor \u2192 ${pm.dataset.n_features} inputs in total`],
      outputs: ['Remaining useful life (cycles) with a spread, and an estimated failure window', `Probability of failure within ${pm.dataset.fail_window} cycles`, 'Risk tier and suggested action', 'Confidence tier: High (spread up to 10 cycles), Medium (up to 20), Low (above 20)', 'Top contributing sensors'],
      howTested: 'Engines are split by engine, never by row (5-fold group cross-validation), so cycles of one engine never sit in both training and validation. Alarm timing was then checked on the 100 held-out NASA test engines.',
      highlights: [
        { label: 'RUL error (5-fold MAE)', value: `${dec(pm.cv.mae_mean)} cycles`, hint: `\u00b1 ${dec(pm.cv.mae_sd)} \u00b7 R\u00b2 ${dec(pm.cv.r2_mean, 2)}` },
        { label: `Failure within ${pm.dataset.fail_window} cycles: AUC`, value: dec(pm.single_fold.auc, 3), hint: `Brier ${dec(pm.single_fold.brier, 3)} \u00b7 one fold, ${pm.split.val_engines} engines` },
        { label: 'Median warning lead time', value: `${dec(lt.median)} cycles`, hint: `${lt.alarmed} of ${lt.of} test engines alarmed` },
        { label: 'High-confidence predictions', value: pct(conf.HIGH / confTotal, 0), hint: `${int(conf.HIGH)} of ${int(confTotal)} validation rows` },
      ],
      blocks: [
        {
          type: 'bars',
          title: 'What drives the prediction: top 10 inputs by importance',
          rows: pm.importance_top.map((f) => ({ label: sensorName(f.feature), value: f.importance, display: pct(f.importance, 1), tone: 'accent' })),
          note: `Sensors 4, 11 and 9 carry ${pct(impTop3, 0)} of the total. Importance shows which signals the model relies on. It does not prove they cause the failure.`,
        },
        {
          type: 'table',
          title: 'RUL accuracy across the 5 validation folds',
          cols: [{ key: 'f', label: 'Fold', num: true }, { key: 'mae', label: 'MAE (cycles)', num: true }, { key: 'rmse', label: 'RMSE (cycles)', num: true }, { key: 'r2', label: 'R\u00b2', num: true }],
          rows: [
            ...cvf.map((c) => ({ f: c.fold, mae: dec(c.mae, 2), rmse: dec(c.rmse, 2), r2: dec(c.r2, 3) })),
            { f: 'Mean', mae: `${dec(pm.cv.mae_mean, 2)} \u00b1 ${dec(pm.cv.mae_sd, 2)}`, rmse: dec(pm.cv.rmse_mean, 2), r2: `${dec(pm.cv.r2_mean, 3)} \u00b1 ${dec(pm.cv.r2_sd, 3)}`, _hl: true },
          ],
          note: `Measured on every cycle of the training engines, with RUL capped at ${pm.dataset.rul_cap} cycles. This is not the same test as the official NASA leaderboard.`,
        },
        {
          type: 'table',
          title: 'How early would the alarm have fired? (100 held-out test engines)',
          cols: [{ key: 'm', label: 'Measure' }, { key: 'v', label: 'Value', num: true }],
          rows: [
            { m: 'Engines that raised an alarm (probability 50%+)', v: `${lt.alarmed} of ${lt.of}` },
            { m: 'Median remaining life at first alarm', v: `${dec(lt.median)} cycles` },
            { m: 'Mean remaining life at first alarm', v: `${dec(lt.mean)} cycles` },
            { m: 'Earliest / shortest warning', v: `${dec(lt.max, 0)} / ${dec(lt.min, 0)} cycles` },
          ],
          note: 'Each NASA test series stops before failure, so many engines were still healthy when recording ended and should not alarm.',
        },
        {
          type: 'bars',
          title: 'Confidence tiers on validation predictions',
          rows: [
            { label: 'High confidence', value: conf.HIGH, display: `${int(conf.HIGH)} (${pct(conf.HIGH / confTotal, 0)})`, tone: 'accent' },
            { label: 'Medium confidence', value: conf.MEDIUM, display: `${int(conf.MEDIUM)} (${pct(conf.MEDIUM / confTotal, 0)})`, tone: 'warning' },
            { label: 'Low confidence', value: conf.LOW, display: `${int(conf.LOW)} (${pct(conf.LOW / confTotal, 1)})`, tone: 'danger' },
          ],
          note: 'Confidence comes from how much the trees in the forest disagree. It is a useful signal, but it is not a statistically calibrated interval.',
        },
        {
          type: 'table',
          title: 'Dataset',
          cols: [{ key: 'm', label: 'Item' }, { key: 'v', label: 'Value', num: true }],
          rows: [
            { m: 'Training engines / rows', v: `${pm.dataset.engines} / ${int(pm.dataset.train_rows)}` },
            { m: 'Test engines / rows', v: `${pm.dataset.engines} / ${int(pm.dataset.test_rows)}` },
            { m: 'Engine life (min / median / mean / max)', v: `${dec(pm.dataset.life_min, 0)} / ${dec(pm.dataset.life_median, 0)} / ${dec(pm.dataset.life_mean, 0)} / ${dec(pm.dataset.life_max, 0)} cycles` },
            { m: 'Fault type / operating condition', v: 'One (compressor degradation) / one' },
          ],
        },
      ],
      limits: [
        'This is simulated benchmark data, not your equipment. To use it on real machines it must be retrained on your own sensor histories and recorded failures.',
        'The benchmark has a single fault mode under one operating condition. The model predicts when a machine will fail, not which component will fail.',
        `RUL is capped at ${pm.dataset.rul_cap} cycles, because healthy engines all look alike. It cannot say \u201cmore than ${pm.dataset.rul_cap} cycles\u201d in finer detail.`,
        `Failure-probability figures (AUC, Brier) come from a single validation fold of ${pm.split.val_engines} engines. RUL error on the ${pm.dataset.engines} official test engines was not computed, so results cannot be compared with published benchmarks.`,
        `Only ${lt.alarmed} of ${lt.of} test engines alarmed. The notebook did not check how many engines that truly ended within ${pm.dataset.fail_window} cycles were among them, so the miss rate is unknown. Alarms fired between ${dec(lt.min, 0)} and ${dec(lt.max, 0)} cycles before failure.`,
        'Risk-tier thresholds are illustrative, not tuned to a real cost of downtime.',
      ],
    },
  ],
};

export const MODULES = [WMS_MODULE, PROC_MODULE, QUALITY_MODULE, MAINT_MODULE];

// ================================================================== Overview
export const OVERVIEW = {
  intro:
    'This page explains the analytics models developed for this ERP: what each one does, how it was tested, and what its numbers mean. Models are grouped by ERP module. Use the tabs above to open a module.',
  notice: {
    title: 'Read this first',
    body: 'Every model here was developed and tested offline on a sample or public dataset. None is connected to live ERP data yet. The statistics describe how each model did on its own test data \u2014 not on your warehouse, suppliers or plant \u2014 and they will change when a model is retrained on your records.',
  },
  coverage: [
    { module: 'wms', trainedOn: `Sample hospital-drug sales, ${wms.run.n_skus} SKUs, ${wms.run.train_period.slice(0, 4)}\u2013${wms.run.holdout_period.slice(0, 4)} (${wms.run.currency})`, stats: 'Accuracy vs plan, cost simulation, stress tests, buffer calibration, SKU reliability grades, monitoring' },
    { module: 'procurement', trainedOn: 'Public Kaggle procurement KPI dataset (not included)', stats: 'None yet. Pipelines are complete; they need the data and a run.' },
    { module: 'quality', trainedOn: `Public welding-defect images, ${int(tot('images'))} images`, stats: 'Dataset statistics only. The model is not trained.' },
    { module: 'maintenance', trainedOn: `NASA C-MAPSS turbofan benchmark, ${pm.dataset.engines} engines`, stats: 'RUL error, failure-probability accuracy, sensor drivers, warning lead time, confidence tiers' },
  ],
};

export const GLOSSARY = [
  ['WAPE', 'Weighted absolute percentage error: total absolute forecast error divided by total actual demand. Lower is better. A WAPE of 7% means the forecast is off by about 7 units for every 100 actually used.'],
  ['Bias', 'Whether a forecast runs systematically low (negative) or high (positive) compared with what actually happened.'],
  ['MAPE / sMAPE', 'Average percentage error. sMAPE is a version that treats over- and under-forecasts more evenly.'],
  ['MAE / RMSE', 'Average size of the error in the original unit (MAE), or a version that punishes large misses more (RMSE). Lower is better.'],
  ['R\u00b2', 'Share of the variation in the outcome that the model explains. 1 is perfect; 0 is no better than guessing the average.'],
  ['MASE', 'Forecast error relative to a naive forecast. Below 1 means the model beats the naive approach.'],
  ['Pinball loss', 'Error measure for percentile forecasts such as P50 and P90. It penalises being on the wrong side of the percentile.'],
  ['Coverage', 'How often the actual value falls inside a predicted range or under a predicted percentile. A 90% range should cover about 90% of outcomes.'],
  ['Fill rate', 'Share of demanded units that were actually supplied from stock.'],
  ['Service level', 'Target probability of not running out of stock during the ordering lead time.'],
  ['Stock-out product-months', 'Share of product-months in which a SKU ran out of stock at some point.'],
  ['Order-up-to level', 'The stock position a SKU is topped up to whenever an order is placed: expected demand over the protection period plus a safety buffer.'],
  ['ABC class', 'A ranking of SKUs by annual value. A is the highest-value group, C the lowest.'],
  ['AUC / ROC-AUC', 'How well a model ranks risky cases above safe ones. 0.5 is a coin flip; 1.0 is perfect ranking.'],
  ['PR-AUC', 'Like AUC but focused on the rare cases (for example breaches). Better than AUC when the events you care about are uncommon.'],
  ['Precision / recall', 'Of the items flagged, the share that were truly bad (precision); of all truly bad items, the share that were flagged (recall).'],
  ['Brier score', 'Accuracy of predicted probabilities. Lower is better; 0 is perfect.'],
  ['Calibration / ECE', 'Whether a predicted 70% risk really happens about 70% of the time. ECE (expected calibration error) is the average gap.'],
  ['Spearman correlation', 'How well two rankings agree, from \u22121 to +1. Used to check whether suppliers scored as riskier really were riskier.'],
  ['mAP@0.5', 'Overall accuracy of an image detector, averaged across classes. A detected box counts as right if it overlaps the true box by at least 50%.'],
  ['RUL', 'Remaining useful life: how many operating cycles a machine has left before it fails.'],
  ['Hold-out', 'Data set aside and never used to build or tune a model, kept for a final unbiased check.'],
  ['Censoring', 'When recorded data is capped by something other than true demand. For example, sales cannot exceed stock, so a stock-out hides real demand.'],
];
