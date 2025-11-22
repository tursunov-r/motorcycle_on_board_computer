import time
import s3lcd

from fonts import vga2_bold_16x32 as big
from tft_drivers.tft_buttons import Buttons

from functions.handlers import (
    get_transmission,
    get_speed,
    get_voltage,
    get_trip_km,
    get_fuel_level,
    get_remaining_range,
    read_time,
    humidity,
    temperature,
)
from functions.markup import *
from functions.menu import show_menu
from functions.brightness_control import update_brightness

markup = Markup()

btn_select = Buttons().left
btn_next = Buttons().right

hold_start = None


def wait_for_both_pressed(timeout=5000):
    """Неблокирующая проверка — возвращает True, если удерживают обе кнопки timeout мс"""
    global hold_start
    if not btn_select.value() and not btn_next.value():
        if hold_start is None:
            hold_start = time.ticks_ms()
        elif time.ticks_diff(time.ticks_ms(), hold_start) > timeout:
            tft.fill(s3lcd.BLACK)
            markup.center(big, "Release the buttons")
            tft.show()
            time.sleep_ms(800)
            hold_start = None
            return True
    else:
        hold_start = None
    return False


def main():
    tft.init()
    tft.fill(s3lcd.BLACK)
    tft.rotation(3)
    tft.show()
    for pos in range(tft.height(), 0):
        tft.png("pictures/logo.png", pos, pos)
        tft.show()
    time.sleep(3)
    tft.fill(s3lcd.BLACK)
    tft.png("pictures/background_n.png", 0, 0)
    tft.show()
    while True:
        update_brightness()
        if wait_for_both_pressed():
            while not btn_select.value() or not btn_next.value():
                time.sleep_ms(200)
            show_menu()
            tft.png("pictures/background_n.png", 0, 0)
            tft.show()
        current_speed = get_speed()
        current_transmission = get_transmission()
        markup.center(big, f"{read_time()}")
        tft.fill_rect(26, 1, 80, big.HEIGHT, s3lcd.YELLOW)
        tft.fill_rect(144, 4, 32, big.HEIGHT, s3lcd.WHITE)
        tft.fill_rect(124, 170 - big.HEIGHT, 64, big.HEIGHT, s3lcd.WHITE)
        markup.top_left(
            big, f"{get_fuel_level()}L", s3lcd.BLACK, s3lcd.YELLOW, 26, 1
        )
        markup.left_center(big, f"{get_trip_km()}")
        markup.top_right(
            big, f"{get_voltage()}v", s3lcd.BLACK, s3lcd.GREEN, -40, -1
        )
        markup.right_center(big, f"{humidity()}")
        markup.bottom_right(
            big, f"{temperature()}", s3lcd.BLACK, s3lcd.CYAN, -27, -1
        )
        markup.bottom_left(
            big,
            f"{get_remaining_range()}km",
            s3lcd.BLACK,
            s3lcd.RED,
            26,
            -1,
        )
        markup.top_center(
            big,
            f"{current_transmission}",
            s3lcd.BLACK,
            s3lcd.WHITE,
            oy=4,
            ox=0,
        )
        markup.bottom_center(big, f"{current_speed}", s3lcd.BLACK, s3lcd.WHITE)
        tft.show()


main()
