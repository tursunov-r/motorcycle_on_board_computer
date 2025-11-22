import time

import s3lcd
from fonts import vga2_bold_16x32 as big
from functions.handlers import (
    calibrate_empty,
    calibrate_full,
    pause_trip_timer,
    resume_trip_timer,
    rtc,
    set_trip_zero_and_save,
)
from functions.markup import Markup, tft
from tft_drivers.tft_buttons import Buttons

btn_select = Buttons().left
btn_next = Buttons().right

markup = Markup()

MENU_ITEMS = [
    "Time",
    "FUEL calibration",
    "Reset Trip",
]


# --------------------------
# Helper drawing / input
# --------------------------
def draw_menu(index):
    """Draw menu title and items, highlighting current index."""
    tft.fill(s3lcd.BLACK)
    markup.top_left(big, "Menu", s3lcd.WHITE)
    for i, item in enumerate(MENU_ITEMS):
        color = s3lcd.YELLOW if i == index else s3lcd.WHITE
        tft.text(big, item, 10, 50 + i * 40, color)
    tft.show()


def wait_release(button, poll_ms=50):
    """Wait until the specified button is released (debounce)."""
    while button.value() == 0:
        time.sleep_ms(poll_ms)


def any_button_pressed():
    """Return True if any of the two buttons is pressed."""
    return (btn_select.value() == 0) or (btn_next.value() == 0)


# --------------------------
# Menu action dispatch
# --------------------------
_MENU_ACTIONS = {
    "Time": lambda: menu_set_time(),
    "FUEL calibration": lambda: menu_fuel_calibration(),
    "Reset Trip": lambda: menu_reset_trip(),
}


def handle_select(index):
    """Call action for selected menu item (if exists)."""
    key = MENU_ITEMS[index]
    action = _MENU_ACTIONS.get(key)
    if action:
        action()


# --------------------------
# Main menu
# --------------------------
def show_menu(timeout=2000):
    """Main menu with auto-exit (preserves original behavior)."""
    index = 0
    tft.fill(s3lcd.BLACK)
    last_action = time.ticks_ms()

    while True:
        # timeout check
        if time.ticks_diff(time.ticks_ms(), last_action) > timeout:
            tft.fill(s3lcd.BLACK)
            markup.center(big, "Exit menu", s3lcd.BLACK, s3lcd.RED)
            tft.show()
            time.sleep(1)
            break

        # draw
        draw_menu(index)

        # handle next button: advance selection
        if btn_next.value() == 0:
            index = (index + 1) % len(MENU_ITEMS)
            last_action = time.ticks_ms()
            time.sleep_ms(200)
            wait_release(btn_next)
            continue

        # handle select button: execute action
        if btn_select.value() == 0:
            last_action = time.ticks_ms()
            handle_select(index)
            # wait release of either button (original behavior waited both)
            while not btn_select.value() or not btn_next.value():
                time.sleep_ms(200)
            last_action = time.ticks_ms()
            """
            redraw background
            (original code did fill background after return)
            """
            tft.fill(s3lcd.BLACK)

        # small delay to reduce CPU usage and allow responsiveness
        time.sleep_ms(20)


# --------------------------
# Submenus (kept original logic)
# --------------------------
def menu_set_time():
    """set time menu"""
    time.sleep(1)
    tft.fill(s3lcd.BLACK)
    dt = rtc.datetime()
    hour, minute = dt.hour, dt.minute
    field = 0  # 0=hours, 1=minutes
    last_press = time.ticks_ms()

    while True:
        tft.fill(s3lcd.BLACK)
        display_time = (
            f"[{hour:02}]:{minute:02}"
            if field == 0
            else f"{hour:02}:[{minute:02}]"
        )
        markup.center(big, display_time, s3lcd.YELLOW)
        markup.top_left(big, "SET Time", s3lcd.WHITE)
        tft.show()

        # timeout inactive -> save and exit
        if time.ticks_diff(time.ticks_ms(), last_press) > 5000:
            rtc.datetime(
                (dt.year, dt.month, dt.day, dt.weekday, hour, minute, 0, 0)
            )
            tft.fill(s3lcd.BLACK)
            markup.center(big, "SAVE", s3lcd.GREEN)
            tft.show()
            time.sleep(1)
            return

        if not btn_next.value():
            field = 1 - field
            last_press = time.ticks_ms()
            time.sleep_ms(250)

        if not btn_select.value():
            if field == 0:
                hour = (hour + 1) % 24
            else:
                minute = (minute + 1) % 60
            last_press = time.ticks_ms()
            time.sleep_ms(250)


def menu_fuel_calibration():
    """Fuel calibration (EMPTY / FULL)"""
    tft.fill(s3lcd.BLACK)
    markup.center(big, "Fuel calibration", s3lcd.WHITE)
    tft.show()
    time.sleep(1)

    step = 0  # 0 = EMPTY, 1 = FULL
    last_action = time.ticks_ms()

    while True:
        tft.fill(s3lcd.BLACK)

        if step == 0:
            markup.center(big, "[EMPTY]", s3lcd.YELLOW)
            markup.top_left(big, "Press SEL to save", s3lcd.WHITE)
        else:
            markup.center(big, "[FULL]", s3lcd.CYAN)
            markup.top_left(big, "Press SEL to save", s3lcd.WHITE)

        markup.bottom_left(big, "NEXT -> switch", s3lcd.WHITE)
        tft.show()

        # auto-exit if inactive
        if time.ticks_diff(time.ticks_ms(), last_action) > 8000:
            tft.fill(s3lcd.BLACK)
            markup.center(big, "Exit fuel menu", s3lcd.RED)
            tft.show()
            time.sleep(1)
            return

        # switch step
        if not btn_next.value():
            step = 1 - step
            last_action = time.ticks_ms()
            time.sleep_ms(250)

        # confirm calibrate
        if not btn_select.value():
            if step == 0:
                calibrate_empty()
                tft.fill(s3lcd.BLACK)
                markup.center(big, "EMPTY SAVED", s3lcd.GREEN)
                tft.show()
                time.sleep(1)
            else:
                calibrate_full()
                tft.fill(s3lcd.BLACK)
                markup.center(big, "FULL SAVED", s3lcd.GREEN)
                tft.show()
                time.sleep(1)

            last_action = time.ticks_ms()
            time.sleep_ms(250)


def menu_reset_trip():
    """reset trip"""
    tft.fill(s3lcd.BLACK)
    markup.center(big, "Reset Trip?", s3lcd.WHITE)
    tft.show()
    time.sleep(1)

    confirm = False
    last_action = time.ticks_ms()

    while True:
        # auto-exit in 8 seconds inactive
        if time.ticks_diff(time.ticks_ms(), last_action) > 8000:
            return

        tft.fill(s3lcd.BLACK)
        markup.center(
            big,
            "Confirm?" if confirm else "Cancel?",
            s3lcd.YELLOW if confirm else s3lcd.CYAN,
        )
        markup.bottom_left(big, "NEXT -> switch", s3lcd.WHITE)
        tft.show()

        if not btn_next.value():
            confirm = not confirm
            last_action = time.ticks_ms()
            time.sleep_ms(250)
            while not btn_next.value():
                time.sleep_ms(50)

        if not btn_select.value():
            last_action = time.ticks_ms()
            # wait release to prevent accidental repeats
            while not btn_select.value():
                time.sleep_ms(50)

            if confirm:
                # Safe reset: stop timer -> write -> start timer
                pause_trip_timer()
                set_trip_zero_and_save()
                resume_trip_timer()

                tft.fill(s3lcd.BLACK)
                markup.center(big, "Trip Reset!", s3lcd.GREEN)
                tft.show()
                time.sleep_ms(800)
            else:
                tft.fill(s3lcd.BLACK)
                markup.center(big, "Canceled", s3lcd.RED)
                tft.show()
                time.sleep_ms(800)
            return
