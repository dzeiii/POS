from datetime import date, datetime, time, timedelta
from pathlib import Path
import logging
import sqlite3
import streamlit as st
import pandas as pd
from data_structures import LinkedListCart, AVLTree, MinHeap, HeapEntry
import database as db

APP_DIR=Path(__file__).resolve().parent
LOG_PATH=APP_DIR/'pos.log'
logging.basicConfig(filename=LOG_PATH, level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')

st.set_page_config(page_title='Gulps & Grubs | POS', page_icon='🥤', layout='wide', initial_sidebar_state='collapsed')

def money(cents): return f"₱{int(cents)/100:,.2f}"
def safe_error(exc):
    logging.exception('Application operation failed')
    if isinstance(exc,(ValueError,sqlite3.IntegrityError)): st.error(str(exc))
    else: st.error('Something went wrong while saving your changes. No incomplete transaction was committed. Check pos.log for technical details.')
def cents_from_peso(value): return int(round(float(value)*100))

def rebuild_tree():
    tree=AVLTree()
    for p in db.list_products(active_only=True): tree.insert(p['code'],p)
    tree.validate()
    return tree

def rebuild_heap():
    heap=MinHeap()
    for o in db.list_orders(pending_only=True):
        heap.push(HeapEntry(int(o['priority']),int(o['sequence_no']),int(o['id']),o))
    return heap

# Retro orange-and-yellow diner theme inspired by the Gulps & Grubs brand.
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
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#4b1117 0%,#672027 72%,#4b1117 100%);
  border-right:5px solid var(--gold); box-shadow:5px 0 18px rgba(75,17,23,.10);
}
[data-testid="stSidebar"] *{color:#fff4d8!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label{
  padding:9px 11px; border:1px solid rgba(255,201,40,.12); border-radius:10px;
  background:rgba(255,255,255,.045); margin-bottom:5px; transition:background .15s ease;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{
  background:rgba(255,201,40,.18); border-color:rgba(255,201,40,.42)
}
[data-testid="stSidebar"] [data-testid="stImage"] img{border:3px solid var(--gold);border-radius:13px}
[data-testid="stSidebar"] hr{border-color:rgba(255,201,40,.35)!important}
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
.brand-banner{
  position:relative;overflow:hidden;padding:22px 25px 19px;margin:2px 0 24px;
  border:4px solid var(--gold);outline:1px solid #d95714;border-radius:15px;
  background:repeating-linear-gradient(90deg,rgba(213,79,12,.23) 0,rgba(213,79,12,.23) 13px,transparent 13px,transparent 165px),
  linear-gradient(115deg,#ed7423 0%,#ff9e2e 50%,#ef7923 100%);
  box-shadow:0 6px 0 rgba(75,17,23,.10),inset 0 0 0 2px rgba(255,245,208,.48);
}
.brand-banner:after{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 85% 30%,rgba(255,245,208,.30) 0 4px,transparent 5px),radial-gradient(circle at 91% 72%,rgba(255,245,208,.28) 0 7px,transparent 8px);background-size:42px 42px,58px 58px}
.brand-kicker{position:relative;z-index:1;font-size:.75rem;text-transform:uppercase;letter-spacing:.16em;font-weight:900;color:#fff2c7}
.brand-title{position:relative;z-index:1;font-size:clamp(1.8rem,3vw,2.7rem);line-height:1.05;font-weight:950;color:var(--burgundy);margin:.25rem 0;text-shadow:1px 2px 0 rgba(255,221,112,.8)}
.brand-sub{position:relative;z-index:1;color:#fff7df;margin:0;font-weight:600}
.product-card{background:linear-gradient(145deg,#fffdf6 0%,#fff0d2 100%);border:1px solid #efc36b;border-top:4px solid var(--orange);border-radius:14px;padding:14px;min-height:125px;box-shadow:0 4px 12px rgba(75,17,23,.055)}
.product-card h3{color:var(--orange-deep)!important;margin:.45rem 0}
.small-note{font-size:.88rem;color:var(--muted)}
[data-testid="stAlert"]{border-radius:12px}
@media (max-width: 768px){.brand-banner{padding:16px}.brand-title{font-size:1.8rem}[data-testid="stMetric"]{padding:10px}}
</style>''',unsafe_allow_html=True)

# UI polish layer: clearer hierarchy, stronger brand contrast, and friendlier controls.
st.markdown('''<style>
/* Keep the retro palette, but improve contrast and reduce visual noise. */
.block-container{padding-top:1.5rem;padding-bottom:2rem;max-width:1500px}
.brand-banner{padding:clamp(18px,2.5vw,30px);border-radius:18px;margin-bottom:1.5rem}
.brand-title{
  color:#fff5d9!important;font-size:clamp(2rem,4vw,3.15rem);letter-spacing:-.035em;
  text-shadow:-2px -2px 0 #4b1117,2px -2px 0 #4b1117,-2px 2px 0 #4b1117,2px 2px 0 #4b1117,0 5px 0 #4b1117,0 7px 0 rgba(255,201,40,.95);
}
.brand-sub{font-size:1rem;text-shadow:0 1px 2px rgba(75,17,23,.35)}
.brand-kicker{display:inline-block;background:rgba(75,17,23,.88);padding:5px 10px;border:1px solid rgba(255,226,122,.75);border-radius:999px;margin-bottom:8px}
h1,h2,h3{line-height:1.2}
h2{margin-top:.4rem}
[data-testid="stSidebar"] [data-testid="stRadio"] label{font-weight:650;border-radius:12px;padding:10px 12px}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:rgba(255,201,40,.24);border-color:#ffc928;box-shadow:inset 3px 0 0 #ffc928}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,[data-testid="stDateInput"] input,textarea{
  background:#fffdf7!important;border-color:#e8c88c!important;color:#42151a!important
}
[data-baseweb="select"]>div{background:#fffdf7!important;border-color:#e8c88c!important}
[data-testid="stForm"]{box-shadow:0 4px 14px rgba(75,17,23,.045);margin-bottom:.75rem}
[data-testid="stExpander"]{box-shadow:0 3px 10px rgba(75,17,23,.035)}
[data-testid="stMetric"]{min-height:116px;display:flex;flex-direction:column;justify-content:center}
[data-testid="stMetricLabel"] p{font-size:.9rem;font-weight:700}
[data-testid="stMetricValue"]{font-size:clamp(1.45rem,2.2vw,2rem)}
.product-card{min-height:145px;padding:16px;position:relative;transition:transform .15s ease,box-shadow .15s ease}
.product-card h3{font-size:1.55rem;margin:.55rem 0 .35rem;color:#a83f13!important}
.product-card b{font-size:1.04rem;color:#4b1117}
.product-card:hover{transform:translateY(-2px);box-shadow:0 8px 18px rgba(75,17,23,.10)}
.small-note{line-height:1.45}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{font-weight:700;letter-spacing:.005em}
.stButton>button:focus-visible,.stDownloadButton>button:focus-visible{outline:3px solid #ffc928;outline-offset:2px}
[data-testid="stDataFrame"]{background:#fffdf7}
[data-testid="stAlert"]{border:1px solid rgba(75,17,23,.08);box-shadow:0 2px 8px rgba(75,17,23,.025)}
/* Make tables and metrics fit tablets without adding excessive decoration. */
@media (max-width:900px){
  .block-container{padding-left:1rem;padding-right:1rem}
  [data-testid="stMetric"]{min-height:100px;padding:10px}
}
@media (max-width:600px){
  .brand-title{font-size:1.8rem;line-height:1.1}
  .brand-sub{font-size:.9rem}
  .brand-banner{border-width:3px;padding:15px}
  h2{font-size:1.35rem}
}
/* Top navigation replaces the left sidebar for a wider checkout workspace. */
[data-testid="stSidebar"]{display:none!important}
[data-testid="stSidebarCollapsedControl"]{display:none!important}
.st-key-top_navigation{
  background:linear-gradient(180deg,#fffaf0 0%,#fff0d2 100%);
  border:1px solid #efc777;border-bottom:4px solid #ffc928;border-radius:14px;
  padding:12px 16px 7px;margin:0 0 22px;box-shadow:0 4px 12px rgba(75,17,23,.055)
}
.st-key-top_navigation [data-testid="stRadio"]>label{display:none}
.st-key-top_navigation [data-testid="stRadio"] [role="radiogroup"]{gap:8px;flex-wrap:wrap}
.st-key-top_navigation [data-testid="stRadio"] [role="radio"]{
  border:1px solid #edc47c;border-radius:999px;padding:7px 14px;
  background:#fff8e8;color:#4b1117;font-weight:750;min-height:38px
}
.st-key-top_navigation [data-testid="stRadio"] [role="radio"][aria-checked="true"]{
  background:#4b1117;color:#fff4d8;border-color:#ffc928;box-shadow:inset 0 -3px 0 #ffc928
}
.st-key-top_navigation [data-testid="stRadio"] [role="radio"] div{color:inherit}
.nav-eyebrow{font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#815a4a;margin:0 0 5px 2px}
@media (max-width:900px){.st-key-top_navigation{padding:10px}.st-key-top_navigation [data-testid="stRadio"] [role="radio"]{padding:6px 10px}}
</style>''',unsafe_allow_html=True)

# Storefront-style top header: orange branded background with navigation integrated into it.
st.markdown('''<style>
[data-testid="stHeader"]{background:rgba(255,244,216,.95)!important}
.st-key-site_header{
  background:linear-gradient(105deg,#ef7420 0%,#ff982b 48%,#ed6d19 100%);
  border:2px solid #ffc928;border-bottom:5px solid #ffc928;border-radius:12px;
  padding:10px 16px 8px;margin:0 0 20px;box-shadow:0 5px 0 rgba(75,17,23,.10),inset 0 0 0 1px rgba(255,248,220,.5);
  position:relative;overflow:hidden
}
.st-key-site_header:before{
  content:"";position:absolute;inset:0;pointer-events:none;opacity:.55;
  background-image:radial-gradient(circle,rgba(255,245,210,.55) 0 3px,transparent 4px);
  background-size:34px 34px
}
.st-key-site_header [data-testid="stHorizontalBlock"]{position:relative;z-index:1;align-items:center;gap:.65rem}
.st-key-site_header [data-testid="stImage"] img{border:2px solid #ffc928;border-radius:8px;display:block}
.site-brand-name{color:#fff8e7;font-weight:950;font-size:clamp(1.1rem,1.6vw,1.65rem);line-height:1.1;letter-spacing:-.025em;text-shadow:2px 2px 0 #4b1117,-1px -1px 0 #4b1117}
.site-brand-tag{color:#fff0c9;font-size:.68rem;font-weight:850;letter-spacing:.08em;margin-top:5px;white-space:nowrap}
.site-nav-label{font-size:.61rem;line-height:1.1;font-weight:950;letter-spacing:.13em;color:#fff0c9;margin:0 0 6px 3px;text-transform:uppercase}
.st-key-site_header [data-testid="stRadio"]>label{display:none}
.st-key-site_header [data-testid="stRadio"] [role="radiogroup"]{gap:5px;flex-wrap:wrap;align-items:center}
.st-key-site_header [data-testid="stRadio"] [role="radio"]{
  background:rgba(75,17,23,.12);border:1px solid rgba(255,247,220,.38);border-radius:6px;
  padding:7px 10px;min-height:34px;color:#fff8e7;font-size:.82rem;font-weight:850;white-space:nowrap;
  transition:background .12s ease,border-color .12s ease
}
.st-key-site_header [data-testid="stRadio"] [role="radio"]:hover{background:rgba(75,17,23,.28);border-color:#ffe27a}
.st-key-site_header [data-testid="stRadio"] [role="radio"][aria-checked="true"]{
  background:#4b1117;border-color:#ffe27a;box-shadow:inset 0 -3px 0 #ffc928;color:#fff8e7
}
.st-key-site_header [data-testid="stRadio"] [role="radio"] div,
.st-key-site_header [data-testid="stRadio"] [role="radio"] p{color:inherit!important}
/* The header is the navigation surface, so the old hero banner is no longer needed. */
.brand-banner{display:none}
@media (max-width:1100px){
  .st-key-site_header{padding:10px}
  .st-key-site_header [data-testid="stHorizontalBlock"]{gap:.35rem}
  .site-brand-tag{white-space:normal}
  .st-key-site_header [data-testid="stRadio"] [role="radio"]{padding:6px 8px;font-size:.76rem}
}
@media (max-width:760px){
  .st-key-site_header [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
  .site-brand-name{font-size:1.2rem}
  .st-key-site_header [data-testid="stImage"] img{max-width:90px}
}
</style>''',unsafe_allow_html=True)

try:
    db.init_db()
except Exception as e:
    st.error('Could not initialize the database. Check folder permissions and the application log.')
    logging.exception('Database initialization failed')
    st.stop()

if 'cart' not in st.session_state: st.session_state.cart=LinkedListCart()
if 'last_sale' not in st.session_state: st.session_state.last_sale=None
if 'mode' not in st.session_state: st.session_state.mode='Admin'

st.markdown('<div class="brand-banner"><div class="brand-kicker">Small business · simple records</div><div class="brand-title">Gulps & Grubs POS</div><div class="brand-sub">Warm service. Clear stock. No more handwritten totals.</div></div>',unsafe_allow_html=True)

# Branded horizontal header inspired by the supplied storefront navigation reference.
# The logo, workspace switcher, and page links share one orange header bar.
with st.container(key='site_header'):
    logo_col, brand_col, mode_col, page_col = st.columns([1.05, 1.8, 1.55, 5.2], vertical_alignment='center', gap='small')
    with logo_col:
        st.image(str(APP_DIR / 'brand_logo.jpg'), width=118)
    with brand_col:
        st.markdown('<div class="site-brand-name">Gulps &amp; Grubs</div><div class="site-brand-tag">AT THE GARAGE · POS</div>', unsafe_allow_html=True)
    with mode_col:
        st.markdown('<div class="site-nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        mode=st.radio('Workspace',['Admin','Cashier'],index=0 if st.session_state.get('mode_choice','Admin')=='Admin' else 1,
                      horizontal=True,key='mode_choice',label_visibility='collapsed')
    st.session_state.mode=mode
    with page_col:
        st.markdown('<div class="site-nav-label">NAVIGATION</div>', unsafe_allow_html=True)
        if mode=='Admin':
            page=st.radio('Admin navigation',['Dashboard','Products & Inventory','Sales History','Pickup Queue'],
                          horizontal=True,key='admin_page',label_visibility='collapsed')
        else:
            page=st.radio('Cashier navigation',['New Sale','Last Transaction'],
                          horizontal=True,key='cashier_page',label_visibility='collapsed')
st.caption('Demo mode selector only — it is not secure authentication. Add role-based login before public deployment.')

# Rebuild the AVL tree from SQLite at each run, keeping the database as source of truth.
try: product_tree=rebuild_tree()
except Exception as e:
    safe_error(e); st.stop()

if mode=='Admin' and page=='Dashboard':
    st.subheader('Business overview')
    today=date.today(); start=datetime.combine(today,time.min).isoformat(); end=datetime.combine(today+timedelta(days=1),time.min).isoformat()
    summary=db.sales_summary(start,end)
    all_products=db.list_products(active_only=True)
    low=[p for p in all_products if p['stock']<=p['low_stock_threshold']]
    a,b,c,d=st.columns(4)
    a.metric('Today’s revenue',money(summary['revenue_cents']))
    b.metric('Completed sales',summary['transactions'])
    c.metric('Active products',len(all_products))
    d.metric('Low-stock alerts',len(low),delta='Needs attention' if low else 'Stock looks good',delta_color='inverse' if low else 'normal')
    st.caption('Revenue is the total value of recorded sales, not profit. Product costs and operating expenses are not tracked.')
    left,right=st.columns([1.15,1])
    with left:
        st.markdown('#### Low-stock watch')
        if low:
            st.dataframe(pd.DataFrame([{'Code':p['code'],'Product':p['name'],'Stock':p['stock'],'Alert at':p['low_stock_threshold']} for p in low]),use_container_width=True,hide_index=True)
        else: st.success('No active products are at or below their low-stock threshold.')
    with right:
        st.markdown('#### Recent transactions')
        recent=db.transaction_history()[:6]
        if recent: st.dataframe(pd.DataFrame([{'Sale #':r['id'],'Date':r['created_at'].replace('T',' '),'Total':money(r['total_cents'])} for r in recent]),use_container_width=True,hide_index=True)
        else: st.info('Completed sales will appear here.')
    st.markdown('#### Sales over the last 7 days')
    daily=[]
    for i in range(6,-1,-1):
        day=today-timedelta(days=i); s=datetime.combine(day,time.min).isoformat(); e=datetime.combine(day+timedelta(days=1),time.min).isoformat(); sm=db.sales_summary(s,e)
        daily.append({'Date':day.strftime('%b %d'),'Revenue (₱)':sm['revenue_cents']/100})
    st.bar_chart(pd.DataFrame(daily).set_index('Date'))

elif mode=='Admin' and page=='Products & Inventory':
    st.subheader('Products & inventory')
    tab1,tab2,tab3=st.tabs(['Add product','Edit / deactivate','Restock'])
    with tab1:
        with st.form('add_product_form',clear_on_submit=True):
            c1,c2=st.columns(2)
            #automatic product code generation
            code=c1.text_input('Product code *',placeholder='e.g. DRK-004').strip().upper()
            name=c2.text_input('Product name *',placeholder='e.g. Brown Sugar Latte').strip()
            category=st.selectbox('Category',['Gulps','Grubs','Other'],index=0)
            if category=='Gulps':
                category=st.selectbox('Category',['Milkshake', 'Milktea','Lemonades','Lemonade Slushie','Floats','Coffee'],index=0)
                if category=='Milkshake' or category=='Lemonades' or category=='Lemonade Slushie' or category=='Coffee':
                    size=st.selectbox('Size',['12oz','16oz'],index=1)
                elif category=='Floats':
                    size=st.selectbox('Size',['8oz','12oz','16oz'],index=1)
            c3,c4,c5=st.columns(3)
            price=c3.number_input('Price (₱)',min_value=0.0,max_value=1000000.0,value=50.0,step=0.5,format='%.2f')
            stock=c4.number_input('Starting stock',min_value=0,max_value=1000000,value=0,step=1)
            threshold=c5.number_input('Low-stock alert at',min_value=0,max_value=1000000,value=5,step=1)
            submitted=st.form_submit_button('Add product',type='primary',use_container_width=True)
        if submitted:
            try:
                db.add_product(code,name,category,cents_from_peso(price),int(stock),int(threshold)); st.success(f'{name} added successfully.'); st.rerun()
            except Exception as e: safe_error(e)
    products=db.list_products()
    active=[p for p in products if p['active']]
    with tab2:
        if not products: st.info('Add your first product to begin.')
        else:
            labels={f"{p['code']} — {p['name']} {'(inactive)' if not p['active'] else ''}":p for p in products}
            selected_label=st.selectbox('Select product',list(labels),key='edit_select')
            p=labels[selected_label]
            if p['active']:
                with st.form('edit_product_form'):
                    ec1,ec2=st.columns(2)
                    new_code=ec1.text_input('Product code',value=p['code']).strip().upper()
                    new_name=ec2.text_input('Product name',value=p['name']).strip()
                    new_cat=st.selectbox('Category',['Gulps','Grubs','Other'],index=['Gulps','Grubs','Other'].index(p['category']) if p['category'] in ['Gulps','Grubs','Other'] else 2)
                    ec3,ec4=st.columns(2)
                    new_price=ec3.number_input('Price (₱)',min_value=0.0,max_value=1000000.0,value=p['price_cents']/100,step=0.5,format='%.2f')
                    new_threshold=ec4.number_input('Low-stock alert at',min_value=0,max_value=1000000,value=p['low_stock_threshold'],step=1)
                    save=st.form_submit_button('Save changes',type='primary')
                if save:
                    try: db.update_product(p['id'],new_code,new_name,new_cat,cents_from_peso(new_price),int(new_threshold)); st.success('Product updated.'); st.rerun()
                    except Exception as e: safe_error(e)
                st.warning('Products are deactivated instead of deleted so historical sales remain intact.')
                if st.button('Deactivate selected product',key='deactivate_btn'):
                    try: db.deactivate_product(p['id']); st.success('Product deactivated.'); st.rerun()
                    except Exception as e: safe_error(e)
            else: st.info('This product is inactive and cannot be sold. Its historic transaction details are preserved.')
    with tab3:
        if active:
            options={f"{p['code']} — {p['name']} (stock: {p['stock']})":p for p in active}
            with st.form('restock_form'):
                chosen=st.selectbox('Product to restock',list(options))
                qty=st.number_input('Quantity to add',min_value=1,max_value=1000000,value=1,step=1)
                restock=st.form_submit_button('Record restock',type='primary')
            if restock:
                try: db.restock_product(options[chosen]['id'],int(qty)); st.success('Stock updated.'); st.rerun()
                except Exception as e: safe_error(e)
        else: st.info('Add an active product before restocking.')
    st.markdown('#### Product catalogue')
    search=st.text_input('Search by code or product name',key='product_search')
    shown=[p for p in products if search.casefold() in (p['code']+' '+p['name']).casefold()]
    if shown:
        st.dataframe(pd.DataFrame([{'Code':p['code'],'Product':p['name'],'Category':p['category'],'Price':money(p['price_cents']),'Stock':p['stock'],'Low-stock threshold':p['low_stock_threshold'],'Status':'Active' if p['active'] else 'Inactive'} for p in shown]),use_container_width=True,hide_index=True)
    else: st.info('No products match your search.')
    with st.expander('AVL Tree diagnostic (product codes sorted by the AVL tree)'):
        st.write([p['code'] for p in product_tree.inorder()]); st.caption('The tree is rebuilt from active SQLite products on every app run; product-code search is O(log n) when balanced.')

elif mode=='Admin' and page=='Sales History':
    st.subheader('Sales history')
    c1,c2=st.columns(2); start_date=c1.date_input('From date',value=date.today()-timedelta(days=30)); end_date=c2.date_input('To date',value=date.today())
    if start_date>end_date: st.error('The start date must not be after the end date.')
    else:
        start=datetime.combine(start_date,time.min).isoformat(); end=datetime.combine(end_date+timedelta(days=1),time.min).isoformat()
        rows=db.transaction_history(start,end)
        st.metric('Revenue in selected period',money(sum(r['total_cents'] for r in rows)))
        if rows:
            st.dataframe(pd.DataFrame([{'Sale #':r['id'],'Date/time':r['created_at'].replace('T',' '),'Cashier':r['cashier_label'],'Total':money(r['total_cents'])} for r in rows]),use_container_width=True,hide_index=True)
            chosen=st.selectbox('View sale details',[r['id'] for r in rows],format_func=lambda x:f"Sale #{x}")
            details=db.transaction_items(chosen)
            st.dataframe(pd.DataFrame([{'Code':x['product_code'],'Product':x['product_name'],'Qty':x['quantity'],'Unit price':money(x['unit_price_cents']),'Subtotal':money(x['subtotal_cents'])} for x in details]),use_container_width=True,hide_index=True)
            st.download_button('Download filtered sales CSV',pd.DataFrame([{'sale_id':r['id'],'created_at':r['created_at'],'cashier':r['cashier_label'],'total_php':r['total_cents']/100} for r in rows]).to_csv(index=False).encode('utf-8'),'sales_history.csv','text/csv')
        else: st.info('No transactions were found for the selected dates.')

elif mode=='Admin' and page=='Pickup Queue':
    st.subheader('Scheduled pickup queue')
    st.caption('Priority rule: 1 is most urgent, 5 is least urgent. Orders with equal priority are handled first-in, first-out using their unique sequence number.')
    with st.form('new_order_form',clear_on_submit=True):
        customer=st.text_input('Customer name')
        details=st.text_input('Order details',placeholder='e.g. 2 milk teas, pickup at 4:30 PM')
        priority=st.select_slider('Priority',options=[1,2,3,4,5],value=3,format_func=lambda x:{1:'1 · Urgent',2:'2 · High',3:'3 · Normal',4:'4 · Low',5:'5 · Flexible'}[x])
        add_order_btn=st.form_submit_button('Add pending pickup order',type='primary')
    if add_order_btn:
        try: oid=db.add_order(customer,details,int(priority)); st.success(f'Pickup order #{oid} added.'); st.rerun()
        except Exception as e: safe_error(e)
    heap=rebuild_heap(); next_order=heap.peek()
    if next_order:
        st.info(f"Next order: #{next_order.order_id} · {next_order.payload['customer_name']} · Priority {next_order.priority}")
        if st.button('Mark next order completed',type='primary'):
            try: db.update_order_status(next_order.order_id,'Completed'); st.success(f'Order #{next_order.order_id} completed.'); st.rerun()
            except Exception as e: safe_error(e)
    else: st.success('No pending pickup orders.')
    all_orders=db.list_orders()
    if all_orders:
        st.dataframe(pd.DataFrame([{'Order #':o['id'],'Customer':o['customer_name'],'Details':o['details'],'Priority':o['priority'],'Status':o['status'],'Created':o['created_at'].replace('T',' ')} for o in all_orders]),use_container_width=True,hide_index=True)
    with st.expander('Heap order diagnostic'):
        st.write([{'order_id':e.order_id,'priority':e.priority,'sequence':e.sequence} for e in heap.ordered_entries()]); st.caption('Heap insert and extract are O(log n); viewing the top item is O(1).')

elif mode=='Cashier' and page=='New Sale':
    st.subheader('New sale')
    products=db.list_products(active_only=True)
    left,right=st.columns([1.35,1],gap='large')
    with left:
        st.markdown('#### Available products')
        query=st.text_input('Find a product',placeholder='Search product name or code')
        # Product lookup goes through the manually implemented AVL tree.
        if query.strip():
            match=product_tree.search(query.strip())
            shown=[match] if match else [p for p in products if query.casefold() in (p['name']+' '+p['code']).casefold()]
        else: shown=products
        if not shown: st.info('No matching active products.')
        for start_idx in range(0,len(shown),2):
            cols=st.columns(2)
            for col,p in zip(cols,shown[start_idx:start_idx+2]):
                with col:
                    st.markdown(f"<div class='product-card'><b>{p['name']}</b><br><span class='small-note'>{p['code']} · {p['category']}</span><h3>{money(p['price_cents'])}</h3><span class='small-note'>In stock: {p['stock']}</span></div>",unsafe_allow_html=True)
                    with st.form(f"add_cart_{p['id']}"):
                        qty=st.number_input('Qty',min_value=1,max_value=max(1,int(p['stock'])),value=1,step=1,key=f"qty_{p['id']}",disabled=p['stock']<1)
                        add=st.form_submit_button('Add to cart',use_container_width=True,disabled=p['stock']<1)
                    if add:
                        try:
                            if qty>p['stock']: raise ValueError(f"Only {p['stock']} unit(s) are in stock.")
                            st.session_state.cart.add(p,int(qty)); st.success(f"Added {qty} × {p['name']}."); st.rerun()
                        except Exception as e: safe_error(e)
    with right:
        st.markdown('#### Shopping cart')
        cart=st.session_state.cart
        items=cart.items()
        if not items: st.info('Your cart is empty. Add a product to begin.')
        else:
            for item in items:
                with st.container(border=True):
                    c1,c2=st.columns([2,1]); c1.markdown(f"**{item['name']}**\n\n{money(item['unit_price_cents'])} each")
                    c2.markdown(f"**{money(item['subtotal_cents'])}**")
                    qcol,rmcol=st.columns([2,1])
                    new_q=qcol.number_input('Quantity',min_value=1,max_value=1000000,value=int(item['quantity']),step=1,key=f"cart_q_{item['product_id']}")
                    if qcol.button('Update',key=f"update_{item['product_id']}"):
                        try:
                            p=db.get_product(item['product_id'])
                            if not p or not p['active']: raise ValueError('This product is no longer available. Remove it from the cart.')
                            if int(new_q)>p['stock']: raise ValueError(f"Only {p['stock']} unit(s) are in stock.")
                            cart.set_quantity(item['product_id'],int(new_q)); st.rerun()
                        except Exception as e: safe_error(e)
                    if rmcol.button('Remove',key=f"remove_{item['product_id']}"):
                        cart.remove(item['product_id']); st.rerun()
            st.divider(); st.markdown(f"### Total: {money(cart.total_cents())}")
            st.caption('Inventory is checked again at checkout. No stock is deducted until the sale commits successfully.')
            with st.form('checkout_form'):
                cashier_label=st.text_input('Cashier label (optional)',value='Cashier')
                confirm=st.form_submit_button('Confirm sale',type='primary',use_container_width=True)
            if confirm:
                try:
                    sale=db.checkout(cart.items(),cashier_label.strip() or 'Cashier')
                    st.session_state.last_sale=sale; cart.clear(); st.success(f"Sale #{sale['transaction_id']} completed — {money(sale['total_cents'])}."); st.rerun()
                except Exception as e: safe_error(e)
        st.markdown('---')
        st.markdown('**Cart data structure:** custom singly linked list')
        st.caption(f'{len(cart)} distinct item(s) · item lookup O(n) · cart total O(n)')

elif mode=='Cashier' and page=='Last Transaction':
    st.subheader('Last transaction')
    sale=st.session_state.last_sale
    if not sale: st.info('Complete a sale in New Sale to display its details here. For historical records, ask the admin to open Sales History.')
    else:
        st.success(f"Sale #{sale['transaction_id']} · {sale['created_at'].replace('T',' ')}")
        st.metric('Total paid',money(sale['total_cents']))
        st.dataframe(pd.DataFrame([{'Code':x['code'],'Product':x['name'],'Qty':x['quantity'],'Unit price':money(x['unit_price_cents']),'Subtotal':money(x['subtotal_cents'])} for x in sale['items']]),use_container_width=True,hide_index=True)
        st.caption('The database transaction has committed successfully; inventory and transaction history have been updated.')

st.divider()
st.caption('Gulps & Grubs POS · SQLite is the persistent source of truth · Prices stored as integer centavos')
