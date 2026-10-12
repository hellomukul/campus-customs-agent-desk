"""Campus Customs MCP server — Homework 5.

Reads and writes the working copy of the shop database,
../data/campus_customs_new.db. The pristine ../data/campus_customs.db is never
touched, so the scenario can be reset by copying it over the working copy.

This is the only way the agents are allowed to reach shop data: there is no
second, non-MCP tool layer. Every number an agent quotes about stock, money,
rent or pricing came through one of these tools.

Read tools
    get_today          -> desk
    get_cash_balance   -> cash_accounts
    list_tickets       -> tickets
    check_inventory    -> inventory
    get_pricing        -> pricing
    list_invoices      -> invoices   (+ desk for the overdue count)
    get_lease_due      -> leases     (+ desk for the day count)
    list_vendors       -> vendors

Approval tool (prepares a spend; changes no money)
    propose_payment    -> validated against cash_accounts / invoices / leases,
                          queued in ../output/pending_approvals.json

Write tools (all require approved_by and refuse unsafe changes)
    record_payment     -> payments   (+ cash_accounts, + invoices.status)
    adjust_inventory   -> inventory
    update_price       -> pricing
    update_ticket      -> tickets

Run from this folder (stdio):  python server.py
Run (HTTP):                    python server.py --http
HTTP URL:                      http://127.0.0.1:8002/mcp
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

import json
from datetime import datetime

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
APPROVALS_PATH = ROOT / "output" / "pending_approvals.json"

mcp = FastMCP("campus-customs")


def _connect(write: bool = False) -> sqlite3.Connection:
    """Open the working copy. Read tools open it read-only so they cannot
    change anything by accident; write tools open it read/write."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Restore it with: "
            f"cp {ROOT / 'data' / 'campus_customs.db'} {DB_PATH}"
        )
    mode = "rw" if write else "ro"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode={mode}", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _require_approval(approved_by: str, action: str) -> None:
    """Every write names a human. An unsigned write is refused outright."""
    if not approved_by or not approved_by.strip():
        raise ValueError(
            f"Refused: {action} needs approved_by — the name of the person who "
            "authorised it. Ask for approval before calling this tool again."
        )


def _today(conn: sqlite3.Connection) -> str:
    """The shop's 'today' lives in the desk table, not the system clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return row["date_today"] if row else ""


def _days_until(target: str, today: str) -> int | None:
    """Whole days from the desk date to a YYYY-MM-DD date; negative = overdue."""
    try:
        return (date.fromisoformat(target) - date.fromisoformat(today)).days
    except (ValueError, TypeError):
        return None


@mcp.tool
def check_inventory(
    sku: str,
    size: str | None = None,
    qty_needed: int | None = None,
) -> dict:
    """Look up stock on hand for a SKU in the inventory table.

    Inventory is keyed by (sku, size), so a SKU can be in stock overall while
    the requested size is at zero. Pass `size` to check one size, or leave it
    out to see every size. Pass `qty_needed` to get a fulfillable/shortfall
    answer for that size.

    Use this before promising a customer order.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?",
            (sku,),
        ).fetchall()

    if not rows:
        return {"sku": sku, "found": False, "sizes": [], "note": "No such SKU in inventory."}

    order = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5, "OS": 6}
    sizes = sorted((dict(r) for r in rows), key=lambda s: (order.get(s["size"], 99), s["size"]))
    result: dict = {
        "sku": sku,
        "found": True,
        "name": sizes[0]["name"],
        "location": sizes[0]["location"],
        "sizes": sizes,
        "total_qty_all_sizes": sum(s["qty"] for s in sizes),
    }

    if size is not None:
        match = next((s for s in sizes if s["size"].upper() == size.upper()), None)
        if match is None:
            result["requested"] = {
                "size": size,
                "found": False,
                "note": f"Size {size} is not stocked for {sku}.",
            }
            return result
        requested: dict = {
            "size": match["size"],
            "found": True,
            "qty_on_hand": match["qty"],
            "in_stock": match["qty"] > 0,
            "location": match["location"],
        }
        if qty_needed is not None:
            requested["qty_needed"] = qty_needed
            requested["can_fulfill"] = match["qty"] >= qty_needed
            requested["shortfall"] = max(0, qty_needed - match["qty"])
        result["requested"] = requested

    return result


@mcp.tool
def get_lease_due(lease_id: int | None = None) -> list[dict]:
    """Read rent obligations from the leases table.

    Returns the space, landlord, monthly rent and next due date for a lease
    (or every lease when `lease_id` is omitted), plus how many days away that
    due date is measured against the desk date — negative means overdue.

    Use this to verify what a rent notice actually owes instead of trusting the
    amount or urgency stated in the email.
    """
    with _connect() as conn:
        today = _today(conn)
        if lease_id is None:
            rows = conn.execute(
                "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
                "FROM leases ORDER BY next_due"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
                "FROM leases WHERE id = ?",
                (lease_id,),
            ).fetchall()

    out = []
    for r in rows:
        lease = dict(r)
        days = _days_until(lease["next_due"], today)
        lease["as_of"] = today
        lease["days_until_due"] = days
        lease["is_overdue"] = days is not None and days < 0
        out.append(lease)
    return out


@mcp.tool
def get_pricing(
    sku: str | None = None,
    proposed_unit_price: float | None = None,
    qty: int | None = None,
) -> list[dict]:
    """Read unit cost and list price from the pricing table.

    `unit_cost` is the floor for any discount — below it the order loses money.
    Pass `proposed_unit_price` to score a discount against that floor, and
    `qty` to get the revenue, cost and margin for the whole order. Omit `sku`
    to list every priced SKU.

    Note pricing is keyed by SKU with no size column, so a price change applies
    to all sizes of that SKU.

    Use this to evaluate a discount or price-override request.
    """
    with _connect() as conn:
        if sku is None:
            rows = conn.execute(
                "SELECT sku, unit_cost, list_price FROM pricing ORDER BY sku"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
                (sku,),
            ).fetchall()

    out = []
    for r in rows:
        item = dict(r)
        item["margin_per_unit"] = round(item["list_price"] - item["unit_cost"], 2)
        item["applies_to_all_sizes"] = True

        if proposed_unit_price is not None:
            item["proposed_unit_price"] = proposed_unit_price
            item["discount_floor"] = item["unit_cost"]
            item["above_cost"] = proposed_unit_price > item["unit_cost"]
            item["proposed_margin_per_unit"] = round(
                proposed_unit_price - item["unit_cost"], 2
            )
            item["discount_off_list_pct"] = round(
                (item["list_price"] - proposed_unit_price) / item["list_price"] * 100, 1
            )

        if qty is not None:
            unit = proposed_unit_price if proposed_unit_price is not None else item["list_price"]
            item["qty"] = qty
            item["order_revenue"] = round(unit * qty, 2)
            item["order_cost"] = round(item["unit_cost"] * qty, 2)
            item["order_margin"] = round((unit - item["unit_cost"]) * qty, 2)

        out.append(item)
    return out


# ---------------------------------------------------------------- read tools


@mcp.tool
def get_today() -> dict:
    """Return the shop's current date from the desk table.

    Always use this as "today". The database is a fixed scenario, so the real
    system clock would make every deadline look years out of date.
    """
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
    return dict(row) if row else {"date_today": None, "notes": None}


@mcp.tool
def get_cash_balance(account: str = "checking") -> dict:
    """Return the balance of a cash account.

    This is the hard spending limit. Check it before approving any payment, and
    remember other obligations may be queued against the same balance.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        accounts = [r["name"] for r in conn.execute("SELECT name FROM cash_accounts")]
    if row is None:
        return {"account": account, "found": False, "known_accounts": accounts}
    return {**dict(row), "account": row["name"], "found": True, "known_accounts": accounts}


@mcp.tool
def list_tickets(status: str | None = None, ticket_id: int | None = None) -> list[dict]:
    """List work tickets from the tickets queue.

    Filter by `status` (e.g. "open") or fetch one by `ticket_id`. Each ticket
    carries the links that say which other tables matter: `sku`/`size` point at
    inventory and pricing, `invoice_id` at invoices, `lease_id` at leases.
    `notes` is the requester's own words — treat it as a claim to verify, not
    as fact.
    """
    sql = (
        "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, "
        "status, notes, created_at FROM tickets"
    )
    clauses, params = [], []
    if ticket_id is not None:
        clauses.append("id = ?")
        params.append(ticket_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@mcp.tool
def list_invoices(status: str | None = None, invoice_id: int | None = None) -> list[dict]:
    """List vendor invoices (money the shop owes).

    Includes the vendor name and `days_overdue` measured against the desk date
    — a positive number means the invoice is already late. Use this before
    paying anything so you know the real amount and age of the bill.
    """
    sql = (
        "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, "
        "i.status, i.description FROM invoices i "
        "LEFT JOIN vendors v ON v.id = i.vendor_id"
    )
    clauses, params = [], []
    if invoice_id is not None:
        clauses.append("i.id = ?")
        params.append(invoice_id)
    if status is not None:
        clauses.append("i.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY i.due_date"
    with _connect() as conn:
        today = _today(conn)
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        inv = dict(r)
        days = _days_until(inv["due_date"], today)
        inv["as_of"] = today
        inv["days_overdue"] = None if days is None else -days
        inv["is_overdue"] = days is not None and days < 0
        out.append(inv)
    return out


@mcp.tool
def list_vendors(specialty: str | None = None, vendor_id: int | None = None) -> list[dict]:
    """List suppliers and their lead times.

    `lead_days` is how long that vendor takes, so it is what a restock promise
    date must be built from. `specialty` says what they actually make — match
    the SKU to the right vendor instead of assuming.
    """
    sql = "SELECT id, name, specialty, lead_days FROM vendors"
    clauses, params = [], []
    if vendor_id is not None:
        clauses.append("id = ?")
        params.append(vendor_id)
    if specialty is not None:
        clauses.append("specialty LIKE ?")
        params.append(f"%{specialty}%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY lead_days"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------- human approval queue


def _load_approvals() -> list[dict]:
    """Read the approval queue, preserving whatever is already there."""
    if not APPROVALS_PATH.exists() or APPROVALS_PATH.stat().st_size == 0:
        return []
    try:
        data = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_approvals(queue: list[dict]) -> None:
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")


@mcp.tool
def propose_payment(
    kind: str,
    amount: float,
    reason: str,
    requested_by: str,
    ref_id: int | None = None,
    account: str = "checking",
) -> dict:
    """Prepare a payment for a human to approve. **Moves no money.**

    This is how an agent asks for a spend. The proposal is checked against the
    live tables — the account exists, the balance covers it, the invoice is
    real and not already paid, the lease exists — and then queued with status
    "pending". The cash balance, the payments ledger and the invoice are left
    exactly as they were.

    Nothing happens until a person approves it in the dashboard; only then is
    `record_payment` called. Use this instead of asking for a payment in prose,
    and tell the requester the proposal is waiting on a human.
    """
    if amount <= 0:
        raise ValueError("Refused: amount must be greater than zero.")
    if not reason or not reason.strip():
        raise ValueError("Refused: give a reason a human can judge this by.")
    if not requested_by or not requested_by.strip():
        raise ValueError("Refused: requested_by must name the agent asking.")
    kind = kind.strip().lower()
    if kind not in {"invoice", "rent", "purchase"}:
        raise ValueError('Refused: kind must be "invoice", "rent" or "purchase".')

    warnings: list[str] = []
    with _connect() as conn:
        today = _today(conn)
        cash = conn.execute(
            "SELECT name, balance FROM cash_accounts WHERE name = ?", (account,)
        ).fetchone()
        if cash is None:
            raise ValueError(f"Refused: no cash account named {account!r}.")
        if amount > cash["balance"]:
            raise ValueError(
                f"Refused: {account} holds {cash['balance']:.2f} but the proposal is "
                f"{amount:.2f}. Do not propose a spend the shop cannot cover."
            )

        detail: dict = {}
        if kind == "invoice":
            if ref_id is None:
                raise ValueError('Refused: kind "invoice" needs the invoice id as ref_id.')
            inv = conn.execute(
                "SELECT id, amount, status, due_date, description FROM invoices WHERE id = ?",
                (ref_id,),
            ).fetchone()
            if inv is None:
                raise ValueError(f"Refused: no invoice with id {ref_id}.")
            if inv["status"] == "paid":
                raise ValueError(f"Refused: invoice {ref_id} is already paid.")
            detail = dict(inv)
            if abs(inv["amount"] - amount) > 0.005:
                warnings.append(
                    f"Proposed {amount:.2f} does not match invoice {ref_id} at {inv['amount']:.2f}."
                )
        elif kind == "rent":
            if ref_id is None:
                raise ValueError('Refused: kind "rent" needs the lease id as ref_id.')
            lease = conn.execute(
                "SELECT id, space_name, monthly_rent, next_due FROM leases WHERE id = ?",
                (ref_id,),
            ).fetchone()
            if lease is None:
                raise ValueError(f"Refused: no lease with id {ref_id}.")
            detail = dict(lease)
            if abs(lease["monthly_rent"] - amount) > 0.005:
                warnings.append(
                    f"Proposed {amount:.2f} does not match lease {ref_id} rent of "
                    f"{lease['monthly_rent']:.2f}."
                )

        balance_after = round(cash["balance"] - amount, 2)
        rent = conn.execute(
            "SELECT id, monthly_rent, next_due FROM leases ORDER BY next_due LIMIT 1"
        ).fetchone()
        if rent and kind != "rent" and balance_after < rent["monthly_rent"]:
            warnings.append(
                f"After this, {balance_after:.2f} would be left, below the "
                f"{rent['monthly_rent']:.2f} rent due {rent['next_due']}."
            )

    queue = _load_approvals()
    proposal = {
        "id": max((p["id"] for p in queue), default=0) + 1,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "amount": round(amount, 2),
        "account": account,
        "reason": reason.strip(),
        "requested_by": requested_by.strip(),
        "proposed_on": today,
        "proposed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "balance_before": cash["balance"],
        "balance_if_approved": balance_after,
        "detail": detail,
        "warnings": warnings,
        "money_moved": False,
    }
    queue.append(proposal)
    _save_approvals(queue)
    return {
        "ok": True,
        "queued": True,
        "money_moved": False,
        "note": "Queued for human approval. No cash has moved and no ledger row was written.",
        "proposal": proposal,
    }


@mcp.tool
def list_pending_approvals() -> list[dict]:
    """List payment proposals and their state (pending / approved / rejected).

    Check this before proposing a spend so the same payment is not queued
    twice.
    """
    return _load_approvals()


# --------------------------------------------------------------- write tools


@mcp.tool
def record_payment(
    kind: str,
    amount: float,
    approved_by: str,
    ref_id: int | None = None,
    account: str = "checking",
    memo: str | None = None,
) -> dict:
    """Pay money out: write a payments row and decrease the cash balance.

    `kind` is "invoice" (then `ref_id` is an invoice id, and that invoice is
    marked paid) or "rent" (then `ref_id` is a lease id). `approved_by` must
    name the person who authorised the spend.

    Refuses to spend more than the account holds, refuses a non-positive
    amount, and refuses to pay an invoice that is already paid. The whole thing
    is one transaction, so cash, the ledger and the invoice never disagree.
    """
    _require_approval(approved_by, "record_payment")
    if amount <= 0:
        raise ValueError("Refused: amount must be greater than zero.")
    kind = kind.strip().lower()
    if kind not in {"invoice", "rent"}:
        raise ValueError('Refused: kind must be "invoice" or "rent".')

    conn = _connect(write=True)
    try:
        with conn:
            cash = conn.execute(
                "SELECT name, balance FROM cash_accounts WHERE name = ?", (account,)
            ).fetchone()
            if cash is None:
                raise ValueError(f"Refused: no cash account named {account!r}.")
            if amount > cash["balance"]:
                raise ValueError(
                    f"Refused: {account} holds {cash['balance']:.2f} but the payment is "
                    f"{amount:.2f}. Not enough cash — escalate instead of overdrawing."
                )

            if kind == "invoice" and ref_id is not None:
                inv = conn.execute(
                    "SELECT id, amount, status FROM invoices WHERE id = ?", (ref_id,)
                ).fetchone()
                if inv is None:
                    raise ValueError(f"Refused: no invoice with id {ref_id}.")
                if inv["status"] == "paid":
                    raise ValueError(f"Refused: invoice {ref_id} is already paid.")
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            if kind == "rent" and ref_id is not None:
                lease = conn.execute(
                    "SELECT id FROM leases WHERE id = ?", (ref_id,)
                ).fetchone()
                if lease is None:
                    raise ValueError(f"Refused: no lease with id {ref_id}.")

            paid_at = _today(conn)
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, ref_id, amount, account, paid_at, approved_by),
            )
            conn.execute(
                "UPDATE cash_accounts SET balance = balance - ? WHERE name = ?",
                (amount, account),
            )
            new_balance = conn.execute(
                "SELECT balance FROM cash_accounts WHERE name = ?", (account,)
            ).fetchone()["balance"]
            return {
                "ok": True,
                "payment_id": cur.lastrowid,
                "kind": kind,
                "ref_id": ref_id,
                "amount": amount,
                "account": account,
                "paid_at": paid_at,
                "approved_by": approved_by,
                "memo": memo,
                "balance_before": cash["balance"],
                "balance_after": new_balance,
                "invoice_marked_paid": ref_id if kind == "invoice" and ref_id else None,
            }
    finally:
        conn.close()


@mcp.tool
def adjust_inventory(
    sku: str,
    size: str,
    delta: int,
    reason: str,
    approved_by: str,
) -> dict:
    """Change the quantity on hand for one (sku, size) row.

    `delta` is the change, not the new total: -1 sells a unit, +12 receives a
    restock. Refuses to drive stock below zero, so a sale that cannot be
    covered fails loudly instead of inventing stock. `reason` is recorded in
    the audit trail by the caller.
    """
    _require_approval(approved_by, "adjust_inventory")
    if delta == 0:
        raise ValueError("Refused: delta of 0 would change nothing.")
    if not reason or not reason.strip():
        raise ValueError("Refused: give a reason for the stock change.")

    conn = _connect(write=True)
    try:
        with conn:
            row = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory "
                "WHERE sku = ? AND size = ?",
                (sku, size),
            ).fetchone()
            if row is None:
                raise ValueError(f"Refused: {sku} has no size {size!r} in inventory.")
            new_qty = row["qty"] + delta
            if new_qty < 0:
                raise ValueError(
                    f"Refused: {sku}/{size} has {row['qty']} on hand; {delta} would "
                    f"leave {new_qty}. Stock cannot go negative — restock first."
                )
            conn.execute(
                "UPDATE inventory SET qty = ? WHERE sku = ? AND size = ?",
                (new_qty, sku, size),
            )
            return {
                "ok": True,
                "sku": sku,
                "size": size,
                "name": row["name"],
                "qty_before": row["qty"],
                "delta": delta,
                "qty_after": new_qty,
                "location": row["location"],
                "reason": reason,
                "approved_by": approved_by,
            }
    finally:
        conn.close()


@mcp.tool
def update_price(
    sku: str,
    new_list_price: float,
    reason: str,
    approved_by: str,
) -> dict:
    """Change the list price of a SKU in the pricing table.

    Refuses any price at or below `unit_cost`, so an approved discount can
    never be sold at a loss. Pricing has no size column, so this changes the
    price for every size of the SKU — say so when you propose it.
    """
    _require_approval(approved_by, "update_price")
    if not reason or not reason.strip():
        raise ValueError("Refused: give a reason for the price change.")

    conn = _connect(write=True)
    try:
        with conn:
            row = conn.execute(
                "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Refused: {sku} is not in the pricing table.")
            if new_list_price <= row["unit_cost"]:
                raise ValueError(
                    f"Refused: {sku} costs {row['unit_cost']:.2f} a unit; a list price of "
                    f"{new_list_price:.2f} would sell at or below cost."
                )
            conn.execute(
                "UPDATE pricing SET list_price = ? WHERE sku = ?", (new_list_price, sku)
            )
            return {
                "ok": True,
                "sku": sku,
                "unit_cost": row["unit_cost"],
                "list_price_before": row["list_price"],
                "list_price_after": new_list_price,
                "margin_per_unit_after": round(new_list_price - row["unit_cost"], 2),
                "applies_to_all_sizes": True,
                "reason": reason,
                "approved_by": approved_by,
            }
    finally:
        conn.close()


ALLOWED_TICKET_STATUS = ("open", "in_progress", "waiting_approval", "resolved", "closed")


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: str,
    note: str,
    updated_by: str,
) -> dict:
    """Move a ticket along and append a note to its history.

    `status` must be one of: open, in_progress, waiting_approval, resolved,
    closed. The note is appended to the ticket's existing notes with the
    author's name — nothing already written there is overwritten.
    """
    _require_approval(updated_by, "update_ticket")
    status = status.strip().lower()
    if status not in ALLOWED_TICKET_STATUS:
        raise ValueError(
            f"Refused: status must be one of {', '.join(ALLOWED_TICKET_STATUS)}."
        )
    if not note or not note.strip():
        raise ValueError("Refused: give a note saying what happened.")

    conn = _connect(write=True)
    try:
        with conn:
            row = conn.execute(
                "SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Refused: no ticket with id {ticket_id}.")
            stamp = _today(conn)
            addition = f"[{stamp}] {updated_by}: {note.strip()}"
            merged = f"{row['notes']}\n{addition}" if row["notes"] else addition
            conn.execute(
                "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
                (status, merged, ticket_id),
            )
            return {
                "ok": True,
                "ticket_id": ticket_id,
                "status_before": row["status"],
                "status_after": status,
                "note_appended": addition,
                "notes_after": merged,
                "updated_by": updated_by,
            }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument("--http", action="store_true", help="serve over HTTP instead of stdio")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
