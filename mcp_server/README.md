# Campus Customs MCP server

An MCP server (built with [FastMCP](https://github.com/jlowin/fastmcp)) that
gives an agent read access to the Campus Customs shop database, so it can work
the open tickets from real data instead of guessing.

## Database

- **Uses:** `../data/campus_customs_new.db` — the working copy.
- **Never touches:** `../data/campus_customs.db` — the pristine original, kept
  so the scenario can be reset at any time:

  ```bash
  cp ../data/campus_customs.db ../data/campus_customs_new.db
  ```

Every tool opens the working copy read-only (`mode=ro`). Nothing in this server
writes yet; write tools come in a later step.

## Tools

Twelve tools. Read tools open the database read-only; write tools open it
read/write, require `approved_by`, and refuse unsafe changes.

### Read tools

| Tool | Table | What it answers |
|---|---|---|
| `get_today` | `desk` | The shop's current date — the basis for every deadline. |
| `get_cash_balance` | `cash_accounts` | How much cash is actually there. |
| `list_tickets` | `tickets` | The work queue, with the links to the other tables. |
| `check_inventory` | `inventory` | Units on hand per SKU **and** size, and whether a quantity can be filled. |
| `get_pricing` | `pricing` | Unit cost and list price, and how a proposed discount scores against cost. |
| `list_invoices` | `invoices` (+ `desk`) | What the shop owes, to whom, and how overdue it is. |
| `get_lease_due` | `leases` (+ `desk`) | Rent amount, next due date, days away. |
| `list_vendors` | `vendors` | Suppliers, specialities and lead times — the basis for a restock date. |

### Write tools

| Tool | Table(s) | What it does | Refuses to |
|---|---|---|---|
| `record_payment` | `payments`, `cash_accounts`, `invoices` | Writes a ledger row, lowers the balance, marks an invoice paid — one transaction. | Spend more than the balance, pay a non-positive amount, or pay an invoice twice. |
| `adjust_inventory` | `inventory` | Moves stock by a delta: negative for a sale, positive for a restock received. | Take stock below zero. |
| `update_price` | `pricing` | Changes a SKU's list price (all sizes — pricing has no size column). | Set a price at or below `unit_cost`. |
| `update_ticket` | `tickets` | Sets status and **appends** a note with the author's name. | Accept a status outside open / in_progress / waiting_approval / resolved / closed, or overwrite existing notes. |

Every write tool requires a non-empty `approved_by`; an unsigned write is
rejected outright.

### Tool details

- `check_inventory(sku, size=None, qty_needed=None)` — with `size` it reports
  that one size; with `qty_needed` it adds `can_fulfill` and `shortfall`.
- `get_lease_due(lease_id=None)` — `days_until_due` is counted from
  `desk.date_today`, not the system clock. Negative means overdue.
- `get_pricing(sku=None, proposed_unit_price=None, qty=None)` — `unit_cost` is
  the discount floor; add `qty` for order revenue, cost and margin. Returns
  `applies_to_all_sizes` as a reminder that a price change is SKU-wide.
- `record_payment(kind, amount, approved_by, ref_id=None, account="checking", memo=None)`
  — `kind` is `"invoice"` (then `ref_id` is an invoice id, which gets marked
  paid) or `"rent"` (then `ref_id` is a lease id).

## Running it

Not required yet — Problem 3 only builds the server. When you do need it:

Dependencies come from the project venv at `../.venv` (see the root
`README.md`). From the project root:

```bash
.venv/bin/python mcp_server/server.py          # stdio
.venv/bin/python mcp_server/server.py --http   # http://127.0.0.1:8002/mcp
```
