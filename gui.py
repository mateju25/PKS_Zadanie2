import threading
from tkinter import *
import main

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
        radio = self.builder.objects.get("Client").widget
        radio.value = True
        radio = self.builder.objects.get("Server").widget
        radio.value = False

    def server_clicked(self):
        radio = self.builder.objects.get("Server").widget
        radio.value = True
        radio = self.builder.objects.get("Client").widget
        radio.value = False


    def connect(self):
        text = self.builder.objects.get("text_console").widget
        ip = self.builder.objects.get("IP").widget
        port = self.builder.objects.get("PORT").widget
        radio = self.builder.objects.get("Client").widget
        if radio.value:
            thread = threading.Thread(target=main.start_client, args=(text, ip.get(), port.get()))
           # main_.start_client(text, ip.get(), port.get())
        else:
            thread = threading.Thread(target=main.start_server, args=(text, port.get()))
           # main_.start_server(text, port.get())
        thread.start()
        thread.join()

    def keep_alive(self):
        pass


if __name__ == '__main__':
    import tkinter as tk

    root = tk.Tk()
    app = GuiDataApp()
    app.run()

