# ruff: noqa: E501
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from html import escape
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

ADMIN_NAV = (
    ("home", "Dashboard", "/admin"),
    ("portfolio", "Portfolio", "/admin/portfolio"),
    ("cash", "Cash", "/admin/cash"),
    ("holdings", "Holdings", "/admin/holdings"),
    ("trades", "Trades", "/admin/trades"),
    ("orders", "Orders", "/admin/orders"),
    ("watchlist", "Watchlist", "/admin/watchlist"),
    ("settings", "Settings", "/admin/settings"),
    ("audit", "Audit", "/admin/audit"),
)

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
ADMIN_STATIC_DIR = PACKAGE_DIR / "static" / "admin"

templates = (
    Jinja2Templates(directory=str(TEMPLATE_DIR)) if find_spec("jinja2") else None
)


def _page_shell(
    title: str, active_nav: str | None, flash: str | None, body: str
) -> str:
    nav = ""
    logout = ""
    if active_nav != "login":
        logout = (
            '<form method="post" action="/admin/logout">'
            '<button class="button secondary" type="submit">Logout</button></form>'
        )
        links = "".join(
            f'<a href="{href}" class="{"active" if active_nav == key else ""}">{label}</a>'
            for key, label, href in ADMIN_NAV
        )
        nav = f'<nav class="nav" aria-label="Admin navigation">{links}</nav>'
    flash_html = (
        f'<div class="flash" role="status"><strong>{escape(flash)}</strong></div>'
        if flash
        else ""
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} · Finwall Admin</title>"
        '<link rel="stylesheet" href="/admin/static/admin.css"></head><body>'
        '<header class="site-header"><div><a class="brand" href="/admin">Finwall Admin</a>'
        "<p>Internal self-managed portfolio maintenance</p></div>"
        f'{logout}</header>{nav}<main class="container">{flash_html}{body}</main></body></html>'
    )


def _summary_card(label: str, value: object) -> str:
    return f'<div class="summary-card"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'


def _form_page(title: str, body: str) -> str:
    return f"<h1>{escape(title)}</h1>{body}"


def _fallback_body(template_name: str, context: Mapping[str, Any]) -> str:
    if template_name == "login.html":
        return '<section class="panel narrow"><h1>Finwall Admin Login</h1><form method="post" action="/admin/login" class="stacked-form"><label>API token <input type="password" name="token" autocomplete="current-password" required></label><button class="button" type="submit">Login</button></form></section>'
    if template_name == "home.html":
        dashboard = context["dashboard"]
        valuation = dashboard.valuation
        body = [
            "<h1>Dashboard</h1>",
            '<section class="panel"><h2>Portfolio Summary</h2><section class="summary-grid">',
            _summary_card("Portfolio name", dashboard.portfolio_name),
            _summary_card(
                "Total portfolio value",
                valuation["total_portfolio_value"] or "Unavailable",
            ),
            _summary_card("Invested value", valuation["invested_value"]),
            _summary_card("Cash balance", valuation["cash_balance"]),
            _summary_card("Valuation status", valuation["valuation_status"]),
            _summary_card(
                "Price completeness status", valuation["price_completeness_status"]
            ),
            "</section></section>",
            '<section class="panel"><h2>Cash</h2>',
        ]
        if dashboard.cash_balances:
            body.extend(
                f"<p>{escape(str(cash['currency']))} {escape(str(cash['amount']))}</p>"
                for cash in dashboard.cash_balances
            )
        else:
            body.append(
                '<p class="empty-state">No cash balances have been recorded.</p>'
            )
        body.append('</section><section class="panel"><h2>Holdings</h2>')
        if dashboard.holdings:
            body.extend(
                f"<p>{escape(str(holding['ticker']))} {escape(str(holding.get('missing_price_message') or holding.get('price_status')))}</p>"
                for holding in dashboard.holdings
            )
        else:
            body.append('<p class="empty-state">No holdings have been recorded.</p>')
        body.append('</section><section class="panel"><h2>Active Orders</h2>')
        if dashboard.active_orders:
            body.extend(
                f"<p>{escape(str(order['ticker']))} {escape(str(order['description']))}</p>"
                for order in dashboard.active_orders
            )
        else:
            body.append('<p class="empty-state">No active orders.</p>')
        body.append('</section><section class="panel"><h2>Watchlist</h2>')
        if dashboard.watchlist:
            body.extend(
                f"<p>{escape(str(item['ticker']))} {escape(str(item.get('note') or ''))}</p>"
                for item in dashboard.watchlist
            )
        else:
            body.append('<p class="empty-state">No watchlist items.</p>')
        body.append('</section><section class="panel"><h2>Goal And Risk Profile</h2>')
        if dashboard.goal:
            body.append(f"<p>{escape(str(dashboard.goal['name']))}</p>")
        else:
            body.append(
                '<p class="empty-state">Current goal has not been configured.</p>'
            )
        if dashboard.risk_profile:
            body.append(f"<p>{escape(str(dashboard.risk_profile['level']))}</p>")
        else:
            body.append(
                '<p class="empty-state">Risk profile has not been configured.</p>'
            )
        body.extend(
            [
                '</section><section class="panel"><h2>Risk Status</h2>',
                f"<p>{escape(str(valuation['risk']['summary']))}</p>",
                '</section><section class="panel"><h2>Live Data Status</h2>',
                f"<p>Configured market data provider {escape(str(dashboard.live_data['provider']))}</p>",
                f"<p>{escape(str(dashboard.live_data['source']))}</p>",
                '</section><section class="panel"><h2>Latest Report</h2>',
            ]
        )
        if dashboard.latest_report:
            body.append(
                f"<p>Report id {escape(str(dashboard.latest_report['id']))}</p>"
                f"<p>{escape(str(dashboard.latest_report['command_context']))}</p>"
                f"<p>{escape(str(dashboard.latest_report['recommendation_summary'] or ''))}</p>"
            )
        else:
            body.append('<p class="empty-state">No report has been saved yet.</p>')
        body.extend(
            [
                '</section><section class="panel"><h2>Latest Audit</h2><a href="/admin/audit">View all audit events</a>',
            ]
        )
        for event in dashboard.latest_audit_events:
            body.append(
                f"<p>{escape(str(event['changed_at']))} {escape(str(event['action']))} {escape(str(event['entity_type']))} {escape(str(event.get('entity_id') or ''))} {escape(str(event['status']))} {escape(str(event['summary']))}</p>"
            )
        if not dashboard.latest_audit_events:
            body.append('<p class="empty-state">No audit events yet.</p>')
        body.append("</section>")
        return "".join(body)
    if template_name == "portfolio.html":
        return f'<h1>Portfolio</h1><section class="panel"><h2>Portfolio state</h2><pre class="state-dump">{escape(str(context["portfolio"]))}</pre></section>'
    if template_name == "audit.html":
        rows = ""
        for event in context["events"]:
            data = asdict(event) if is_dataclass(event) else event.as_dict()
            rows += (
                "<tr>"
                + "".join(
                    f"<td>{escape(str(data.get(key) or ''))}</td>"
                    for key in [
                        "changed_at",
                        "actor",
                        "source",
                        "action",
                        "entity_type",
                        "entity_id",
                        "status",
                        "summary",
                        "safe_error_message",
                    ]
                )
                + "</tr>"
            )
        if not rows:
            return '<h1>Audit events</h1><section class="panel table-wrap"><p class="empty-state">No audit events yet.</p></section>'
        return (
            '<h1>Audit events</h1><section class="panel table-wrap"><table><thead><tr><th>changed_at</th><th>actor</th><th>source</th><th>action</th><th>entity</th><th>entity id</th><th>status</th><th>summary</th><th>error</th></tr></thead><tbody>'
            + rows
            + "</tbody></table></section>"
        )
    forms: dict[str, str] = {
        "cash.html": '<div class="form-grid"><section class="panel"><h2>Add cash</h2><form method="post" action="/admin/cash/add" class="stacked-form"><label>Currency<input name="currency" placeholder="USD" required></label><label>Amount<input name="amount" inputmode="decimal" required></label><button class="button">Add cash</button></form></section><section class="panel"><h2>Withdraw cash</h2><form method="post" action="/admin/cash/withdraw" class="stacked-form"><label>Currency<input name="currency" placeholder="USD" required></label><label>Amount<input name="amount" inputmode="decimal" required></label><button class="button danger">Withdraw cash</button></form></section></div>',
        "holdings.html": '<div class="form-grid"><section class="panel"><h2>Add or update holding</h2><form method="post" action="/admin/holdings" class="stacked-form"><label>Ticker<input name="ticker" required></label><label>Shares<input name="shares" required></label><label>Average price<input name="average_price" required></label><label>Sector<input name="sector"></label><button class="button">Save holding</button></form></section><section class="panel"><h2>Delete holding</h2><form method="post" action="/admin/holdings/delete" class="stacked-form"><label>Ticker<input name="ticker" required></label><button class="button danger">Delete holding</button></form></section></div>',
        "trades.html": '<div class="form-grid"><section class="panel"><h2>Buy</h2><form method="post" action="/admin/trades/buy" class="stacked-form"><label>Ticker<input name="ticker" required></label><label>Shares<input name="shares" required></label><label>Price<input name="price" required></label><label>Currency<input name="currency" required></label><label>Trade date<input name="trade_date" type="date"></label><button class="button">Buy</button></form></section><section class="panel"><h2>Sell</h2><form method="post" action="/admin/trades/sell" class="stacked-form"><label>Ticker<input name="ticker" required></label><label>Shares<input name="shares" required></label><label>Price<input name="price" required></label><label>Currency<input name="currency" required></label><label>Trade date<input name="trade_date" type="date"></label><button class="button danger">Sell</button></form></section></div>',
        "orders.html": '<div class="form-grid"><section class="panel"><h2>Add or update order</h2><form method="post" action="/admin/orders" class="stacked-form"><label>Ticker<input name="ticker" required></label><label>Side<input name="side" placeholder="buy or sell" required></label><label>Order type<input name="order_type" placeholder="limit, stop_loss, stop_limit" required></label><label>Shares<input name="shares" required></label><label>Limit price<input name="limit_price"></label><label>Stop price<input name="stop_price"></label><button class="button">Save order</button></form></section><section class="panel"><h2>Delete order</h2><form method="post" action="/admin/orders/delete" class="stacked-form"><label>Ticker<input name="ticker" required></label><button class="button danger">Delete order</button></form></section></div>',
        "watchlist.html": '<div class="form-grid"><section class="panel"><h2>Add or update item</h2><form method="post" action="/admin/watchlist" class="stacked-form"><label>Ticker<input name="ticker" required></label><label>Note<input name="note"></label><button class="button">Save item</button></form></section><section class="panel"><h2>Delete item</h2><form method="post" action="/admin/watchlist/delete" class="stacked-form"><label>Ticker<input name="ticker" required></label><button class="button danger">Delete item</button></form></section></div>',
        "settings.html": '<div class="form-grid"><section class="panel"><h2>Goal</h2><form method="post" action="/admin/goal" class="stacked-form"><label>Name<input name="name" required></label><label>Target amount<input name="target_amount"></label><button class="button">Set goal</button></form></section><section class="panel"><h2>Timeline</h2><form method="post" action="/admin/timeline" class="stacked-form"><label>Start date<input name="start_date" type="date" required></label><label>Target date<input name="target_date" type="date"></label><button class="button">Set timeline</button></form></section><section class="panel"><h2>Risk profile</h2><form method="post" action="/admin/risk-profile" class="stacked-form"><label>Level<input name="level" required></label><label>Notes<input name="notes"></label><button class="button">Set risk profile</button></form></section></div>',
    }
    page_title = str(context["title"])
    return _form_page(page_title, forms[template_name])


def render_admin_template(
    request: Request,
    template_name: str,
    *,
    title: str,
    active_nav: str | None = None,
    flash: str | None = None,
    status_code: int = 200,
    **context: Any,
) -> Response:
    full_context = {
        "title": title,
        "active_nav": active_nav,
        "flash": flash if flash is not None else request.query_params.get("msg"),
        "nav_items": ADMIN_NAV,
        "current_path": request.url.path,
        **context,
    }
    if templates is not None:
        return templates.TemplateResponse(
            request, f"admin/{template_name}", full_context, status_code=status_code
        )
    body = _fallback_body(template_name, full_context)
    return HTMLResponse(
        _page_shell(title, active_nav, full_context["flash"], body),
        status_code=status_code,
    )
