from tft_drivers import tft_config
import s3lcd

tft = tft_config.config(tft_config.WIDE)


class Markup:
    def _draw(self, font, text, fc, bc, x, y):
        tft.text(font, text, x, y, fc, bc)

    def _lenpx(self, font, text):
        return len(text) * font.WIDTH

    # ──────────────── POSITIONS ────────────────

    def top_left(self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK, ox=0, oy=0):
        self._draw(font, text, fc, bc, ox, oy)

    def top_right(
        self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK, ox=0, oy=0
    ):
        x = tft.width() - self._lenpx(font, text) + ox
        y = oy
        self._draw(font, text, fc, bc, x, y)

    def bottom_left(
        self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK, ox=0, oy=0
    ):
        x = ox
        y = tft.height() - font.HEIGHT + oy
        self._draw(font, text, fc, bc, x, y)

    def bottom_right(
        self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK, ox=0, oy=0
    ):
        x = tft.width() - self._lenpx(font, text) + ox
        y = tft.height() - font.HEIGHT + oy
        self._draw(font, text, fc, bc, x, y)

    def center(self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK):
        x = tft.width() // 2 - self._lenpx(font, text) // 2
        y = tft.height() // 2 - font.HEIGHT // 2
        self._draw(font, text, fc, bc, x, y)

    def top_center(
        self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK, ox=0, oy=0
    ):
        x = tft.width() // 2 - self._lenpx(font, text) // 2 + ox
        y = 0 + oy
        self._draw(font, text, fc, bc, x, y)

    def left_center(self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK):
        x = 0
        y = tft.height() // 2 - font.HEIGHT // 2
        self._draw(font, text, fc, bc, x, y)

    def right_center(self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK):
        x = tft.width() - self._lenpx(font, text)
        y = tft.height() // 2 - font.HEIGHT // 2
        self._draw(font, text, fc, bc, x, y)

    def bottom_center(self, font, text, fc=s3lcd.WHITE, bc=s3lcd.BLACK):
        x = tft.width() // 2 - self._lenpx(font, text) // 2
        y = tft.height() - font.HEIGHT
        self._draw(font, text, fc, bc, x, y)
