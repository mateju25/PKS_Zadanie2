from tkinter import *

import pygubu


class GuiDataApp:
    def __init__(self):
        self.builder = builder = pygubu.Builder()
        builder.add_from_file("gui_data.ui")
        self.mainwindow = builder.get_object('frame_1')
        builder.connect_callbacks(self)

    def run(self):
        self.mainwindow.mainloop()

    def client_clicked(self):
        radio = self.builder.objects.get("Server").widget
        radio.var = False

    def server_clicked(self):
        radio = self.builder.objects.get("Client").widget
        radio.var = True

    def send_mess(self):
        text = self.builder.objects.get("text_console").widget
        text.insert(END, "ssss\n")
        pass


if __name__ == '__main__':
    import tkinter as tk

    root = tk.Tk()
    app = GuiDataApp()
    app.run()

