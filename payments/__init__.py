"""
统一支付接口 — 封装微信支付和支付宝，提供一致的调用方式。

用法:
  from payments import PaymentGateway

  gw = PaymentGateway(app.config)

  # 创建微信扫码订单
  result = gw.create_order('wechat', description='ACL康复指南',
                           out_trade_no='RG001', amount=29.9)

  # 创建支付宝支付
  result = gw.create_order('alipay', description='ACL康复指南',
                           out_trade_no='RG001', amount=29.9)
"""
from . import wechat_pay
from . import alipay


class PaymentGateway:
    """统一支付网关"""

    def __init__(self, config: dict):
        self.config = config
        self._wechat_available = all([
            config.get('WECHAT_MCHID'),
            config.get('WECHAT_APPID'),
            config.get('WECHAT_API_V3_KEY'),
            config.get('WECHAT_SERIAL_NO'),
            config.get('WECHAT_PRIVATE_KEY'),
        ])
        self._alipay_available = all([
            config.get('ALIPAY_APP_ID'),
            config.get('ALIPAY_APP_PRIVATE_KEY'),
            config.get('ALIPAY_PUBLIC_KEY'),
        ])

    @property
    def wechat_available(self) -> bool:
        return self._wechat_available

    @property
    def alipay_available(self) -> bool:
        return self._alipay_available

    def create_order(self, channel: str, description: str,
                     out_trade_no: str, amount: float) -> dict:
        """
        创建支付订单。

        参数:
          channel      — 'wechat' 或 'alipay'
          description  — 商品描述
          out_trade_no — 商户订单号（唯一）
          amount       — 金额（元）

        返回:
          微信: {"channel": "wechat", "code_url": "weixin://..."}
          支付宝: {"channel": "alipay", "pay_url": "https://openapi.alipay.com/..."}
        """
        if channel == 'wechat':
            if not self._wechat_available:
                raise ValueError("微信支付未配置（缺少商户凭证）")
            result = wechat_pay.create_native_order(
                mchid=self.config['WECHAT_MCHID'],
                appid=self.config['WECHAT_APPID'],
                description=description,
                out_trade_no=out_trade_no,
                amount_total=amount,
                notify_url=self.config['WECHAT_NOTIFY_URL'],
                private_key_str=self.config['WECHAT_PRIVATE_KEY'],
                serial_no=self.config['WECHAT_SERIAL_NO'],
                api_v3_key=self.config['WECHAT_API_V3_KEY'],
            )
            result['channel'] = 'wechat'
            return result

        elif channel == 'alipay':
            if not self._alipay_available:
                raise ValueError("支付宝未配置（缺少商户凭证）")
            result = alipay.create_page_pay(
                app_id=self.config['ALIPAY_APP_ID'],
                subject=description,
                out_trade_no=out_trade_no,
                total_amount=amount,
                notify_url=self.config.get('ALIPAY_NOTIFY_URL', ''),
                return_url=self.config.get('ALIPAY_RETURN_URL', ''),
                private_key_str=self.config['ALIPAY_APP_PRIVATE_KEY'],
            )
            result['channel'] = 'alipay'
            return result

        else:
            raise ValueError(f"不支持的支付渠道: {channel}")

    def verify_wechat_notify(self, headers: dict, body: str) -> tuple:
        """验证微信支付回调，返回 (valid, order_data)"""
        return wechat_pay.verify_notify(
            headers, body,
            self.config.get('WECHAT_API_V3_KEY', '')
        )

    def verify_alipay_notify(self, params: dict) -> tuple:
        """验证支付宝回调，返回 (valid, order_data)"""
        return alipay.verify_notify(
            params,
            self.config.get('ALIPAY_PUBLIC_KEY', '')
        )
