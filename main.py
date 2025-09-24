from client import NanocatClient
import wx
import wx.richtext


POLL_TIME_MS = 100


class NanocatFrame(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Nanocat", size=(800, 600), *args, **kwargs)
        self.SetIcon(wx.Icon("icon.png"))

        panel = wx.Panel(self)
        self.rich_text = wx.richtext.RichTextCtrl(panel, style=wx.richtext.RE_READONLY)
        self.text_entry = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.send_button = wx.Button(panel, label="Send")

        self.rich_text.Bind(wx.EVT_SET_FOCUS, self.focus_text_entry)
        self.text_entry.Bind(wx.EVT_TEXT_ENTER, self.send_message)
        self.send_button.Bind(wx.EVT_BUTTON, self.send_message)
        self.Bind(wx.EVT_CLOSE, self.quit)

        sizer = wx.GridBagSizer(8, 8)
        sizer.AddGrowableCol(0)
        sizer.AddGrowableRow(0)
        sizer.Add(self.rich_text, (0, 0), (1, 2), flag=wx.EXPAND)
        sizer.Add(self.text_entry, (1, 0), flag=wx.EXPAND)
        sizer.Add(self.send_button, (1, 1))

        outer = wx.BoxSizer()
        outer.Add(sizer, 1, flag=wx.EXPAND | wx.ALL, border=8)
        panel.SetSizer(outer)

        dialog = wx.TextEntryDialog(self, "Enter username:", "Nanocat")
        if dialog.ShowModal() != wx.ID_OK:
            self.Destroy()
            return
        username = dialog.Value
        dialog.Destroy()

        self.client = NanocatClient(username=username)

        self.poll_timer = wx.Timer()
        self.poll_timer.Bind(wx.EVT_TIMER, self.poll)
        self.poll_timer.Start(POLL_TIME_MS)

    def focus_text_entry(self, _):
        self.text_entry.SetFocus()

    def poll(self, _):
        for message in self.client.receive_messages():
            self.add_message(message)

    def add_message(self, message):
        self.rich_text.AppendText(message + "\n")
        pos = self.rich_text.GetScrollPos(wx.VERTICAL)
        thumb = self.rich_text.GetScrollThumb(wx.VERTICAL)
        range = self.rich_text.GetScrollRange(wx.VERTICAL)
        if range - (pos + thumb) < 15:
            self.rich_text.ScrollLines(10)

    def send_message(self, _):
        message = self.text_entry.Value
        if not message:
            return
        self.text_entry.Value = ""
        self.client.send_message(message)

    def quit(self, _):
        self.client.quit()
        self.poll_timer.Stop()
        self.Destroy()


if __name__ == "__main__":
    app = wx.App()
    frame = NanocatFrame(None)
    frame.Show()
    app.MainLoop()
