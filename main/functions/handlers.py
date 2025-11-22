import math
import time

import dht
import functions.urtc as urtc
import ujson
from machine import ADC, I2C, Pin, Timer

# ======================================================
# Settings
# ======================================================
WHEEL_WIDTH = 120  # mm
WHEEL_HEIGHT = 60  # % of width
WHEEL_DIAMETER = 17  # wheel diameter (inches)
FULL_FUEL = 17  # fuel tank capacity (liters)
FUEL_FLOW_TRACK = 4  # fuel consumption on highway (L/100km)
FUEL_FLOW_CITY = 7  # fuel consumption in city (L/100km)

WHEEL_CIRCUMFERENCE = math.pi * (
    (WHEEL_DIAMETER * 25.4 + 2 * (WHEEL_WIDTH * WHEEL_HEIGHT / 100)) / 1000
)
PULSES_PER_REV = 1  # pulses per wheel revolution
MEASURE_INTERVAL = 1000  # ms
AVERAGE_WINDOW = 5  # speed averaging window size
SAVE_INTERVAL = 60000  # save trip every 60 seconds
TRIP_FILE = "../trip.json"

# ======================================================
# Pins
# ======================================================
scl_3231 = Pin(43)
sda_3231 = Pin(44)
dht_sensor = dht.DHT11(Pin(21))
fuel = ADC(Pin(1))
voltmetr = ADC(Pin(16))
speed_pin = Pin(17, Pin.IN)

# Speed pins (gear detection)
_first = Pin(2, Pin.IN, Pin.PULL_UP)
_second = Pin(3, Pin.IN, Pin.PULL_UP)
_third = Pin(10, Pin.IN, Pin.PULL_UP)
_four = Pin(11, Pin.IN, Pin.PULL_UP)
_five = Pin(12, Pin.IN, Pin.PULL_UP)
_six = Pin(13, Pin.IN, Pin.PULL_UP)

# ======================================================
# Globals
# ======================================================
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

# caches for fuel and range
_last_fuel = None
_last_range = None


# ======================================================
# Interrupts and handlers
# ======================================================
def _on_pulse(pin):
    """Increment pulse count on rising edge from wheel sensor."""
    global _pulse_count
    _pulse_count += 1


# Attach interrupt for speed sensor
speed_pin.irq(trigger=Pin.IRQ_RISING, handler=_on_pulse)

# ======================================================
# Fuel calibration
# ======================================================
calib_cache = {"empty": None, "full": None}


def load_calib():
    """Load fuel calibration values from file."""
    global calib_cache
    try:
        with open("../fuel_calib.json") as f:
            calib_cache = ujson.load(f)
    except FileNotFoundError:
        calib_cache = {"empty": None, "full": None}


def save_calib():
    """Save current fuel calibration values to file."""
    with open("../fuel_calib.json", "w") as f:
        ujson.dump(calib_cache, f)


def calibrate_empty():
    """Store current ADC value as 'empty' level."""
    calib_cache["empty"] = fuel.read()
    save_calib()


def calibrate_full():
    """Store current ADC value as 'full' level."""
    calib_cache["full"] = fuel.read()
    save_calib()


# ======================================================
# Background updates (fuel and range)
# ======================================================
def update_fuel(timer=None):
    """Update cached fuel level based on calibration and ADC reading."""
    global _last_fuel
    e, f = calib_cache.get("empty"), calib_cache.get("full")
    if e is None or f is None or e == f:
        # keep previous value if we already had one, else show status
        _last_fuel = (
            _last_fuel
            if _last_fuel not in (None, "not calib")
            else "not calib"
        )
        return

    v = fuel.read()

    # guard against transient 0/garbage ADC at startup: keep last valid
    min_adc, max_adc = (f, e) if f < e else (e, f)
    if v == 0 or v < (min_adc - 5) or v > (max_adc + 5):
        # if odd reading, do not overwrite a previously valid value
        if isinstance(_last_fuel, (int, float)):
            return

    ratio = (e - v) / (e - f)  # normalize between empty and full
    ratio = max(0, min(1, ratio))  # clamp to [0, 1]
    _last_fuel = round(ratio * FULL_FUEL, 1)


def update_range(timer=None):
    """Update cached remaining range based on fuel level and current speed."""
    global _last_range
    speed = get_speed()
    fuel_val = _last_fuel

    # if fuel is not ready yet, keep previous range
    if not isinstance(fuel_val, (int, float)):
        if isinstance(_last_range, (int, float)):
            return
        _last_range = fuel_val  # propagate status string like "not calib"
        return

    consumption = (
        FUEL_FLOW_TRACK
        if speed >= 100
        else FUEL_FLOW_CITY if speed > 0 else FUEL_FLOW_TRACK
    )
    _last_range = round((fuel_val / consumption) * 100, 1)


# ======================================================
# Service sensors
# ======================================================
def read_time():
    """Return formatted time from RTC with blinking separator."""
    dt = rtc.datetime()
    return (
        f"{dt.hour:02}:{dt.minute:02}"
        if dt.second % 2 == 0
        else f"{dt.hour:02} {dt.minute:02}"
    )


def temperature():
    """Read temperature from DHT sensor; return 'err' if failed."""
    try:
        dht_sensor.measure()
        return f"{dht_sensor.temperature():.1f}C"
    except ValueError:
        return "err"


def humidity():
    """Read humidity from DHT sensor; return 'err' if failed."""
    try:
        dht_sensor.measure()
        return f"{dht_sensor.humidity():.1f}"
    except ValueError:
        return "err"


def get_voltage():
    """Read voltage from ADC and scale to actual value."""
    v = voltmetr.read() / 4095 * 15 * 1.1
    return round(v, 1)


def get_transmission():
    """Detect current gear using dedicated input pins."""
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


# ======================================================
# Master logic (periodic updates)
# ======================================================
def update_all(timer=None):
    """Compute speed, accumulate trip distance, and trigger periodic save."""
    global _pulse_count, _trip_distance, _current_speed, _last_update

    # Convert pulses to distance
    revs = _pulse_count / PULSES_PER_REV
    _pulse_count = 0
    dist_m = revs * WHEEL_CIRCUMFERENCE
    _trip_distance += dist_m / 1000

    # Time delta for speed calculation
    now = time.ticks_ms()
    dt = time.ticks_diff(now, _last_update) / 1000
    _last_update = now

    # Update speed and averaging buffer
    if dt > 0:
        sp_mps = dist_m / dt
        sp_kph = round(sp_mps * 3.6, 1)
        _current_speed = sp_kph
        if sp_kph > 0:
            _speed_history.append(sp_kph)
            if len(_speed_history) > AVERAGE_WINDOW:
                _speed_history.pop(0)

    # Periodic trip save
    if time.ticks_diff(now, _last_save) > SAVE_INTERVAL:
        save_trip()


# Configure periodic timer for main updates
_timer = Timer(0)
_timer.init(period=MEASURE_INTERVAL, mode=Timer.PERIODIC, callback=update_all)


# ======================================================
# Trip persistence
# ======================================================
def load_trip():
    """Load trip distance (km) from file into cache."""
    global _trip_distance
    try:
        with open(TRIP_FILE) as f:
            _trip_distance = float(ujson.load(f).get("trip", 0))
    except FileNotFoundError:
        _trip_distance = 0.0


def save_trip():
    """Persist current trip distance to file and update last save timestamp."""
    global _last_save
    try:
        with open(TRIP_FILE, "w") as f:
            ujson.dump({"trip": _trip_distance}, f)
        _last_save = time.ticks_ms()
    except FileNotFoundError:
        pass


def reset_trip():
    """Reset trip distance to zero and save."""
    global _trip_distance
    _trip_distance = 0.0
    save_trip()


# Initialize trip from storage
load_trip()


def pause_trip_timer():
    """Stop periodic trip updates (timer deinit)."""
    try:
        _timer.deinit()
    except ValueError:
        pass


def resume_trip_timer():
    """Resume periodic trip updates (timer init)."""
    _timer.init(
        period=MEASURE_INTERVAL, mode=Timer.PERIODIC, callback=update_all
    )


def set_trip_zero_and_save():
    """Force set trip to zero and persist immediately."""
    global _trip_distance, _last_save
    _trip_distance = 0.0
    try:
        with open(TRIP_FILE, "w") as f:
            ujson.dump({"trip": _trip_distance}, f)
        _last_save = time.ticks_ms()
    except FileNotFoundError:
        pass


# ======================================================
# API
# ======================================================
def get_speed():
    """Return current speed (averaged if available)."""
    return (
        int(sum(_speed_history) / len(_speed_history))
        if _speed_history
        else _current_speed
    )


def get_trip_km():
    """Return total trip distance in kilometers."""
    return round(_trip_distance, 1)


def get_fuel_level():
    """Return last computed fuel level or status string."""
    return _last_fuel


def get_remaining_range():
    """Return last computed remaining range or status string."""
    return _last_range


# ======================================================
# Timers for background updates
# ======================================================
fuel_timer = Timer(5)
fuel_timer.init(
    period=10000, mode=Timer.PERIODIC, callback=update_fuel
)  # every 10 sec

range_timer = Timer(2)
range_timer.init(
    period=5000, mode=Timer.PERIODIC, callback=update_range
)  # every 5 sec

# ======================================================
# Initialization
# ======================================================
load_calib()

# Prime initial values to avoid zero/None flashes before timers kick in
update_fuel()
update_range()

# Start background timers after initial priming
fuel_timer = Timer(1)
fuel_timer.init(
    period=10000, mode=Timer.PERIODIC, callback=update_fuel
)  # every 10 sec

range_timer = Timer(2)
range_timer.init(
    period=5000, mode=Timer.PERIODIC, callback=update_range
)  # every 5 sec
