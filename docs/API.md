# API Reference

> Every HTTP endpoint exposed by the backend, grouped by domain and then by subdomain
> (matching the `app/<domain>/<subdomain>/api.py` layout — see
> [`HIGH_LEVEL_ARCHITECTURE.md`](./HIGH_LEVEL_ARCHITECTURE.md) §3 and §8). All paths are
> relative to the API prefix (`/api/v1`, see `app/config.py`). For what each endpoint's
> handler actually validates/does, see the matching
> [module low-level doc](./modules/).

**117 endpoints** across 17 resources.

## Contents

- [Master Data](#master-data)
  - [Units](#units)
  - [Manufacturers](#manufacturers)
  - [Products](#products)
- [Procurement](#procurement)
  - [Suppliers](#suppliers)
  - [Purchase Requisitions](#purchase-requisitions)
  - [RFQs](#rfqs)
  - [Vendor Quotations](#vendor-quotations)
  - [Purchase Orders](#purchase-orders)
  - [Vendor Invoices](#vendor-invoices)
  - [Procurement Dashboard](#procurement-dashboard)
- [WMS](#wms)
  - [Warehouse Hierarchy](#warehouse-hierarchy)
  - [Inventory](#inventory)
  - [Goods Receipts](#goods-receipts)
- [Quality](#quality)
  - [Quality Inspections](#quality-inspections)
- [Platform](#platform)
  - [Search & Utilities](#search-utilities)
  - [Transaction Logs](#transaction-logs)
  - [Health](#health)

## Master Data

### Units
*`app/master_data/unit/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/units` | List Units |
| `POST` | `/api/v1/units` | Create Unit |
| `GET` | `/api/v1/units/{unit_id}` | Get Unit |
| `PUT` | `/api/v1/units/{unit_id}` | Update Unit |
| `DELETE` | `/api/v1/units/{unit_id}` | Delete Unit |
| `POST` | `/api/v1/units/{unit_id}/activate` | Activate Unit |
| `POST` | `/api/v1/units/{unit_id}/deactivate` | Deactivate Unit |

### Manufacturers
*`app/master_data/manufacturer/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/manufacturers` | List Manufacturers |
| `POST` | `/api/v1/manufacturers` | Create Manufacturer |
| `GET` | `/api/v1/manufacturers/{manufacturer_id}` | Get Manufacturer |
| `PUT` | `/api/v1/manufacturers/{manufacturer_id}` | Update Manufacturer |
| `DELETE` | `/api/v1/manufacturers/{manufacturer_id}` | Delete Manufacturer |
| `POST` | `/api/v1/manufacturers/{manufacturer_id}/activate` | Activate Manufacturer |
| `POST` | `/api/v1/manufacturers/{manufacturer_id}/deactivate` | Deactivate Manufacturer |

### Products
*`app/master_data/product/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/products` | List Products |
| `POST` | `/api/v1/products` | Create Product |
| `GET` | `/api/v1/products/{product_id}` | Get Product |
| `PUT` | `/api/v1/products/{product_id}` | Update Product |
| `DELETE` | `/api/v1/products/{product_id}` | Delete Product |
| `POST` | `/api/v1/products/{product_id}/activate` | Activate Product |
| `POST` | `/api/v1/products/{product_id}/change-unit/{unit_id}` | Change Unit |
| `POST` | `/api/v1/products/{product_id}/deactivate` | Deactivate Product |

## Procurement

### Suppliers
*`app/procurement/supplier/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/suppliers` | List Suppliers |
| `POST` | `/api/v1/suppliers` | Create Supplier |
| `GET` | `/api/v1/suppliers/{supplier_id}` | Get Supplier |
| `PUT` | `/api/v1/suppliers/{supplier_id}` | Update Supplier |
| `DELETE` | `/api/v1/suppliers/{supplier_id}` | Delete Supplier |
| `POST` | `/api/v1/suppliers/{supplier_id}/activate` | Activate Supplier |
| `POST` | `/api/v1/suppliers/{supplier_id}/deactivate` | Deactivate Supplier |

### Purchase Requisitions
*`app/procurement/requisition/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/purchase-requisitions` | List Prs |
| `POST` | `/api/v1/purchase-requisitions` | Create Pr |
| `GET` | `/api/v1/purchase-requisitions/{pr_id}` | Get Pr |
| `PUT` | `/api/v1/purchase-requisitions/{pr_id}` | Update Pr |
| `DELETE` | `/api/v1/purchase-requisitions/{pr_id}` | Delete Pr |
| `POST` | `/api/v1/purchase-requisitions/{pr_id}/approve` | Approve Pr |
| `POST` | `/api/v1/purchase-requisitions/{pr_id}/items` | Add Item |
| `DELETE` | `/api/v1/purchase-requisitions/{pr_id}/items/{item_id}` | Remove Item |
| `POST` | `/api/v1/purchase-requisitions/{pr_id}/reject` | Reject Pr |
| `POST` | `/api/v1/purchase-requisitions/{pr_id}/submit` | Submit Pr |

### RFQs
*`app/procurement/rfq/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/rfqs` | List Rfqs |
| `POST` | `/api/v1/rfqs` | Create Rfq |
| `GET` | `/api/v1/rfqs/{rfq_id}` | Get Rfq |
| `POST` | `/api/v1/rfqs/{rfq_id}/close` | Close Rfq |
| `POST` | `/api/v1/rfqs/{rfq_id}/send` | Send Rfq |

### Vendor Quotations
*`app/procurement/vendor_quotation/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/quotations` | List Quotations |
| `POST` | `/api/v1/quotations` | Create Quotation |
| `POST` | `/api/v1/quotations/ingest` | Ingest Quotation |
| `GET` | `/api/v1/quotations/{quotation_id}` | Get Quotation |
| `PUT` | `/api/v1/quotations/{quotation_id}/items/{item_id}` | Update Quotation Item |
| `POST` | `/api/v1/quotations/{quotation_id}/reject` | Reject Quotation |
| `POST` | `/api/v1/quotations/{quotation_id}/review` | Review Quotation |
| `POST` | `/api/v1/quotations/{quotation_id}/select` | Select Quotation |
| `GET` | `/api/v1/rfqs/{rfq_id}/quotations` | List Quotations For Rfq |
| `POST` | `/api/v1/rfqs/{rfq_id}/quotations` | Create Quotation For Rfq |

### Purchase Orders
*`app/procurement/purchase_order/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/purchase-orders` | List Pos |
| `POST` | `/api/v1/purchase-orders` | Create Po |
| `GET` | `/api/v1/purchase-orders/{po_id}` | Get Po |
| `PUT` | `/api/v1/purchase-orders/{po_id}` | Update Po |
| `POST` | `/api/v1/purchase-orders/{po_id}/cancel` | Cancel Po |
| `POST` | `/api/v1/purchase-orders/{po_id}/confirm` | Confirm Po |
| `POST` | `/api/v1/purchase-orders/{po_id}/send` | Send Po |

### Vendor Invoices
*`app/procurement/vendor_invoice/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/vendor-invoices` | List Invoices |
| `POST` | `/api/v1/vendor-invoices` | Create Invoice |
| `POST` | `/api/v1/vendor-invoices/ingest` | Ingest Invoice |
| `GET` | `/api/v1/vendor-invoices/{invoice_id}` | Get Invoice |
| `PUT` | `/api/v1/vendor-invoices/{invoice_id}` | Update Invoice |
| `POST` | `/api/v1/vendor-invoices/{invoice_id}/approve-payment` | Approve Invoice Payment |
| `PUT` | `/api/v1/vendor-invoices/{invoice_id}/items/{item_id}` | Update Invoice Item |
| `POST` | `/api/v1/vendor-invoices/{invoice_id}/mark-paid` | Mark Invoice Paid |
| `POST` | `/api/v1/vendor-invoices/{invoice_id}/match` | Match Invoice |

### Procurement Dashboard
*`app/procurement/dashboard/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/procurement/kpis` | Get Procurement Kpis |
| `GET` | `/api/v1/procurement/reorder-suggestions` | Get Reorder Suggestions |

## WMS

### Warehouse Hierarchy
*`app/wms/warehouse_structure/api.py`*

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/bins` | Create Bin |
| `GET` | `/api/v1/bins/{bin_id}` | Get Bin |
| `DELETE` | `/api/v1/bins/{bin_id}` | Delete Bin |
| `GET` | `/api/v1/locations` | List Locations |
| `POST` | `/api/v1/locations` | Create Location |
| `GET` | `/api/v1/locations/{location_id}` | Get Location |
| `PUT` | `/api/v1/locations/{location_id}` | Update Location |
| `DELETE` | `/api/v1/locations/{location_id}` | Delete Location |
| `POST` | `/api/v1/racks` | Create Rack |
| `GET` | `/api/v1/racks/{rack_id}` | Get Rack |
| `DELETE` | `/api/v1/racks/{rack_id}` | Delete Rack |
| `POST` | `/api/v1/shelves` | Create Shelf |
| `GET` | `/api/v1/shelves/{shelf_id}` | Get Shelf |
| `DELETE` | `/api/v1/shelves/{shelf_id}` | Delete Shelf |
| `GET` | `/api/v1/warehouses` | List Warehouses |
| `POST` | `/api/v1/warehouses` | Create Warehouse |
| `GET` | `/api/v1/warehouses/{warehouse_id}` | Get Warehouse |
| `PUT` | `/api/v1/warehouses/{warehouse_id}` | Update Warehouse |
| `DELETE` | `/api/v1/warehouses/{warehouse_id}` | Delete Warehouse |
| `GET` | `/api/v1/warehouses/{warehouse_id}/racks` | List Warehouse Racks |

### Inventory
*`app/wms/inventory/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/inventory` | List Inventory |
| `POST` | `/api/v1/inventory` | Create Inventory |
| `GET` | `/api/v1/inventory/product/{product_id}/available` | Get Available Stock |
| `GET` | `/api/v1/inventory/product/{product_id}/total` | Get Total Stock |
| `GET` | `/api/v1/inventory/{inventory_id}` | Get Inventory |
| `PUT` | `/api/v1/inventory/{inventory_id}` | Update Inventory |
| `DELETE` | `/api/v1/inventory/{inventory_id}` | Delete Inventory |
| `POST` | `/api/v1/inventory/{inventory_id}/adjust` | Adjust Quantity |
| `POST` | `/api/v1/inventory/{inventory_id}/issue` | Issue Stock |
| `POST` | `/api/v1/inventory/{inventory_id}/move` | Move Stock |
| `POST` | `/api/v1/inventory/{inventory_id}/release` | Release Stock |
| `POST` | `/api/v1/inventory/{inventory_id}/reserve` | Reserve Stock |
| `POST` | `/api/v1/inventory/{inventory_id}/status` | Change Status |

### Goods Receipts
*`app/wms/goods_receipt/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/goods-receipts` | List Grns |
| `POST` | `/api/v1/goods-receipts` | Create Grn |
| `GET` | `/api/v1/goods-receipts/{grn_id}` | Get Grn |
| `POST` | `/api/v1/goods-receipts/{grn_id}/close` | Close Grn |

## Quality

### Quality Inspections
*`app/quality/inspection/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/quality-inspections` | List Qcs |
| `POST` | `/api/v1/quality-inspections` | Create Qc |
| `GET` | `/api/v1/quality-inspections/{qc_id}` | Get Qc |
| `POST` | `/api/v1/quality-inspections/{qc_id}/approve-deviation` | Approve Deviation |

## Platform

### Search & Utilities
*`app/platform/search/api.py`*

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/search/check-availability` | Check Availability |
| `POST` | `/api/v1/search/seed` | Seed Database |

### Transaction Logs
*`app/platform/logs/api.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/logs` | List Transaction Logs |

### Health
*`app/main.py`*

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health Check |
