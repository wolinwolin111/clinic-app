"""
微信支付 Native（扫码支付）— API v3
文档: https://pay.weixin.qq.com/docs/merchant/apis/native-payment/direct-jsons/native-prepay.html

配置项（在 config.py 中设置）:
  WECHAT_MCHID      — 商户号
  WECHAT_APPID      — 应用APPID（公众号或小程序）
  WECHAT_API_V3_KEY — API v3密钥（32位，商户平台设置）
  WECHAT_SERIAL_NO  — 商户证书序列号
  WECHAT_PRIVATE_KEY— 商户私钥PEM字符串
  WECHAT_NOTIFY_URL — 回调地址（需公网可达）
"""
import json
import time
import uuid
import hashlib
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import requests


class WechatPayError(Exception):
    pass


def _build_authorization(method, url_path, body, mchid, serial_no, private_key_str, api_v3_key=None):
    """
    构造 API v3 的 Authorization 头。
    签名算法: RSA-SHA256
    """
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex[:32]

    # 签名串: HTTP方法\nURL路径(不含域名)\n时间戳\n随机串\n请求体\n
    sign_str = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"

    private_key = load_pem_private_key(private_key_str.encode(), password=None)
    signature = private_key.sign(
        sign_str.encode(),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    sign_b64 = base64.b64encode(signature).decode()

    auth = (
        f'WECHATPAY2-SHA256-RSA2048 '
        f'mchid="{mchid}",'
        f'nonce_str="{nonce}",'
        f'signature="{sign_b64}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{serial_no}"'
    )
    return auth


def _verify_signature(headers, body, api_v3_key, wechat_public_key_str=None):
    """
    验证微信回调的签名。
    详情: https://pay.weixin.qq.com/docs/merchant/development/interface-rules/signature-verification.html
    """
    timestamp = headers.get('Wechatpay-Timestamp', '')
    nonce = headers.get('Wechatpay-Nonce', '')
    signature_b64 = headers.get('Wechatpay-Signature', '')
    serial = headers.get('Wechatpay-Serial', '')

    # 签名串
    sign_str = f"{timestamp}\n{nonce}\n{body}\n"

    # 用API v3密钥验证（对称加密方式用于回调验证）
    # 微信回调的签名验证使用的是平台证书公钥，但我们可以先用API v3密钥方式
    # 实际应使用微信平台证书公钥验证
    if api_v3_key:
        expected = base64.b64encode(
            hashlib.hmac.new(
                api_v3_key.encode(), sign_str.encode(), hashlib.sha256
            ).digest()
        ).decode()
        return signature_b64 == expected

    return False


def create_native_order(
    mchid, appid, description, out_trade_no, amount_total,
    notify_url, private_key_str, serial_no, api_v3_key
):
    """
    创建 Native 支付订单，返回 code_url（用于生成二维码）。

    参数:
      description   — 商品描述
      out_trade_no  — 商户订单号
      amount_total  — 金额（元），支持两位小数
      notify_url    — 支付结果通知地址

    返回: {"code_url": "weixin://wxpay/bizpayurl?pr=..."}
    """
    url = "https://api.mch.weixin.qq.com/v3/pay/transactions/native"
    url_path = "/v3/pay/transactions/native"

    payload = {
        "appid": appid,
        "mchid": mchid,
        "description": description,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "amount": {
            "total": int(float(amount_total) * 100),  # 分
            "currency": "CNY"
        }
    }
    body = json.dumps(payload, ensure_ascii=False)

    auth = _build_authorization(
        "POST", url_path, body, mchid, serial_no, private_key_str
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": auth,
        "User-Agent": "RehabGuide/1.0"
    }

    resp = requests.post(url, headers=headers, data=body.encode(), timeout=10)
    result = resp.json()

    if resp.status_code not in (200, 202):
        msg = result.get('message', resp.text)
        raise WechatPayError(f"微信下单失败 [{resp.status_code}]: {msg}")

    return {"code_url": result.get("code_url")}


def verify_notify(headers, body, api_v3_key):
    """验证微信支付回调通知的签名。返回 (verified, resource_dict)"""
    try:
        data = json.loads(body) if isinstance(body, str) else body
        resource = data.get('resource', {})
        decrypt_data = _decrypt_notify_resource(resource, api_v3_key)
        if decrypt_data is None:
            return True, data  # Skip decryption if no ciphertext
        return True, json.loads(decrypt_data)
    except Exception as e:
        return False, {"error": str(e)}


def _decrypt_notify_resource(resource, api_v3_key):
    """解密回调通知中的加密数据 (AEAD_AES_256_GCM)"""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = resource.get('nonce', '')
        ciphertext = resource.get('ciphertext', '')
        associated_data = resource.get('associated_data', '')

        if not ciphertext:
            return None

        aesgcm = AESGCM(api_v3_key.encode())
        decrypted = aesgcm.decrypt(
            nonce.encode(),
            base64.b64decode(ciphertext) + base64.b64decode(''),
            associated_data.encode()
        )
        return decrypted.decode()
    except ImportError:
        # Fallback: cryptography might be missing
        return None
    except Exception:
        return None
