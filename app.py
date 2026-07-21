import os
import json
import hashlib
import uuid
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_file, abort, flash, jsonify
from config import (
    SECRET_KEY, PRODUCTS_DIR, DATA_DIR, USERS_FILE, ORDERS_FILE,
    PRODUCTS,
    PAYMENT_METHODS, WECHAT_QR_PATH, HOST, PORT,
    WECHAT_MCHID, WECHAT_APPID, WECHAT_API_V3_KEY, WECHAT_SERIAL_NO,
    WECHAT_PRIVATE_KEY, WECHAT_NOTIFY_URL,
    ALIPAY_APP_ID, ALIPAY_APP_PRIVATE_KEY, ALIPAY_PUBLIC_KEY,
    ALIPAY_NOTIFY_URL, ALIPAY_RETURN_URL
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Tell Flask all URLs are under /shop/ (for correct url_for generation)
app.config['APPLICATION_ROOT'] = '/shop'


class ScriptNameMiddleware:
    """Ensure SCRIPT_NAME is set so APPLICATION_ROOT works in url_for."""
    def __init__(self, app, script_name='/shop'):
        self.app = app
        self.script_name = script_name

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = self.script_name
        return self.app(environ, start_response)


app.wsgi_app = ScriptNameMiddleware(app.wsgi_app, '/shop')

# Session cookie needs to be set at /shop path since nginx proxies via /shop/
app.config['APPLICATION_ROOT'] = '/shop'
app.config['SESSION_COOKIE_PATH'] = '/shop'

# Payment gateway (lazy init)
_payment_gw = None

def get_payment_gateway():
    global _payment_gw
    if _payment_gw is None:
        from payments import PaymentGateway
        _payment_gw = PaymentGateway({
            'WECHAT_MCHID': WECHAT_MCHID,
            'WECHAT_APPID': WECHAT_APPID,
            'WECHAT_API_V3_KEY': WECHAT_API_V3_KEY,
            'WECHAT_SERIAL_NO': WECHAT_SERIAL_NO,
            'WECHAT_PRIVATE_KEY': WECHAT_PRIVATE_KEY,
            'WECHAT_NOTIFY_URL': WECHAT_NOTIFY_URL,
            'ALIPAY_APP_ID': ALIPAY_APP_ID,
            'ALIPAY_APP_PRIVATE_KEY': ALIPAY_APP_PRIVATE_KEY,
            'ALIPAY_PUBLIC_KEY': ALIPAY_PUBLIC_KEY,
            'ALIPAY_NOTIFY_URL': ALIPAY_NOTIFY_URL,
            'ALIPAY_RETURN_URL': ALIPAY_RETURN_URL,
        })
    return _payment_gw

# ============================================================
# Data helpers
# ============================================================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_orders(orders):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated

def generate_order_id():
    now = datetime.datetime.now()
    suffix = uuid.uuid4().hex[:6].upper()
    return f"RG{now.strftime('%Y%m%d%H%M%S')}{suffix}"


# ============================================================
# Public routes
# ============================================================

def cleanup_temp_files():
    """Delete temp preview files older than 1 hour."""
    cleanup_temp_files()
    temp_dir = os.path.join(DATA_DIR, "temp")
    if not os.path.exists(temp_dir):
        return
    now = datetime.datetime.now()
    for fname in os.listdir(temp_dir):
        fpath = os.path.join(temp_dir, fname)
        age = now - datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
        if age > datetime.timedelta(hours=1):
            os.remove(fpath)


@app.route('/')
def landing():
    return render_template('landing.html', products=PRODUCTS,
                           )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('login.html')

        users = load_users()
        pw_hash = hash_password(password)

        if username in users and users[username]['password'] == pw_hash:
            session['user'] = username
            session['is_admin'] = users[username].get('role') == 'admin'
            flash(f'欢迎回来，{username}！', 'success')
            return redirect(url_for('shop'))

        flash('用户名或密码错误', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()

        if not username or not password:
            flash('请填写所有字段', 'error')
            return render_template('register.html')

        if len(username) < 3 or len(username) > 20:
            flash('用户名需3-20个字符', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('密码至少6个字符', 'error')
            return render_template('register.html')

        if password != confirm:
            flash('两次密码不一致', 'error')
            return render_template('register.html')

        users = load_users()
        if username in users:
            flash('用户名已存在，请直接登录', 'error')
            return render_template('register.html')

        # Create user
        users[username] = {
            'password': hash_password(password),
            'purchases': [],
            'role': 'user',
            'created_at': datetime.datetime.now().isoformat()
        }
        save_users(users)
        session['user'] = username
        session['is_admin'] = False
        flash(f'注册成功，欢迎 {username}！', 'success')
        return redirect(url_for('shop'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    resp = redirect(url_for('landing'))
    resp.delete_cookie('session', path='/shop')
    resp.delete_cookie('session', path='/')
    return resp


# ============================================================
# Shop & Payment routes
# ============================================================
@app.route('/shop')
@login_required
def shop():
    users = load_users()
    user = users.get(session['user'], {})
    purchases = user.get('purchases', [])
    orders = load_orders()
    # Get user's pending orders
    my_orders = {oid: o for oid, o in orders.items()
                 if o['username'] == session['user']}
    return render_template('shop.html', products=PRODUCTS, purchases=purchases,
                                                      username=session['user'], is_admin=session.get('is_admin', False),
                           orders=my_orders)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    product_key = request.form.get('product', '').strip()

    # Determine what user is buying
    if product_key in PRODUCTS:
        p = PRODUCTS[product_key]
        product_name = p['name']
        amount = p['price']
    else:
        flash('无效的产品', 'error')
        return redirect(url_for('shop'))

    order_id = generate_order_id()
    orders = load_orders()
    orders[order_id] = {
        'order_id': order_id,
        'username': session['user'],
        'product': product_key,
        'product_name': product_name,
        'amount': amount,
        'format': 'web',
        'status': 'pending',  # pending → paid → granted
        'created_at': datetime.datetime.now().isoformat(),
        'paid_at': None
    }
    save_orders(orders)
    return redirect(url_for('payment', order_id=order_id))

@app.route('/payment/<order_id>')
@login_required
def payment(order_id):
    orders = load_orders()
    order = orders.get(order_id)
    if not order or order['username'] != session['user']:
        flash('订单不存在', 'error')
        return redirect(url_for('shop'))

    # Check if real payment is configured
    gw = get_payment_gateway()
    wechat_qr_url = None
    alipay_pay_url = None

    if gw.wechat_available:
        try:
            result = gw.create_order(
                'wechat',
                description=order['product_name'],
                out_trade_no=order_id,
                amount=order['amount']
            )
            wechat_qr_url = result.get('code_url')
        except Exception as e:
            wechat_qr_url = f'__ERROR__:{str(e)}'

    if gw.alipay_available:
        try:
            result = gw.create_order(
                'alipay',
                description=order['product_name'],
                out_trade_no=order_id,
                amount=order['amount']
            )
            alipay_pay_url = result.get('pay_url')
        except Exception as e:
            alipay_pay_url = f'__ERROR__:{str(e)}'

    return render_template('payment.html', order=order,
                           payment_methods=PAYMENT_METHODS,
                           wechat_qr_url=wechat_qr_url,
                           alipay_pay_url=alipay_pay_url)

@app.route('/payment/notify/wechat', methods=['POST'])
def wechat_notify():
    """微信支付异步回调 — 服务器自动确认支付"""
    body = request.get_data(as_text=True)
    headers = dict(request.headers)

    gw = get_payment_gateway()
    valid, data = gw.verify_wechat_notify(headers, body)

    if valid and data.get('out_trade_no'):
        order_id = data['out_trade_no']
        _handle_payment_success(order_id)
        return jsonify({"code": "SUCCESS", "message": "OK"})

    return jsonify({"code": "FAIL", "message": "签名验证失败"}), 400


@app.route('/payment/notify/alipay', methods=['POST'])
def alipay_notify():
    """支付宝异步回调 — 服务器自动确认支付"""
    params = dict(request.form)

    gw = get_payment_gateway()
    valid, data = gw.verify_alipay_notify(params)

    if valid and data.get('trade_status') == 'TRADE_SUCCESS':
        order_id = data['out_trade_no']
        _handle_payment_success(order_id)
        return 'success'

    return 'fail'


def _handle_payment_success(order_id):
    """支付成功后的统一处理：更新订单+解锁产品"""
    orders = load_orders()
    order = orders.get(order_id)
    if not order:
        return

    if order['status'] == 'paid':
        return  # Already processed

    order['status'] = 'paid'
    order['paid_at'] = datetime.datetime.now().isoformat()
    orders[order_id] = order
    save_orders(orders)

    # Grant access
    users = load_users()
    username = order['username']
    if username in users:
        purchases = users[username].get('purchases', [])
        product = order['product']
        if product not in purchases:
            purchases.append(product)
            users[username]['purchases'] = purchases
            save_users(users)


@app.route('/simulate-pay/<order_id>')
@login_required
def simulate_pay(order_id):
    """Development helper: simulate payment (grants access instantly)."""
    orders = load_orders()
    order = orders.get(order_id)
    if not order or order['username'] != session['user']:
        flash('订单不存在', 'error')
        return redirect(url_for('shop'))

    # Mark order as paid
    order['status'] = 'paid'
    order['paid_at'] = datetime.datetime.now().isoformat()
    orders[order_id] = order

    # Grant access to the user
    users = load_users()
    username = session['user']
    if username in users:
        purchases = users[username].get('purchases', [])
        if order['product'] not in purchases:
            purchases.append(order['product'])
            users[username]['purchases'] = purchases

    save_orders(orders)
    save_users(users)

    flash('支付成功！已解锁产品，可以立即查看。', 'success')
    return redirect(url_for('shop'))

# ============================================================
# Preview & Download
# ============================================================
@app.route('/preview-free/<condition>')
def preview_free(condition):
    """Free preview — shows display version in iframe with watermark."""
    if condition not in PRODUCTS:
        abort(404)
    display_file = os.path.join(PRODUCTS_DIR, condition, 'display.html')
    if not os.path.exists(display_file):
        abort(404)

    with open(display_file, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inject watermark (generic, no username since not logged in)
    username = session.get('user', '游客')
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    # Generate watermark HTML layers
    wm_layers = ''.join(
        f'<div class="wm-layer wm-{i}">运动康复饶老师</div>'
        for i in [1, 3]
    )
    
    protection = f'''
<style id="rehab-watermark">
.wm-layer {{
    position: fixed; z-index: 9998; pointer-events: none;
    opacity: 0.04; font-size: 100px; font-weight: 900;
    color: #000; white-space: nowrap; user-select: none;
}}
.wm-1 {{ top: 35%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-2 {{ top: 30%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-3 {{ top: 65%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-4 {{ top: 70%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-5 {{ top: 90%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
</style>
{wm_layers}
<script>
(function(){{
    ['contextmenu','copy','cut','selectstart','dragstart'].forEach(function(e){{
        document.addEventListener(e, function(ev){{ ev.preventDefault(); }});
    }});
    document.addEventListener('keydown', function(ev){{
        if(ev.ctrlKey && 'spu'.includes(ev.key.toLowerCase())) ev.preventDefault();
    }});
}})();
</script>
'''
    if '</head>' in html:
        html = html.replace('</head>', protection + '\n</head>')
    elif '<body' in html:
        html = html.replace('<body', protection + '\n<body')

    # Save to temp and serve as file for iframe
    temp_dir = os.path.join(DATA_DIR, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f'preview_{condition}.html')
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return render_template('preview.html', condition=condition,
                           product=PRODUCTS[condition], is_free=True)


@app.route('/preview/<condition>')
@login_required
def preview(condition):
    if condition not in PRODUCTS:
        abort(404)
    users = load_users()
    user = users.get(session['user'], {})
    purchases = user.get('purchases', [])
    is_admin = session.get('is_admin', False)
    has_access = is_admin or condition in purchases
    if not has_access:
        flash('请先购买此产品', 'error')
        return redirect(url_for('shop'))
    return render_template('preview.html', condition=condition,
                           product=PRODUCTS[condition])

def inject_watermark(html):
    """Inject dense dynamic watermark + anti-leak protection."""
    lines = '\\A'.join(['运动康复饶老师'] * 240)

    # Generate watermark HTML layers
    wm_layers = ''.join(
        f'<div class="wm-layer wm-{i}">运动康复饶老师</div>'
        for i in [1, 3]
    )
    
    protection = f'''
<style id="rehab-watermark">
.wm-layer {{
    position: fixed; z-index: 9998; pointer-events: none;
    opacity: 0.04; font-size: 100px; font-weight: 900;
    color: #000; white-space: nowrap; user-select: none;
}}
.wm-1 {{ top: 35%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-2 {{ top: 30%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-3 {{ top: 65%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-4 {{ top: 70%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
.wm-5 {{ top: 90%; left: 50%; transform: translate(-50%, -50%) rotate(-25deg); }}
</style>
{wm_layers}
<script>
(function(){{
    ['contextmenu','copy','cut','selectstart','dragstart'].forEach(function(e){{
        document.addEventListener(e, function(ev){{ ev.preventDefault(); }});
    }});
    document.addEventListener('keydown', function(ev){{
        if(ev.ctrlKey && 'spu'.includes(ev.key.toLowerCase())) ev.preventDefault();
    }});
}})();
</script>
'''

    if '</head>' in html:
        html = html.replace('</head>', protection + '\n</head>')
    elif '<body' in html:
        html = html.replace('<body', protection + '\n<body')
    return html


@app.route('/files-free/<condition>')
def serve_free_display(condition):
    """Serve the watermarked free preview HTML for iframe."""
    if condition not in PRODUCTS:
        abort(404)
    temp_path = os.path.join(DATA_DIR, 'temp', f'preview_{condition}.html')
    if not os.path.exists(temp_path):
        # Regenerate
        display_file = os.path.join(PRODUCTS_DIR, condition, 'display.html')
        if not os.path.exists(display_file):
            abort(404)
        return redirect(url_for('preview_free', condition=condition))
    return send_file(temp_path)


@app.route('/files/<condition>')
@login_required
def serve_display(condition):
    """Serve the FULL HTML with dynamic watermark and protection."""
    if condition not in PRODUCTS:
        abort(404)
    full_file = os.path.join(PRODUCTS_DIR, condition, 'full.html')
    if not os.path.exists(full_file):
        abort(404)

    with open(full_file, 'r', encoding='utf-8') as f:
        html = f.read()

    html = inject_watermark(html)
    from flask import Response
    return Response(html, mimetype='text/html')

@app.route('/download/<condition>/<filetype>')
@login_required
def download(condition, filetype):
    if condition not in PRODUCTS:
        abort(404)
    users = load_users()
    user = users.get(session['user'], {})
    purchases = user.get('purchases', [])
    is_admin = session.get('is_admin', False)
    has_access = is_admin or condition in purchases
    if not has_access:
        flash('请先购买此产品', 'error')
        return redirect(url_for('shop'))

    if filetype == 'html':
        filepath = os.path.join(PRODUCTS_DIR, condition, 'full.html')
        if not os.path.exists(filepath):
            flash('文件暂未生成，请联系管理员', 'error')
            return redirect(url_for('shop'))
        with open(filepath, 'r', encoding='utf-8') as fh:
            html = fh.read()
        html = inject_watermark(html)
        from flask import Response
        from urllib.parse import quote
        safe_name = quote(f'{PRODUCTS[condition]["short"]}_康复指南.html')
        return Response(html, mimetype='text/html',
                        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{safe_name}"})
    else:
        abort(404)




@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = load_users()
    return render_template('admin_users.html', users=users, products=PRODUCTS)


@app.route('/admin/grant', methods=['POST'])
@login_required
@admin_required
def admin_grant():
    username = request.form.get('username')
    condition = request.form.get('condition')
    if not condition:
        flash('请选择要授予的产品', 'error')
        return redirect(url_for('admin_users'))
    users = load_users()
    if username in users:
        if condition not in users[username].get('purchases', []):
            users[username].setdefault('purchases', []).append(condition)
            save_users(users)
            flash(f'已授予 {username} 访问 {condition}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/revoke', methods=['POST'])
@login_required
@admin_required
def admin_revoke():
    username = request.form.get('username')
    condition = request.form.get('condition')
    users = load_users()
    if username in users:
        purchases = users[username].get('purchases', [])
        if condition in purchases:
            purchases.remove(condition)
            users[username]['purchases'] = purchases
            save_users(users)
            flash(f'已撤销 {username} 的 {condition} 访问权', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/add_user', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    purchases = request.form.getlist('purchases')
    if not username or not password:
        flash('用户名和密码不能为空', 'error')
        return redirect(url_for('admin_users'))
    users = load_users()
    users[username] = {
        'password': hash_password(password),
        'purchases': purchases,
        'role': 'user',
        'created_at': datetime.datetime.now().isoformat()
    }
    save_users(users)
    flash(f'用户 {username} 已创建', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user', methods=['POST'])
@login_required
@admin_required
def admin_edit_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    purchases = request.form.getlist('purchases')
    users = load_users()
    if username not in users:
        flash('用户不存在', 'error')
        return redirect(url_for('admin_users'))
    users[username]['purchases'] = purchases
    if password:
        users[username]['password'] = hash_password(password)
    save_users(users)
    flash(f'用户 {username} 已更新', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete/<username>')
@login_required
@admin_required
def admin_delete_user(username):
    if username == 'admin':
        flash('不能删除管理员账号', 'error')
        return redirect(url_for('admin_users'))
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        flash(f'用户 {username} 已删除', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/toggle/<username>')
@login_required
@admin_required
def admin_toggle(username):
    if username == 'admin':
        flash('不能修改管理员账号角色', 'error')
        return redirect(url_for('admin_users'))
    users = load_users()
    if username in users:
        current = users[username].get('role', 'user')
        users[username]['role'] = 'admin' if current == 'user' else 'user'
        save_users(users)
        flash(f'{username} 角色已切换', 'success')
    return redirect(url_for('admin_users'))


# ============================================================
# Admin — Orders
# ============================================================
def to_local_time(iso_str):
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        local_dt = dt + datetime.timedelta(hours=8)
        return local_dt.strftime('%Y-%m-%d %H:%M')
    except:
        return iso_str[:16] if iso_str else '-'


@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    orders = load_orders()
    for oid in orders:
        o = orders[oid]
        o['created_display'] = to_local_time(o.get('created_at', ''))
        o['paid_display'] = to_local_time(o.get('paid_at', '')) if o.get('paid_at') else '-'
    sorted_orders = dict(sorted(
        orders.items(),
        key=lambda x: x[1].get('created_at', ''),
        reverse=True
    ))

    # Compute dashboard stats
    all_orders = list(orders.values())
    paid_orders = [o for o in all_orders if o.get('status') == 'paid']
    total_revenue = sum(o['amount'] for o in paid_orders)
    total_orders = len(all_orders)
    paid_count = len(paid_orders)
    paid_users = len(set(o['username'] for o in paid_orders))
    pending_count = len([o for o in all_orders if o.get('status') == 'pending'])

    # Per-product stats
    product_stats = {}
    for o in paid_orders:
        pname = o.get('product_name', '未知')
        if pname not in product_stats:
            product_stats[pname] = {'count': 0, 'revenue': 0}
        product_stats[pname]['count'] += 1
        product_stats[pname]['revenue'] += o['amount']

    # Total registered users
    users = load_users()
    total_users = len(users)

    stats = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'paid_users': paid_users,
        'total_users': total_users,
        'product_stats': product_stats,
    }

    return render_template('admin_orders.html', orders=sorted_orders, stats=stats)

@app.route('/admin/confirm-payment/<order_id>')
@login_required
@admin_required
def admin_confirm_payment(order_id):
    """Admin confirms a payment — marks order paid and grants access."""
    orders = load_orders()
    order = orders.get(order_id)
    if not order:
        flash('订单不存在', 'error')
        return redirect(url_for('admin_orders'))

    order['status'] = 'paid'
    order['paid_at'] = datetime.datetime.now().isoformat()
    orders[order_id] = order

    # Grant access to the user
    users = load_users()
    username = order['username']
    if username in users:
        purchases = users[username].get('purchases', [])
        product = order['product']
        if product not in purchases:
            purchases.append(product)
            users[username]['purchases'] = purchases
            save_users(users)

    save_orders(orders)
    flash(f'订单 {order_id} 已确认支付，用户 {username} 已解锁产品', 'success')
    return redirect(url_for('admin_orders'))


if __name__ == '__main__':
    from config import HOST, PORT
    app.run(host=HOST, port=PORT, debug=True)
