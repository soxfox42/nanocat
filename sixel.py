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
        width = self.width
        height = len(self.pixels) // width
        rgb_data = []
        alpha_data = []
        for pixel in self.pixels:
            rgb_data += [(1 - pixel) * 255] * 3
            alpha_data.append(pixel * 255)
        return wx.Image(width, height, bytes(rgb_data), bytes(alpha_data))
