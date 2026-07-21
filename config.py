import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask
SECRET_KEY = 'rehab-shop-secret-key-change-in-production'
HOST = '127.0.0.1'
PORT = 3098

# Paths
PRODUCTS_DIR = os.path.join(BASE_DIR, 'products')
DATA_DIR = os.path.join(BASE_DIR, 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
ORDERS_FILE = os.path.join(DATA_DIR, 'orders.json')



# Payment — 微信收款码路径（替换为你的真实收款码图片）
WECHAT_QR_PATH = os.path.join(BASE_DIR, 'static', 'images', 'wechat-qr.png')

# ============================================================
# 微信支付 Native（扫码支付）— API v3
# 获取方式: https://pay.weixin.qq.com → 产品中心 → Native支付
# ============================================================
WECHAT_MCHID = ''              # 商户号（例如: 1234567890）
WECHAT_APPID = ''              # 应用APPID
WECHAT_API_V3_KEY = ''         # API v3密钥（32位，商户平台→API安全→设置）
WECHAT_SERIAL_NO = ''          # 商户证书序列号
WECHAT_PRIVATE_KEY = '''-----BEGIN PRIVATE KEY-----
# 在此粘贴你的商户私钥（apiclient_key.pem 的内容）
-----END PRIVATE KEY-----'''
WECHAT_NOTIFY_URL = 'http://66.154.101.204:3098/payment/notify/wechat'

# ============================================================
# 支付宝电脑网站支付
# 获取方式: https://open.alipay.com → 网页&移动应用
# ============================================================
ALIPAY_APP_ID = ''             # 应用APPID（例如: 2021003xxxxxxxxx）
ALIPAY_APP_PRIVATE_KEY = '''-----BEGIN RSA PRIVATE KEY-----
# 在此粘贴你的应用私钥
-----END RSA PRIVATE KEY-----'''
ALIPAY_PUBLIC_KEY = '''-----BEGIN PUBLIC KEY-----
# 在此粘贴支付宝公钥（从支付宝开放平台下载）
-----END PUBLIC KEY-----'''
ALIPAY_NOTIFY_URL = 'http://66.154.101.204:3098/payment/notify/alipay'
ALIPAY_RETURN_URL = 'http://66.154.101.204:3098/shop'

# Products catalog
PRODUCTS = {
    'acl': {
        'name': 'ACL重建术后康复训练指南',
        'short': 'ACL',
        'desc': '涵盖移植物选择科普、手术方式详解、分阶段训练方案（0-2周至12周+）、健康宣教与预防再损伤指导、进阶评估标准',
        'price': 29.9,
        'icon': '🦵',
        'color': '#3B82F6',
    },
    'meniscus': {
        'name': '半月板术后康复训练指南',
        'short': '半月板',
        'desc': '涵盖半月板缝合与切除两种术式科普、手术知识详解、分阶段训练方案、日常健康宣教与关节保护指导、进阶评估标准',
        'price': 29.9,
        'icon': '🩹',
        'color': '#8B5CF6',
    },
    'acl-meniscus': {
        'name': 'ACL+半月板联合术后康复训练指南',
        'short': 'ACL+半月板',
        'desc': '涵盖联合手术知识科普、两种术式对比详解、分阶段训练方案、术后健康宣教与关节长期保护策略、进阶评估标准',
        'price': 29.9,
        'icon': '🔬',
        'color': '#EC4899',
    },
}


# 支付配置
PAYMENT_METHODS = {
    'wechat': {'name': '微信支付', 'icon': '💬', 'color': '#07C160'},
    'alipay': {'name': '支付宝', 'icon': '🔵', 'color': '#1677FF'},
}