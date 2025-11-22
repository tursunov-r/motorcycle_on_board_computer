import time

from machine import ADC, PWM, Pin
from tft_drivers.tft_config import BACKLIGHT

PHOTO_PIN = 18
MIN_BRIGHTNESS = 50  # min — background light
MAX_BRIGHTNESS = 1023  # max - background light
UPDATE_INTERVAL = 100  # update every 0.1 seconds
STEP = 50  # step for update

photo_adc = ADC(Pin(PHOTO_PIN))
photo_adc.atten(ADC.ATTN_11DB)
backlight_pwm = PWM(BACKLIGHT)
backlight_pwm.freq(1000)

_last_update = time.ticks_ms()
_current_brightness = 0  # current value PWM


def _map(x, in_min, in_max, out_min, out_max):
    return int(
        (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    )


def update_brightness():
    global _last_update, _current_brightness

    if time.ticks_diff(time.ticks_ms(), _last_update) < UPDATE_INTERVAL:
        return

    light_value = photo_adc.read()  # 0–4095
    target_brightness = _map(
        light_value, 100, 4095, MIN_BRIGHTNESS, MAX_BRIGHTNESS
    )
    target_brightness = max(
        MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, target_brightness)
    )

    # move to current value
    if _current_brightness < target_brightness:
        _current_brightness = min(
            _current_brightness + STEP, target_brightness
        )
    elif _current_brightness > target_brightness:
        _current_brightness = max(
            _current_brightness - STEP, target_brightness
        )

    backlight_pwm.duty(_current_brightness)
    _last_update = time.ticks_ms()


def set_brightness(level):
    global _current_brightness
    _current_brightness = int(max(0, min(1023, level)))
    backlight_pwm.duty(_current_brightness)
