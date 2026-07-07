# ⛽ Fuel Station Management System — Odoo 15

A complete, production-ready Fuel Station Management System built as a custom Odoo 15 module from scratch. Every line of code is written manually with full understanding of the Odoo framework, Python ORM, XML views, and business logic.

---

## 📌 About This Project

This module manages the complete end-to-end operations of a fuel/petrol station — from fuel procurement and underground tank management, through pump and nozzle operations, employee shift management, meter readings, fuel sales, fleet customer accounts, accounting integration, and a fully functional public website with customer portal.

---

## 🏗️ Business Flow

```
Fuel Types → Tanks → Pumps → Nozzles → Shifts → Sales → Accounting
                                                    ↓
                                              Fleet Customers
                                                    ↓
                                              Website Portal
```

1. **Fuel Types** — Define petrol, diesel, premium fuel with prices
2. **Tanks** — Underground storage tanks holding one fuel type each
3. **Pumps** — Connected to tanks, located across the station
4. **Nozzles** — On each pump, with meters counting total litres dispensed
5. **Shifts** — Employee opens shift, records opening meter readings
6. **Sales** — Closing meter minus opening meter = litres sold per shift
7. **Purchases** — Fuel ordered from suppliers, tank stock updated on delivery
8. **Expenses** — Cash, electricity, salary tracked per shift
9. **Fleet** — Vehicle credit accounts for regular customers
10. **Accounting** — Journal entries auto-generated on sales and purchases
11. **Website** — Public pages with live fuel prices and customer portal

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.8+, Odoo ORM |
| Views | XML (Form, List, Search, Kanban) |
| Reports | QWeb + wkhtmltopdf (PDF) |
| Excel Exports | xlsxwriter |
| Styling | CSS via assets_backend |
| Accounting | Odoo account module integration |
| Website | Odoo website module + QWeb templates |
| Database | PostgreSQL 14 |
| Environment | Docker + docker-compose |

---

## 🗄️ Data Models

| Model | Technical Name | Purpose |
|---|---|---|
| Fuel Type | `fuel.type` | Petrol, diesel, premium — price per litre |
| Tank | `fuel.tank` | Underground storage with capacity and stock |
| Pump | `fuel.pump` | Pump units connected to tanks |
| Nozzle | `fuel.nozzle` | Nozzles with meter readings |
| Shift | `fuel.shift` | Employee shifts with opening/closing meters |
| Sale | `fuel.sale` | Sales calculated from meter differences |
| Purchase | `fuel.purchase` | Fuel procurement from suppliers |
| Expense | `fuel.expense` | Per-shift expense tracking |
| Fleet | `fuel.fleet` | Fleet vehicle credit accounts |

---

## 📊 Reports

### PDF Reports
- **Shift Summary** — Sales, cash, and expenses per shift
- **Daily Sales Report** — Revenue breakdown by fuel type
- **Tank Level Report** — Current stock across all tanks
- **Customer Statement** — Fleet customer credit and usage history

### Excel Exports
- Sales data filterable by date and shift
- All shifts with reconciliation summary
- Procurement records and delivery history
- Historical tank stock levels

---

## 🌐 Website Pages

| Page | Description |
|---|---|
| Home | Station overview with live fuel prices |
| About Us | Company info and branch details |
| Fuel Prices | Live prices from the Odoo backend |
| Branch Locator | Map of all station locations |
| Fleet Registration | Online fleet vehicle registration form |
| Contact Us | Contact form with email notification |
| Customer Portal | Login — view account, credit, and fuel history |
| Services | Car wash, oil change, and other station services |
