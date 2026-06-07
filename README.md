## Agriculture (Syova Seeds Field Operations)

A Frappe/ERPNext app for managing seed-company field operations: field promoters,
farmers, demo gardens, material requests, a per-promoter stock ledger, field
order collection, KPI targets, scheduled alerts, and a SAP Business One
integration. SAP B1 remains the ERP system of record — field orders, payments and
inventory movements collected on the ground are pushed to SAP B1, and master data
(Items, Customers, Price Lists) is pulled back from it.

It builds on the original ERPNext Agriculture domain (crops, diseases, fertilizers,
soil/water/plant/weather analysis) and extends it with the field-operations layer.

### Key components

- **Field Promoter / Farmer** — field staff and the farmers they serve, with
  row-level security so promoters see only their own (and their team's) records.
- **Demo Garden** lifecycle — Material Request → Issue → Receipt → Planting →
  Input Application → Monitoring → Field Day, each posting to the **Promoter Stock
  Ledger**.
- **Order Collection** — field orders and payments, auto-pushed to SAP B1.
- **Reports** — Promoter Performance, Demo Garden Status, Materials Issued vs
  Applied, Farmer Visit History.
- **SAP B1 integration** (`agriculture/agriculture/sap_integration.py`) — Service
  Layer push (Orders, Payments, Stock Transfer Requests, Goods Issues/Receipts)
  and master-data pull. Configure it under **Agriculture Settings**.

### Installation

```sh
$ bench get-app agriculture <repo-url>
$ bench --site <your-site> install-app agriculture
```

Requires the `erpnext` app. After install, open **Agriculture Settings** to
configure alert thresholds, KPI targets and (optionally) SAP B1 connection details.

### License

GNU GPL v3. See [license.txt](license.txt).
