import s3lcd
from fonts import vga2_bold_16x32 as big
from tft_drivers.tft_buttons import Buttons
from functions.handlers import *
from functions.markup import *

btn_select = Buttons().left
btn_next = Buttons().right

markup = Markup()

MENU_ITEMS = [
    "Time",
    "FUEL calibration",
    "Reset Trip",
]


# =============== INACTION TRACKING FUNCTION ===============
def show_menu(timeout=2000):
    """main menu with auto-exit"""
    index = 0
    tft.fill(s3lcd.BLACK)

    last_action = time.ticks_ms()  # mark last active

    while True:
        # --- check timeout inactive ---
        if time.ticks_diff(time.ticks_ms(), last_action) > timeout:
            tft.fill(s3lcd.BLACK)
            markup.center(big, "Exit menu", s3lcd.BLACK, s3lcd.RED)
            tft.show()
            time.sleep(1)
            break  # exite in main

        # --- draw menu ---
        tft.fill(s3lcd.BLACK)
        markup.top_left(big, "Menu", s3lcd.WHITE)
        for i, item in enumerate(MENU_ITEMS):
            color = s3lcd.YELLOW if i == index else s3lcd.WHITE
            tft.text(big, item, 10, 50 + i * 40, color)
        tft.show()

        # --- next ---
        if btn_next.value() == 0:
            index = (index + 1) % len(MENU_ITEMS)
            last_action = time.ticks_ms()  # update timer
            time.sleep_ms(200)
            while btn_next.value() == 0:
                time.sleep_ms(200)

        # --- item selection  ---
        if btn_select.value() == 0:
            last_action = time.ticks_ms()
            if MENU_ITEMS[index] == "Time":
                menu_set_time()  # get timeout
            elif MENU_ITEMS[index] == "Reset Trip":
                menu_reset_trip()
            elif MENU_ITEMS[index] == "FUEL calibration":
                menu_fuel_calibration()

            # wait release the buttons
            while btn_select.value() == 0 or btn_next.value() == 0:
                time.sleep_ms(200)

            last_action = time.ticks_ms()


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
        if field == 0:
            display_time = f"[{hour:02}]:{minute:02}"
        else:
            display_time = f"{hour:02}:[{minute:02}]"

        markup.center(big, display_time, s3lcd.YELLOW)
        markup.top_left(big, "SET Time", s3lcd.WHITE)
        tft.show()

        # timeout inactive
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

        # --- auto-exit if inactive ---
        if time.ticks_diff(time.ticks_ms(), last_action) > 8000:
            tft.fill(s3lcd.BLACK)
            markup.center(big, "Exit fuel menu", s3lcd.RED)
            tft.show()
            time.sleep(1)
            return

        # --- switch step ---
        if not btn_next.value():
            step = 1 - step  # switch EMPTY / FULL
            last_action = time.ticks_ms()
            time.sleep_ms(250)

        # --- Confirm calibrate ---
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
            # wait replace, for not active repeat
            while not btn_select.value():
                time.sleep_ms(50)

            if confirm:
                # ⚠️ Safe reset: stop timer -> write -> start timer
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
