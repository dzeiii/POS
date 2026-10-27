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
            page = st.radio('Admin navigation', ['Dashboard', 'Product Management', 'Sales History'], horizontal=True, key='admin_page', label_visibility='collapsed')
        elif mode == 'Cashier':
            page = st.radio('Cashier navigation', ['New Sale', 'Pickup Queue Priority', 'Last Transaction'], horizontal=True, key='cashier_page', label_visibility='collapsed')
        elif mode == 'Inventory Manager':
            page = st.radio('Inventory navigation', ['Stock Overview', 'Restock'], horizontal=True, key='inventory_page', label_visibility='collapsed')

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

elif mode == 'Admin' and page == 'Product Management':
    st.subheader('Product Catalog Management')
    products = db.list_products()
    
    tab1, tab2 = st.tabs(['Add Product', 'Edit / Delete Product'])
    
    with tab1:
        with st.form('add_product_form', clear_on_submit=True):
            name = st.text_input('Product name *', placeholder='e.g. Brown Sugar Latte').strip()
            product_group = st.selectbox('Product group', ['Gulps', 'Grubs', 'Other'], index=0)

            selected_size = None

            if product_group == 'Gulps':
                category = st.selectbox('Gulps category', ['Milkshake', 'Milktea', 'Lemonades', 'Lemonade Slushie', 'Floats', 'Coffee'])
                
                if category in ['Milkshake', 'Lemonades', 'Lemonade Slushie', 'Coffee', 'Milktea']:
                    selected_size = st.selectbox('Drink Size', ['12oz', '16oz'], index=1)
                elif category == 'Floats':
                    selected_size = st.selectbox('Drink Size', ['8oz', '12oz', '16oz'], index=1)

            elif product_group == 'Grubs':
                category = st.selectbox('Grubs category', ['Streetfoods', 'Donut and Waffles', 'Dim Sum', 'Others'])
            else:
                category = 'Other'

            c2, c3, c4 = st.columns(3)
