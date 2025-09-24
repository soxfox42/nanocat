from client import NanocatClient
from pathlib import Path
import re
import sys
import wx
import wx.richtext

from sixel import Sixel


POLL_TIME_MS = 100

SIXEL_REGEX = re.compile(r"\\\(([^)]+)\)")

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    bundle_dir = Path(sys._MEIPASS)
else:
    bundle_dir = Path(__file__).parent


# https://en.wikipedia.org/wiki/HSL_and_HSV#HSV_to_RGB
def hsv_to_rgb(h, s, v):
    h %= 360
    h /= 60
    c = v * s
    x = c * (1 - abs(h % 2 - 1))
    m = v - c
    if h < 1:
        r, g, b = c, x, 0
    elif h < 2:
        r, g, b = x, c, 0
    elif h < 3:
        r, g, b = 0, c, x
    elif h < 4:
        r, g, b = 0, x, c
    elif h < 5:
        r, g, b = x, 0, c
    elif h < 6:
        r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


class NanocatFrame(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Nanocat", size=(800, 600), *args, **kwargs)
        self.SetIcon(wx.Icon(str(bundle_dir / "icon.png")))

        self.initialised = False
        self.nick_colours = {}

        panel = wx.Panel(self)
        self.motd_label = wx.StaticText(panel, label="MOTD: none yet")
        self.rich_text = wx.richtext.RichTextCtrl(panel, style=wx.richtext.RE_READONLY)
        self.text_entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.send_button = wx.Button(panel, label="Send")

        self.rich_text.Bind(wx.EVT_SET_FOCUS, self.focus_text_entry)
        self.text_entry.Bind(wx.EVT_TEXT_ENTER, self.send_message)
        self.send_button.Bind(wx.EVT_BUTTON, self.send_message)
        self.Bind(wx.EVT_CLOSE, self.quit)

        sizer = wx.GridBagSizer(8, 8)
        sizer.Add(self.motd_label, (0, 0))
        sizer.Add(self.rich_text, (1, 0), (1, 2), flag=wx.EXPAND)
        sizer.Add(self.text_entry, (2, 0), flag=wx.EXPAND)
        sizer.Add(self.send_button, (2, 1))
        sizer.AddGrowableCol(0)
        sizer.AddGrowableRow(1)

        outer = wx.BoxSizer()
        outer.Add(sizer, 1, flag=wx.EXPAND | wx.ALL, border=8)
        panel.SetSizer(outer)

        dialog = wx.TextEntryDialog(self, "Enter username:", "Nanocat")
        if dialog.ShowModal() != wx.ID_OK:
            self.Destroy()
            return
        username = dialog.Value
        dialog.Destroy()

        if len(sys.argv) >= 2:
            self.client = NanocatClient(address=sys.argv[1], username=username)
        else:
            self.client = NanocatClient(username=username)
        for message in self.client.initial_messages[-200:]:
            self.add_message(message)
        wx.CallAfter(lambda: self.rich_text.ScrollIntoView(self.rich_text.CaretPosition, wx.WXK_PAGEDOWN))

        self.poll_timer = wx.Timer()
        self.poll_timer.Bind(wx.EVT_TIMER, self.poll)
        self.poll_timer.Start(POLL_TIME_MS)

        self.text_entry.SetFocus()

        self.initialised = True

    def focus_text_entry(self, _):
        self.text_entry.SetFocus()

    def poll(self, _):
        for message in self.client.receive_messages():
            self.add_message(message)

    def get_nick_colour(self, nick):
        if nick not in self.nick_colours:
            nick_sum = 0
            for c in nick:
                nick_sum *= 31
                nick_sum += ord(c)
            self.nick_colours[nick] = hsv_to_rgb(nick_sum, 0.5, 0.8)
        return self.nick_colours[nick]

    def write_text_sixel(self, rich_text, text):
        i = 0
        for match in SIXEL_REGEX.finditer(text):
            start, end = match.span()
            if start != i:
                rich_text.WriteText(text[i:start])
            i = end
            try:
                image = Sixel(match[1]).to_wx_image()
                rich_text.WriteImage(image)
            except ValueError:
                rich_text.WriteText("[invalid sixel]")
        rich_text.WriteText(text[i:])

    def add_message(self, message):
        if message.startswith("MOTD "):
            self.show_motd(message[5:])
            return

        self.rich_text.SetInsertionPointEnd()
        at_end = self.rich_text.IsPositionVisible(-1)

        if ":" in message:
            username, message = message.split(":", 1)
            self.rich_text.BeginBold()
            if username != self.client.username:
                self.rich_text.BeginTextColour(self.get_nick_colour(username))
            self.write_text_sixel(self.rich_text, username + ":")
            self.rich_text.EndAllStyles()
        else:
            self.rich_text.BeginItalic()
        self.write_text_sixel(self.rich_text, message + "\n")
        self.rich_text.EndAllStyles()

        if at_end:
            self.rich_text.ScrollIntoView(self.rich_text.CaretPosition, wx.WXK_PAGEDOWN)

    def send_message(self, _):
        message = self.text_entry.Value
        self.text_entry.Value = ""

        if not message:
            return
        if message.startswith("/me "):
            action = message[4:]
            self.client.send_action(action)
        elif message.startswith("/motd "):
            motd = message[6:]
            self.client.send_motd(motd)
        else:
            self.client.send_message(message)

    def show_motd(self, motd):
        self.motd_label.Label = f"MOTD: {motd}"

    def quit(self, _):
        self.client.quit()
        self.poll_timer.Stop()
        self.Destroy()


if __name__ == "__main__":
    app = wx.App()
    frame = NanocatFrame(None)
    if frame.initialised:
        frame.Show()
        app.MainLoop()
