"""
支付宝电脑网站支付
文档: https://opendocs.alipay.com/open/270/105898

配置项（在 config.py 中设置）:
  ALIPAY_APP_ID           — 应用APPID
  ALIPAY_APP_PRIVATE_KEY  — 商户私钥PEM字符串
  ALIPAY_PUBLIC_KEY       — 支付宝公钥PEM字符串
  ALIPAY_NOTIFY_URL       — 回调地址（需公网可达）
  ALIPAY_RETURN_URL       — 支付完成跳转地址
"""
import json
import time
import base64
import uuid
from urllib.parse import urlencode
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import requests


ALIPAY_GATEWAY = "https://openapi.alipay.com/gateway.do"


class AlipayError(Exception):
    pass


def _build_sign_string(params):
    """构造待签名字符串（key=value格式，按key字母排序）"""
    sorted_items = sorted(
        (k, v) for k, v in params.items() if v and k not in ('sign', 'sign_type')
    )
    return '&'.join(f'{k}={v}' for k, v in sorted_items)


def _rsa_sign(sign_str, private_key_str):
    """使用RSA-SHA256对字符串签名，返回base64编码的签名"""
    private_key = load_pem_private_key(private_key_str.encode(), password=None)
    signature = private_key.sign(
        sign_str.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode()


def _rsa_verify(sign_str, signature_b64, public_key_str):
    """使用支付宝公钥验证签名"""
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        public_key = load_pem_public_key(public_key_str.encode())
        public_key.verify(
            base64.b64decode(signature_b64),
            sign_str.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def create_page_pay(
    app_id, subject, out_trade_no, total_amount,
    notify_url, return_url, private_key_str
):
    """
    创建电脑网站支付，返回支付页面URL。

    参数:
      subject       — 商品名称
      out_trade_no  — 商户订单号
      total_amount  — 金额（元），支持两位小数
      notify_url    — 支付结果异步通知地址
      return_url    — 支付完成同步跳转地址

    返回: {"pay_url": "https://openapi.alipay.com/gateway.do?..."}
    """
    biz_content = {
        "out_trade_no": out_trade_no,
        "product_code": "FAST_INSTANT_TRADE_PAY",
        "subject": subject,
        "total_amount": str(total_amount),
    }

    params = {
        "app_id": app_id,
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify_url,
        "return_url": return_url,
        "biz_content": json.dumps(biz_content, ensure_ascii=False),
    }

    sign_str = _build_sign_string(params)
    params["sign"] = _rsa_sign(sign_str, private_key_str)

    pay_url = ALIPAY_GATEWAY + "?" + urlencode(params)
    return {"pay_url": pay_url}


def verify_notify(params, public_key_str):
    """
    验证支付宝异步通知的签名。

    参数: params — POST请求的所有参数（dict）
    返回: (verified, trade_data_dict)
    """
    sign = params.get('sign', '')
    sign_type = params.get('sign_type', 'RSA2')

    # 过滤掉sign和sign_type
    verify_params = {k: v for k, v in params.items() if k not in ('sign', 'sign_type')}
    sign_str = _build_sign_string(verify_params)

    verified = _rsa_verify(sign_str, sign, public_key_str)

    trade_data = {
        'out_trade_no': params.get('out_trade_no', ''),
        'trade_no': params.get('trade_no', ''),
        'total_amount': params.get('total_amount', ''),
        'trade_status': params.get('trade_status', ''),
    }

    return verified, trade_data
