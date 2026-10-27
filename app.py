from datetime import date, datetime, time, timedelta
from pathlib import Path
import logging
import re
import sqlite3
import streamlit as st
import pandas as pd
from data_structures import LinkedListCart, AVLTree, MinHeap, HeapEntry
import database as db

APP_DIR = Path(__file__).resolve().parent
LOG_PATH = APP_DIR / 'pos.log'
logging.basicConfig(filename=LOG_PATH, level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')

st.set_page_config(page_title='Gulps & Grubs | POS', page_icon='🥤', layout='wide', initial_sidebar_state='collapsed')

def money(cents): return f"₱{int(cents)/100:,.2f}"
def safe_error(exc):
    logging.exception('Application operation failed')
    if isinstance(exc, (ValueError, sqlite3.IntegrityError)): st.error(str(exc))
    else: st.error('Something went wrong while saving your changes. No incomplete transaction was committed. Check pos.log for technical details.')
def cents_from_peso(value): return int(round(float(value) * 100))

def generate_category_product_code(category):
    """Generate the next unused product code for the selected category."""
    category_prefixes = {
        'Milkshake': 'GUL-MS',
        'Milktea': 'GUL-MT',
        'Lemonades': 'GUL-LEM',
        'Lemonade Slushie': 'GUL-LS',
        'Floats': 'GUL-FL',
        'Coffee': 'GUL-COF',
        'Streetfoods': 'GRB-STF',
        'Donut and Waffles': 'GRB-WAF',
        'Dim Sum': 'GRB-DSM',
        'Others': 'GRB-OTH',
        'Gulps': 'GUL',
        'Grubs': 'GRB',
        'Other': 'OTH',
    }
    prefix = category_prefixes.get(category, 'OTH')

    existing_products = db.list_products()
    existing_codes = {
        str(product.get('code', '')).strip().upper()
        for product in existing_products
    }

    pattern = re.compile(rf"^{re.escape(prefix)}-(\\d+)$", re.IGNORECASE)
    used_numbers = []
    for existing_code in existing_codes:
        match = pattern.fullmatch(existing_code)
        if match:
            used_numbers.append(int(match.group(1)))

    next_number = max(used_numbers, default=0) + 1
    candidate = f"{prefix}-{next_number:03d}"
    while candidate.upper() in existing_codes:
        next_number += 1
        candidate = f"{prefix}-{next_number:03d}"

    return candidate


def rebuild_tree():
    tree = AVLTree()
    for p in db.list_products(active_only=True): tree.insert(p['code'], p)
    tree.validate()
    return tree

def rebuild_heap():
    heap = MinHeap()
    for o in db.list_orders(pending_only=True):
        heap.push(HeapEntry(int(o['priority']), int(o['sequence_no']), int(o['id']), o))
    return heap

# Retro orange-and-yellow diner theme
st.markdown('''<style>
:root{
  --cream:#fff4d8; --paper:#fffaf0; --orange:#f47b20; --orange-deep:#df5e12;
  --burgundy:#4b1117; --burgundy-soft:#682027; --gold:#ffc928; --gold-light:#ffe27a;
  --ink:#42151a; --muted:#815a4a; --line:#f0c777;
}
.stApp{
  background-color:var(--cream); color:var(--ink);
  background-image:repeating-linear-gradient(90deg,rgba(244,123,32,.055) 0,rgba(244,123,32,.055) 14px,transparent 14px,transparent 165px),
  linear-gradient(180deg,#fff8e6 0%,#fff0d1 100%);
}
[data-testid="stHeader"]{background:rgba(255,244,216,.88)}
h1,h2,h3{color:var(--burgundy)!important;letter-spacing:-.025em}
h2{border-bottom:2px solid rgba(244,123,32,.20);padding-bottom:.35rem}
[data-testid="stMetric"]{
  background:var(--paper); border:1px solid var(--line); border-top:4px solid var(--orange);
  border-radius:14px; padding:14px 16px; box-shadow:0 5px 15px rgba(75,17,23,.07)
}
[data-testid="stMetricLabel"]{color:var(--muted)!important}
[data-testid="stMetricValue"]{color:var(--burgundy)!important;font-weight:800}
.stButton>button,.stDownloadButton>button{
  border-radius:10px;border:1px solid var(--orange-deep);font-weight:750;min-height:2.55rem;
  background:#fffaf0;color:var(--burgundy);transition:transform .12s ease,box-shadow .12s ease;
}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--burgundy);box-shadow:0 3px 9px rgba(75,17,23,.12);transform:translateY(-1px)}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{
  background:linear-gradient(180deg,#ff9a2e 0%,#ed6b17 100%);color:#fffaf0;border:1px solid #c84d12;
}
.stButton>button[kind="primary"]:hover,.stFormSubmitButton>button[kind="primary"]:hover{
  background:linear-gradient(180deg,#f47b20 0%,#d95312 100%);color:white;border-color:var(--burgundy)
}
[data-testid="stForm"]{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px}
[data-testid="stExpander"]{background:var(--paper);border:1px solid var(--line);border-radius:12px}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:7px}
[data-testid="stTabs"] [data-baseweb="tab"]{background:#ffefd0;border-radius:9px 9px 0 0;padding:9px 14px;color:var(--burgundy)}
[data-testid="stTabs"] [aria-selected="true"]{background:var(--orange)!important;color:white!important}
input,[data-baseweb="select"]>div,textarea{border-radius:8px!important}
[data-testid="stDataFrame"], [data-testid="stTable"]{border:1px solid var(--line);border-radius:10px;overflow:hidden}
hr{border-color:var(--line)!important} footer{visibility:hidden}
.product-card{background:linear-gradient(145deg,#fffdf6 0%,#fff0d2 100%);border:1px solid #efc36b;border-top:4px solid var(--orange);border-radius:14px;padding:14px;min-height:125px;box-shadow:0 4px 12px rgba(75,17,23,.055)}
.product-card h3{color:var(--orange-deep)!important;margin:.45rem 0}
.small-note{font-size:.88rem;color:var(--muted)}
[data-testid="stSidebar"]{display:none!important}
[data-testid="stSidebarCollapsedControl"]{display:none!important}
</style>''', unsafe_allow_html=True)

# Storefront header styling
st.markdown('''<style>
[data-testid="stHeader"]{background:rgba(255,244,216,.95)!important}
.st-key-site_header{
  background:linear-gradient(105deg,#ef7420 0%,#ff982b 48%,#ed6d19 100%);
  border:2px solid #ffc928;border-bottom:5px solid #ffc928;border-radius:12px;
  padding:10px 16px 8px;margin:0 0 20px;box-shadow:0 5px 0 rgba(75,17,23,.10),inset 0 0 0 1px rgba(255,248,220,.5);
  position:relative;overflow:hidden
}
.site-brand-name{color:#fff8e7;font-weight:950;font-size:clamp(1.1rem,1.6vw,1.65rem);line-height:1.1;letter-spacing:-.025em;text-shadow:2px 2px 0 #4b1117,-1px -1px 0 #4b1117}
.site-brand-tag{color:#fff0c9;font-size:.68rem;font-weight:850;letter-spacing:.08em;margin-top:5px;white-space:nowrap}
.site-nav-label{font-size:.61rem;line-height:1.1;font-weight:950;letter-spacing:.13em;color:#fff0c9;margin:0 0 6px 3px;text-transform:uppercase}
.st-key-site_header [data-testid="stRadio"]>label{display:none}
.st-key-site_header [data-testid="stRadio"] [role="radiogroup"]{gap:5px;flex-wrap:wrap;align-items:center}
.st-key-site_header [data-testid="stRadio"] [role="radio"]{
  background:rgba(75,17,23,.12);border:1px solid rgba(255,247,220,.38);border-radius:6px;
  padding:7px 10px;min-height:34px;color:#fff8e7;font-size:.82rem;font-weight:850;white-space:nowrap;
}
.st-key-site_header [data-testid="stRadio"] [role="radio"][aria-checked="true"]{
  background:#4b1117;border-color:#ffe27a;box-shadow:inset 0 -3px 0 #ffc928;color:#fff8e7
}
.st-key-site_header [data-testid="stRadio"] [role="radio"] div,
.st-key-site_header [data-testid="stRadio"] [role="radio"] p{color:inherit!important}
</style>''', unsafe_allow_html=True)

try:
    db.init_db()
except Exception as e:
    st.error('Could not initialize the database. Check folder permissions and the application log.')
    logging.exception('Database initialization failed')
    st.stop()

if 'cart' not in st.session_state: st.session_state.cart = LinkedListCart()
if 'last_sale' not in st.session_state: st.session_state.last_sale = None

# Header Navigation supporting 3 MODES
with st.container(key='site_header'):
    logo_col, brand_col, mode_col, page_col = st.columns([1.05, 1.8, 1.85, 4.9], vertical_alignment='center', gap='small')
    with logo_col:
        st.image(str(APP_DIR / 'brand_logo.jpg'), width=118)
    with brand_col:
        st.markdown('<div class="site-brand-name">Gulps &amp; Grubs</div><div class="site-brand-tag">AT THE GARAGE · POS</div>', unsafe_allow_html=True)
    with mode_col:
        st.markdown('<div class="site-nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        mode = st.radio('Workspace', ['Admin', 'Cashier', 'Inventory Manager'], horizontal=True, key='mode_choice', label_visibility='collapsed')
    
    with page_col:
        st.markdown('<div class="site-nav-label">NAVIGATION</div>', unsafe_allow_html=True)
        if mode == 'Admin':
            page = st.radio('Admin navigation', ['Dashboard', 'Sales History'], horizontal=True, key='admin_page', label_visibility='collapsed')
        elif mode == 'Cashier':
            page = st.radio('Cashier navigation', ['New Sale', 'Pickup Queue Priority', 'Last Transaction'], horizontal=True, key='cashier_page', label_visibility='collapsed')
        elif mode == 'Inventory Manager':
            page = st.radio('Inventory navigation', ['Stock Overview', 'Products Management', 'Restock'], horizontal=True, key='inventory_page', label_visibility='collapsed')

# Rebuild AVL tree on each run
try: product_tree = rebuild_tree()
except Exception as e:
    safe_error(e); st.stop()


# ==========================================
# MODE 1: ADMIN
# ==========================================
if mode == 'Admin' and page == 'Dashboard':
    st.subheader('Business Overview')
    today = date.today(); start = datetime.combine(today, time.min).isoformat(); end = datetime.combine(today + timedelta(days=1), time.min).isoformat()
    summary = db.sales_summary(start, end)
    all_products = db.list_products(active_only=True)
    low = [p for p in all_products if p['stock'] <= p['low_stock_threshold']]
    
    a, b, c, d = st.columns(4)
    a.metric("Today's Revenue", money(summary['revenue_cents']))
    b.metric('Completed Sales', summary['transactions'])
    c.metric('Active Products', len(all_products))
    d.metric('Low-Stock Alerts', len(low), delta='Needs attention' if low else 'Stock looks good', delta_color='inverse' if low else 'normal')
    
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown('#### Low-stock watch')
        if low:
            st.dataframe(pd.DataFrame([{'Code': p['code'], 'Product': p['name'], 'Stock': p['stock'], 'Alert at': p['low_stock_threshold']} for p in low]), use_container_width=True, hide_index=True)
        else: st.success('No active products are at or below their low-stock threshold.')
    with right:
        st.markdown('#### Recent transactions')
        recent = db.transaction_history()[:6]
        if recent: st.dataframe(pd.DataFrame([{'Sale #': r['id'], 'Date': r['created_at'].replace('T', ' '), 'Total': money(r['total_cents'])} for r in recent]), use_container_width=True, hide_index=True)
        else: st.info('Completed sales will appear here.')

elif mode == 'Admin' and page == 'Sales History':
    st.subheader('Sales History')
    c1, c2 = st.columns(2)
    start_date = c1.date_input('From date', value=date.today() - timedelta(days=30))
    end_date = c2.date_input('To date', value=date.today())
    if start_date > end_date: st.error('The start date must not be after the end date.')
    else:
        start = datetime.combine(start_date, time.min).isoformat()
        end = datetime.combine(end_date + timedelta(days=1), time.min).isoformat()
        rows = db.transaction_history(start, end)
        st.metric('Revenue in selected period', money(sum(r['total_cents'] for r in rows)))
        if rows:
            st.dataframe(pd.DataFrame([{'Sale #': r['id'], 'Date/time': r['created_at'].replace('T', ' '), 'Cashier': r['cashier_label'], 'Total': money(r['total_cents'])} for r in rows]), use_container_width=True, hide_index=True)
            chosen = st.selectbox('View sale details', [r['id'] for r in rows], format_func=lambda x: f"Sale #{x}")
            details = db.transaction_items(chosen)
            st.dataframe(pd.DataFrame([{'Code': x['product_code'], 'Product': x['product_name'], 'Qty': x['quantity'], 'Unit price': money(x['unit_price_cents']), 'Subtotal': money(x['subtotal_cents'])} for x in details]), use_container_width=True, hide_index=True)
        else: st.info('No transactions were found for the selected dates.')


# ==========================================
# MODE 2: CASHIER (Includes Order Priority)
# ==========================================
elif mode == 'Cashier' and page == 'New Sale':
    st.subheader('New Sale')
    products = db.list_products(active_only=True)
    left, right = st.columns([1.35, 1], gap='large')
    with left:
        st.markdown('#### Available products')
        query = st.text_input('Find a product', placeholder='Search product name or code')
        if query.strip():
            match = product_tree.search(query.strip())
            shown = [match] if match else [p for p in products if query.casefold() in (p['name'] + ' ' + p['code']).casefold()]
        else: shown = products
        if not shown: st.info('No matching active products.')
        for start_idx in range(0, len(shown), 2):
            cols = st.columns(2)
            for col, p in zip(cols, shown[start_idx:start_idx+2]):
                with col:
                    st.markdown(f"<div class='product-card'><b>{p['name']}</b><br><span class='small-note'>{p['code']} · {p['category']}</span><h3>{money(p['price_cents'])}</h3><span class='small-note'>In stock: {p['stock']}</span></div>", unsafe_allow_html=True)
                    with st.form(f"add_cart_{p['id']}"):
                        qty = st.number_input('Qty', min_value=1, max_value=max(1, int(p['stock'])), value=1, step=1, key=f"qty_{p['id']}", disabled=p['stock'] < 1)
                        add = st.form_submit_button('Add to cart', use_container_width=True, disabled=p['stock'] < 1)
                    if add:
                        try:
                            if qty > p['stock']: raise ValueError(f"Only {p['stock']} unit(s) are in stock.")
                            st.session_state.cart.add(p, int(qty)); st.success(f"Added {qty} × {p['name']}."); st.rerun()
                        except Exception as e: safe_error(e)
    with right:
        st.markdown('#### Shopping cart')
        cart = st.session_state.cart
        items = cart.items()
        if not items: st.info('Your cart is empty. Add a product to begin.')
        else:
            for item in items:
                with st.container(border=True):
                    c1, c2 = st.columns([2, 1]); c1.markdown(f"**{item['name']}**\n\n{money(item['unit_price_cents'])} each")
                    c2.markdown(f"**{money(item['subtotal_cents'])}**")
                    qcol, rmcol = st.columns([2, 1])
                    new_q = qcol.number_input('Quantity', min_value=1, max_value=1000000, value=int(item['quantity']), step=1, key=f"cart_q_{item['product_id']}")
                    if qcol.button('Update', key=f"update_{item['product_id']}"):
                        try:
                            p = db.get_product(item['product_id'])
                            if not p or not p['active']: raise ValueError('This product is no longer available.')
                            if int(new_q) > p['stock']: raise ValueError(f"Only {p['stock']} unit(s) are in stock.")
                            cart.set_quantity(item['product_id'], int(new_q)); st.rerun()
                        except Exception as e: safe_error(e)
                    if rmcol.button('Remove', key=f"remove_{item['product_id']}"):
                        cart.remove(item['product_id']); st.rerun()
            st.divider(); st.markdown(f"### Total: {money(cart.total_cents())}")
            with st.form('checkout_form'):
                cashier_label = st.text_input('Cashier label (optional)', value='Cashier')
                confirm = st.form_submit_button('Confirm sale', type='primary', use_container_width=True)
            if confirm:
                try:
                    sale = db.checkout(cart.items(), cashier_label.strip() or 'Cashier')
                    st.session_state.last_sale = sale; cart.clear(); st.success(f"Sale #{sale['transaction_id']} completed — {money(sale['total_cents'])}."); st.rerun()
                except Exception as e: safe_error(e)

elif mode == 'Cashier' and page == 'Pickup Queue Priority':
    st.subheader('Cashier - Order Priority & Pickup Queue')
    st.caption('Cashiers can set order priority levels: Priority 1 is most urgent (handles first), Priority 5 is least urgent/flexible.')
    
    with st.form('new_order_form', clear_on_submit=True):
        customer = st.text_input('Customer name *')
        details = st.text_input('Order details *', placeholder='e.g. 2 Milk Teas, 1 Waffle')
        priority = st.select_slider('Set Priority Level', options=[1, 2, 3, 4, 5], value=3, 
                                    format_func=lambda x: {1: '1 · Urgent', 2: '2 · High', 3: '3 · Normal', 4: '4 · Low', 5: '5 · Flexible'}[x])
        add_order_btn = st.form_submit_button('Add Priority Order to Queue', type='primary')
    
    if add_order_btn:
        try:
            if not customer or not details:
                raise ValueError("Customer name and order details are required.")
            oid = db.add_order(customer, details, int(priority))
            st.success(f'Order #{oid} added with Priority {priority}.')
            st.rerun()
        except Exception as e: safe_error(e)

    st.divider()
    heap = rebuild_heap()
    next_order = heap.peek()
    
    if next_order:
        st.markdown("### 🔔 Next Priority Order in Queue")
        st.info(f"**Order #{next_order.order_id}** — {next_order.payload['customer_name']} | **Priority Level:** {next_order.priority} | **Details:** {next_order.payload['details']}")
        if st.button('Mark Next Order Completed', type='primary'):
            try:
                db.update_order_status(next_order.order_id, 'Completed')
                st.success(f'Order #{next_order.order_id} marked as completed.')
                st.rerun()
            except Exception as e: safe_error(e)
    else:
        st.success('No pending pickup orders in queue.')

    st.markdown("#### All Pending Pickup Orders")
    all_orders = db.list_orders()
    if all_orders:
        st.dataframe(pd.DataFrame([{'Order #': o['id'], 'Customer': o['customer_name'], 'Details': o['details'], 'Priority': o['priority'], 'Status': o['status'], 'Created': o['created_at'].replace('T', ' ')} for o in all_orders]), use_container_width=True, hide_index=True)

elif mode == 'Cashier' and page == 'Last Transaction':
    st.subheader('Last Transaction')
    sale = st.session_state.last_sale
    if not sale: st.info('Complete a sale in New Sale to display details here.')
    else:
        st.success(f"Sale #{sale['transaction_id']} · {sale['created_at'].replace('T', ' ')}")
        st.metric('Total Paid', money(sale['total_cents']))
        st.dataframe(pd.DataFrame([{'Code': x['code'], 'Product': x['name'], 'Qty': x['quantity'], 'Unit price': money(x['unit_price_cents']), 'Subtotal': money(x['subtotal_cents'])} for x in sale['items']]), use_container_width=True, hide_index=True)


# ==========================================
# MODE 3: INVENTORY MANAGER
# ==========================================
elif mode == 'Inventory Manager' and page == 'Stock Overview':
    st.subheader('Stock Overview')
    products = db.list_products(active_only=True)
    if products:
        st.dataframe(pd.DataFrame([{'Code': p['code'], 'Product Name': p['name'], 'Category': p['category'], 'Current Stock': p['stock'], 'Alert Threshold': p['low_stock_threshold']} for p in products]), use_container_width=True, hide_index=True)
    else:
        st.info('No active products available.')

elif mode == 'Inventory Manager' and page == 'Products Management':
    st.subheader('Add, Edit, & Delete Products')
    tab1, tab2 = st.tabs(['Add Product', 'Edit / Delete Product'])
    
    with tab1:
        with st.form('add_product_form', clear_on_submit=True):
            name = st.text_input('Product name *', placeholder='e.g. Brown Sugar Latte').strip()
            product_group = st.selectbox('Product group', ['Gulps', 'Grubs', 'Other'], index=0)

            if product_group == 'Gulps':
                category = st.selectbox('Gulps category', ['Milkshake', 'Milktea', 'Lemonades', 'Lemonade Slushie', 'Floats', 'Coffee'])
            elif product_group == 'Grubs':
                category = st.selectbox('Grubs category', ['Streetfoods', 'Donut and Waffles', 'Dim Sum', 'Others'])
            else:
                category = 'Other'

            c2, c3, c4 = st.columns(3)
            price = c2.number_input('Price (₱)', min_value=0.0, max_value=1000000.0, value=0.00, step=0.5, format='%.2f')
            stock = c3.number_input('Starting stock', min_value=0, max_value=1000000, value=0, step=1)
            threshold = c4.number_input('Low-stock alert at', min_value=0, max_value=1000000, value=0, step=1)
            submitted = st.form_submit_button('Add product', type='primary', use_container_width=True)

        if submitted:
            try:
                if not name: raise ValueError('Please enter a product name.')
                code = generate_category_product_code(category)
                db.add_product(code, name, category, cents_from_peso(price), int(stock), int(threshold))
                st.success(f"{name} added successfully with code {code}.")
                st.rerun()
            except Exception as e: safe_error(e)

    products = db.list_products()
    with tab2:
        if not products: st.info('Add your first product to begin.')
        else:
            labels = {f"{p['code']} — {p['name']} {'(inactive)' if not p['active'] else ''}": p for p in products}
            selected_label = st.selectbox('Select product', list(labels), key='edit_select')
            p = labels[selected_label]
            if p['active']:
                with st.form(f"edit_product_form_{p['id']}"):
                    ec1, ec2 = st.columns(2)
                    new_code = ec1.text_input('Product code', value=p['code'], key=f"edit_code_{p['id']}").strip().upper()
                    new_name = ec2.text_input('Product name', value=p['name'], key=f"edit_name_{p['id']}").strip()
                    
                    edit_categories = ['Milkshake', 'Milktea', 'Lemonades', 'Lemonade Slushie', 'Floats', 'Coffee', 'Streetfoods', 'Donut and Waffles', 'Dim Sum', 'Others', 'Gulps', 'Grubs', 'Other']
                    cat_index = edit_categories.index(p['category']) if p['category'] in edit_categories else edit_categories.index('Other')
                    new_cat = st.selectbox('Category', edit_categories, index=cat_index, key=f"edit_cat_{p['id']}")
                    
                    ec3, ec4, ec5 = st.columns(3)
                    new_price = ec3.number_input('Price (₱)', min_value=0.0, max_value=1000000.0, value=float(p['price_cents'] / 100), step=0.5, format='%.2f', key=f"edit_price_{p['id']}")
                    new_stock = ec4.number_input('Stock', min_value=0, max_value=1000000, value=int(p['stock']), step=1, key=f"edit_stock_{p['id']}")
                    new_threshold = ec5.number_input('Low-stock alert at', min_value=0, max_value=1000000, value=int(p['low_stock_threshold']), step=1, key=f"edit_threshold_{p['id']}")

                    save = st.form_submit_button('Save changes', type='primary')
                    if save:
                        try:
                            db.update_product(p['id'], new_code, new_name, new_cat, cents_from_peso(new_price), int(new_stock), int(new_threshold))
                            st.success(f"Product '{new_name}' updated successfully.")
                            st.rerun()
                        except Exception as e: safe_error(e)

                if st.button('Delete selected product', key=f"delete_btn_{p['id']}", type='secondary'):
                    try:
                        db.delete_product(p['id'])
                        st.success('Product permanently deleted.')
                        st.rerun()
                    except Exception as e: safe_error(e)

elif mode == 'Inventory Manager' and page == 'Restock':
    st.subheader('Restock Inventory')
    active_products = db.list_products(active_only=True)
    if active_products:
        options = {f"{p['code']} — {p['name']} (Current Stock: {p['stock']})": p for p in active_products}
        with st.form('restock_form'):
            chosen = st.selectbox('Product to restock', list(options))
            qty = st.number_input('Quantity to add', min_value=1, max_value=1000000, value=10, step=1)
            restock = st.form_submit_button('Record Restock', type='primary')
        if restock:
            try:
                db.restock_product(options[chosen]['id'], int(qty))
                st.success('Stock updated successfully.')
                st.rerun()
            except Exception as e: safe_error(e)
    else:
        st.info('Add an active product before restocking.')

st.divider()
st.caption('Gulps & Grubs POS · SQLite persistent database · 3 Workspace Modes')
