import time, dht, ujson
import math
from machine import ADC, I2C, Pin, Timer

import functions.urtc as urtc

# ---------------------- Settings ----------------------
WHEEL_WIDTH = 120  # mm
WHEEL_HEIGHT = 60  # % from width
WHEEL_DIAMETER = 17  # Wheel diameter
FULL_FUEL = 17  # fuel tank capacity
FUEL_FLOW_TRACK = 4
FUEL_FLOW_CITY = 7

WHEEL_CIRCUMFERENCE = math.pi * (
    (WHEEL_DIAMETER * 25.4 + 2 * (WHEEL_WIDTH * WHEEL_HEIGHT / 100)) / 1000
)
PULSES_PER_REV = 1  # number of pulses per wheel revolution
MEASURE_INTERVAL = 1000  # ms
AVERAGE_WINDOW = 5  # speed averaging
SAVE_INTERVAL = 60000  # every 60 seconds save trip
TRIP_FILE = "../trip.json"


# ------------------------- Pins -------------------------
scl_3231 = Pin(43)
sda_3231 = Pin(44)
dht_sensor = dht.DHT11(Pin(21))
fuel = ADC(Pin(1))
voltmetr = ADC(Pin(16))
speed_pin = Pin(17, Pin.IN)

# ---------------------- Speed pins ----------------------
_first = Pin(2, Pin.IN, Pin.PULL_UP)
_second = Pin(3, Pin.IN, Pin.PULL_UP)
_third = Pin(10, Pin.IN, Pin.PULL_UP)
_four = Pin(11, Pin.IN, Pin.PULL_UP)
_five = Pin(12, Pin.IN, Pin.PULL_UP)
_six = Pin(13, Pin.IN, Pin.PULL_UP)

# ---------------------- Globals ----------------------
i2c = I2C(0, scl=scl_3231, sda=sda_3231)
rtc = urtc.DS3231(i2c)
fuel.atten(ADC.ATTN_11DB)
voltmetr.atten(ADC.ATTN_11DB)

_pulse_count = 0
_speed_history = []
_trip_distance = 0.0
_current_speed = 0.0
_last_update = time.ticks_ms()
_last_save = _last_update

# кеши для топлива и запаса хода
_last_fuel = None
_last_range = None


# ---------------------- Service ----------------------
def _on_pulse(pin):
    global _pulse_count
    _pulse_count += 1


speed_pin.irq(trigger=Pin.IRQ_RISING, handler=_on_pulse)

# ---------------------- Fuel Calibrate ----------------------
calib_cache = {"empty": None, "full": None}


def load_calib():
    global calib_cache
    try:
        with open("../fuel_calib.json") as f:
            calib_cache = ujson.load(f)
    except:
        calib_cache = {"empty": None, "full": None}


def save_calib():
    with open("../fuel_calib.json", "w") as f:
        ujson.dump(calib_cache, f)


def calibrate_empty():
    calib_cache["empty"] = fuel.read()
    save_calib()


def calibrate_full():
    calib_cache["full"] = fuel.read()
    save_calib()


# ---------------------- Background update ----------------------
def update_fuel(timer=None):
    global _last_fuel
    e, f = calib_cache.get("empty"), calib_cache.get("full")
    if e is None or f is None or e == f:
        _last_fuel = "not calib"
    else:
        v = fuel.read()
        ratio = (e - v) / (e - f)
        ratio = max(0, min(1, ratio))
        _last_fuel = round(ratio * FULL_FUEL, 1)


def update_range(timer=None):
    global _last_range
    speed = get_speed()
    fuel_val = _last_fuel
    if isinstance(fuel_val, str):
        _last_range = fuel_val
    else:
        consumption = (
            FUEL_FLOW_TRACK
            if speed >= 100
            else FUEL_FLOW_CITY if speed > 0 else FUEL_FLOW_TRACK
        )
        _last_range = round((fuel_val / consumption) * 100, 1)


# ---------------------- Service sensors ----------------------
def read_time():
    dt = rtc.datetime()
    if dt.second % 2 == 0:
        return f"{dt.hour:02}:{dt.minute:02}"
    else:
        return f"{dt.hour:02} {dt.minute:02}"


def temperature():
    try:
        dht_sensor.measure()
        return f"{dht_sensor.temperature():.1f}C"
    except:
        return "err"


def humidity():
    try:
        dht_sensor.measure()
        return f"{dht_sensor.humidity():.1f}"
    except:
        return "err"


def get_voltage():
    v = voltmetr.read() / 4095 * 15 * 1.1
    return round(v, 1)


def get_transmission():
    if _first.value() == 0:
        transmission_value = 1
    elif _second.value() == 0:
        transmission_value = 2
    elif _third.value() == 0:
        transmission_value = 3
    elif _four.value() == 0:
        transmission_value = 4
    elif _five.value() == 0:
        transmission_value = 5
    elif _six.value() == 0:
        transmission_value = 6
    else:
        transmission_value = "N"
    return transmission_value


# ---------------------- Master logic ----------------------
def update_all(timer=None):
    global _pulse_count, _speed_history, _trip_distance, _current_speed, _last_save, _last_update

    revs = _pulse_count / PULSES_PER_REV
    _pulse_count = 0
    dist_m = revs * WHEEL_CIRCUMFERENCE
    _trip_distance += dist_m / 1000

    now = time.ticks_ms()
    dt = time.ticks_diff(now, _last_update) / 1000
    _last_update = now

    if dt > 0:
        sp_mps = dist_m / dt
        sp_kph = round(sp_mps * 3.6, 1)
        _current_speed = sp_kph
        if sp_kph > 0:
            _speed_history.append(sp_kph)
            if len(_speed_history) > AVERAGE_WINDOW:
                _speed_history.pop(0)

    if time.ticks_diff(now, _last_save) > SAVE_INTERVAL:
        save_trip()


_timer = Timer(0)
_timer.init(period=MEASURE_INTERVAL, mode=Timer.PERIODIC, callback=update_all)


# ---------------------- Trip ----------------------
def load_trip():
    global _trip_distance
    try:
        with open(TRIP_FILE) as f:
            _trip_distance = float(ujson.load(f).get("trip", 0))
    except:
        _trip_distance = 0.0


def save_trip():
    global _trip_distance, _last_save
    try:
        with open(TRIP_FILE, "w") as f:
            ujson.dump({"trip": _trip_distance}, f)
        _last_save = time.ticks_ms()
    except:
        pass


def reset_trip():
    global _trip_distance
    _trip_distance = 0.0
    save_trip()


load_trip()


def pause_trip_timer():
    try:
        _timer.deinit()
    except:
        pass


def resume_trip_timer():
    _timer.init(
        period=MEASURE_INTERVAL, mode=Timer.PERIODIC, callback=update_all
    )


def set_trip_zero_and_save():
    global _trip_distance, _last_save
    _trip_distance = 0.0
    try:
        with open(TRIP_FILE, "w") as f:
            ujson.dump({"trip": _trip_distance}, f)
        _last_save = time.ticks_ms()
    except:
        pass


# ---------------------- API ----------------------
def get_speed():
    return (
        int(sum(_speed_history) / len(_speed_history))
        if _speed_history
        else _current_speed
    )


def get_trip_km():
    return round(_trip_distance, 1)


def get_fuel_level():
    return _last_fuel


def get_remaining_range():
    return _last_range


# ---------------------- Timer for background update ----------------------
fuel_timer = Timer(1)
fuel_timer.init(
    period=10000, mode=Timer.PERIODIC, callback=update_fuel
)  # каждые 10 сек

range_timer = Timer(2)
range_timer.init(
    period=5000, mode=Timer.PERIODIC, callback=update_range
)  # каждые 5 сек

# ---------------------- Initialise ----------------------
load_calib()
update_fuel()
update_range()
