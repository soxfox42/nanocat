import wx


class Sixel:
    def __init__(self, data):
        self.pixels = []
        lines = data.removesuffix("-").split("-")
        self.width = len(lines[0])
        if any(len(line) != self.width for line in lines):
            raise ValueError("Uneven sixel lines")

        for line in lines:
            for y in range(6):
                for c in line:
                    value = ord(c) - 63
                    pixel = (value >> y) & 1
                    self.pixels.append(pixel)

        self.height = len(self.pixels) // self.width

        self.trim()

    def trim(self):
        top = self.hborder(0, 1)
        bottom = self.hborder(self.height - 1, -1)
        left = self.vborder(0, 1)
        right = self.vborder(self.width - 1, -1)

        result = []
        for y in range(top, bottom + 1):
            start = y * self.width + left
            end = y * self.width + right + 1
            result += self.pixels[start:end]
        self.pixels = result
        self.width = right - left + 1
        self.height = bottom - top + 1

    def hborder(self, start, step):
        y = start
        while 0 <= y < self.height:
            if any(
                pixel == 1
                for pixel in self.pixels[y * self.width : (y + 1) * self.width]
            ):
                return y
            y += step

    def vborder(self, start, step):
        x = start
        while 0 <= x < self.width:
            if any(pixel == 1 for pixel in self.pixels[x :: self.width]):
                return x
            x += step

    def dump(self):
        chars = " ▄▀█"
        i = 0
        while i < len(self.pixels):
            for x in range(self.width):
                upper = self.pixels[i + x]
                if i + x + self.width < len(self.pixels):
                    lower = self.pixels[i + x + self.width]
                else:
                    lower = 0
                pair = upper << 1 | lower
                print(chars[pair], end="")
            print()
            i += self.width * 2

    def to_wx_image(self):
        dark = wx.SystemSettings.GetAppearance().IsDark()

        rgb_data = []
        alpha_data = []
        for pixel in self.pixels:
            if not dark:
                pixel = 1 - pixel
            rgb_data += [pixel * 255] * 3
            alpha_data.append(pixel * 255)
        return wx.Image(self.width, self.height, bytes(rgb_data), bytes(alpha_data))
