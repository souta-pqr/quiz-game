#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GPIO制御モジュール
Raspberry Pi 5対応のGPIO抽象化レイヤー
"""

# GPIO制御のインポート（Raspberry Pi 5対応）
GPIO_AVAILABLE = False
GPIO_LIBRARY = None
lgpio_handle = None

# まずrpi-lgpioを試す（Raspberry Pi 5推奨）
try:
    import RPi.GPIO as GPIO
    # Raspberry Pi 5チェック
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO_AVAILABLE = True
        GPIO_LIBRARY = "RPi.GPIO"
        print("✓ RPi.GPIOを使用します")
    except Exception as e:
        if "SOC peripheral" in str(e):
            # Raspberry Pi 5エラー - lgpioに切り替え
            print(f"⚠️ RPi.GPIOはRaspberry Pi 5で動作しません: {e}")
            GPIO_AVAILABLE = False
        else:
            raise
except ImportError:
    print("⚠️ RPi.GPIOがインポートできません")

# RPi.GPIOが使えない場合、lgpioを試す
if not GPIO_AVAILABLE:
    try:
        import lgpio
        GPIO_AVAILABLE = True
        GPIO_LIBRARY = "lgpio"
        print("✓ lgpioライブラリを使用します (Raspberry Pi 5対応)")
    except ImportError:
        print("⚠️ lgpioが利用できません。ダミーモードで動作します。")
        print("  インストール: pip install rpi-lgpio")

# ===================================
# GPIO設定
# ===================================
START_STOP = 24
RUN_BRAKE = 12
CW_CCW = 14
INT_VR_EXT = 1

ON = 0
OFF = 1


class GPIOWrapper:
    """GPIO操作の抽象化クラス"""
    
    @staticmethod
    def setup_pins():
        """GPIOピンのセットアップ"""
        global lgpio_handle
        
        if not GPIO_AVAILABLE:
            return True
        
        if GPIO_LIBRARY == "RPi.GPIO":
            try:
                GPIO.setup(START_STOP, GPIO.OUT)
                GPIO.setup(RUN_BRAKE, GPIO.OUT)
                GPIO.setup(CW_CCW, GPIO.OUT)
                GPIO.setup(INT_VR_EXT, GPIO.OUT)
                print("✓ RPi.GPIO ピンセットアップ完了")
                return True
            except Exception as e:
                print(f"❌ RPi.GPIO セットアップエラー: {e}")
                return False
        
        elif GPIO_LIBRARY == "lgpio":
            try:
                # gpiochip4 を開く（Raspberry Pi 5）
                lgpio_handle = lgpio.gpiochip_open(4)
                
                # 出力として設定
                lgpio.gpio_claim_output(lgpio_handle, START_STOP)
                lgpio.gpio_claim_output(lgpio_handle, RUN_BRAKE)
                lgpio.gpio_claim_output(lgpio_handle, CW_CCW)
                lgpio.gpio_claim_output(lgpio_handle, INT_VR_EXT)
                
                print("✓ lgpio ピンセットアップ完了 (gpiochip4)")
                return True
            except Exception as e:
                print(f"❌ lgpio セットアップエラー: {e}")
                # gpiochip0を試す
                try:
                    lgpio_handle = lgpio.gpiochip_open(0)
                    lgpio.gpio_claim_output(lgpio_handle, START_STOP)
                    lgpio.gpio_claim_output(lgpio_handle, RUN_BRAKE)
                    lgpio.gpio_claim_output(lgpio_handle, CW_CCW)
                    lgpio.gpio_claim_output(lgpio_handle, INT_VR_EXT)
                    print("✓ lgpio ピンセットアップ完了 (gpiochip0)")
                    return True
                except Exception as e2:
                    print(f"❌ lgpio (gpiochip0) セットアップエラー: {e2}")
                    return False
        
        return False
    
    @staticmethod
    def output(pin, value):
        """GPIO出力"""
        if not GPIO_AVAILABLE:
            return
        
        if GPIO_LIBRARY == "RPi.GPIO":
            GPIO.output(pin, GPIO.LOW if value == ON else GPIO.HIGH)
        
        elif GPIO_LIBRARY == "lgpio":
            if lgpio_handle is not None:
                lgpio.gpio_write(lgpio_handle, pin, value)
    
    @staticmethod
    def cleanup():
        """GPIOクリーンアップ"""
        global lgpio_handle
        
        if not GPIO_AVAILABLE:
            return
        
        if GPIO_LIBRARY == "RPi.GPIO":
            try:
                GPIO.cleanup()
                print("✓ RPi.GPIO クリーンアップ完了")
            except:
                pass
        
        elif GPIO_LIBRARY == "lgpio":
            if lgpio_handle is not None:
                try:
                    lgpio.gpiochip_close(lgpio_handle)
                    lgpio_handle = None
                    print("✓ lgpio クリーンアップ完了")
                except:
                    pass
