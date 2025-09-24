from client import NanocatClient
import wx
import wx.richtext


POLL_TIME_MS = 100


class NanocatFrame(wx.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Nanocat", size=(800, 600), *args, **kwargs)
        self.SetIcon(wx.Icon("icon.png"))

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

        self.client = NanocatClient(username=username)
        filtered_messages = [message for message in self.client.initial_messages if not message.startswith("MOTD ")]
        self.rich_text.AppendText("\n".join(filtered_messages) + "\n")
        self.rich_text.ScrollIntoView(self.rich_text.CaretPosition, wx.WXK_PAGEDOWN)

        motds = [message for message in self.client.initial_messages if message.startswith("MOTD ")]
        motd = motds[-1][5:]
        self.show_motd(motd)

        self.poll_timer = wx.Timer()
        self.poll_timer.Bind(wx.EVT_TIMER, self.poll)
        self.poll_timer.Start(POLL_TIME_MS)

    def focus_text_entry(self, _):
        self.text_entry.SetFocus()

    def poll(self, _):
        for message in self.client.receive_messages():
            self.add_message(message)

    def add_message(self, message):
        if message.startswith("MOTD "):
            self.show_motd(message[5:])
            return
        at_end = self.rich_text.IsPositionVisible(-1)
        self.rich_text.AppendText(message + "\n")
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
    frame.Show()
    app.MainLoop()
