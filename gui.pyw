import socket
import struct
import time
import threading
import tkinter as tk
from tkinter import *

# region Main Code


class Participant:
    socket = None
    dest_adrr_port = None


entrant = Participant()
keep_alive = False
thread_keep = None


# region Protokol


def create_informative_packet(packet_type, total_packets=0, name_of_file=''):
    if total_packets == 0 and name_of_file == '':
        return struct.pack(f"B", packet_type)
    if name_of_file == '':
        return struct.pack("B", packet_type) + struct.pack("H", total_packets)
    else:
        return struct.pack("B", packet_type) + struct.pack("H", total_packets) + struct.pack(f"{len(name_of_file)}s",
                                                                                             name_of_file)


def create_data_packet(packet_number, crc, data):
    return struct.pack(f"HH{len(data)}s", packet_number, crc, data)


def create_wrong_packet(packet_number):
    return struct.pack(f"H", packet_number)


def decode_informative_packet(data):
    if len(data) == 1:
        return struct.unpack(f"B", data)[0], None, None
    if len(data) == 3:
        packet_type, data = struct.unpack(f"B{2}s", data)
        return packet_type, struct.unpack(f"H", data)[0], None
    if len(data) > 3:
        packet_type, data = struct.unpack(f"B{len(data) - 1}s", data)
        num, data = struct.unpack(f"H{len(data) - 2}s", data)
        return packet_type, num, struct.unpack(f"{len(data)}s", data)[0]


def decode_data_packet(data):
    return struct.unpack(f"HH{len(data) - 4}s", data)


def decode_wrong_packet(data):
    return struct.unpack(f"H", data)[0]


# endregion

# region CRC


def xor(first, second):
    result = []

    for i in range(1, len(first)):
        if first[i] == second[i]:
            result.append(0)
        else:
            result.append(1)

    return result


def create_crc(data, end):
    data = list(''.join(format(int(x), 'b') for x in data))
    data = [int(x) for x in data]
    data += end
    generator = (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1)  # 65519
    index = len(generator)
    temp = data[0:index]

    for i in range(index, len(data)):
        if temp[0] != 0:
            temp = xor(temp, generator)
            temp += [data[i]]

        else:
            temp = xor(temp, (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
            temp += [data[i]]

    if temp[0] != 0:
        temp = xor(temp, generator)
    else:
        temp = xor(temp, (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))

    return temp


# endregion

# region Keep alive


def start_keep_alive(dest_socket, addr_port):
    global keep_alive
    while True:
        dest_socket.sendto(create_informative_packet(1), addr_port)
        print_text("Spojenie udržujem.\n")
        for i in range(0, 10):
            time.sleep(1)
            if not keep_alive:
                return


# endregion

# region Client

def send_message_data(message, size_fragments, frag_num, frags_to_send: []):
    global entrant
    for i in range(frag_num, 0, -1):
        frags_to_send.append(i)

    first = True
    everything_good = [False]

    t2 = threading.Thread(target=listen_to_wrong_data, args=(everything_good, frags_to_send))
    t2.start()

    while True:
        while len(frags_to_send) > 0:
            i = frags_to_send.pop()
            if i == frag_num:
                temp = message[(i - 1) * size_fragments:]
            else:
                temp = message[(i - 1) * size_fragments:(i) * size_fragments]
            # temp = separated_data[i - 1]
            crc = int(''.join(str(x) for x in create_crc(temp, (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))), 2)
            if first:
                first = False
                crc = crc - 1
            entrant.socket.sendto(create_data_packet(i, crc, temp), entrant.dest_adrr_port)

        if everything_good[0]:
            t2.join()
            break


def listen_to_wrong_data(everything_good, frags_to_send: []):
    global entrant
    while True:
        data, addr = entrant.socket.recvfrom(1500)
        if len(data) != 2:
            everything_good[0] = True
            return
        else:
            frags_to_send.append(decode_wrong_packet(data))


def start_client(address, port):
    global keep_alive, entrant
    entrant = Participant()
    entrant.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    entrant.dest_adrr_port = (address, int(port))
    entrant.socket.sendto(create_informative_packet(0), entrant.dest_adrr_port)

    print_text(f"Pripojeny na adresu {entrant.dest_adrr_port}\n")
    # print_text(f"Pripojeny na adresu {client.dest_adrr_port}\n")
    # print(f"Pripojeny na adresu {client.dest_adrr_port}\n")


# endregion

# region Server
def server_listen():
    global entrant
    while True:
        data, addr = entrant.socket.recvfrom(1500)
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        if packet_type == 1:
            print_text("Spojenie ostava - prišiel keep alive.\n")
        elif packet_type == 2 or packet_type == 3:

            if packet_type == 3:
                print_text(f"Prišiel súbor: {file_name.decode()}\n")
            else:
                print_text("Prišla správa.\n")

            print_text("Pakety: ")
            packets = {}
            while len(packets) < num_of_packets:
                data, addr = entrant.socket.recvfrom(1500)
                pos, crc, received_data = decode_data_packet(data)
                crc_now = int(
                    ''.join(str(x) for x in create_crc(received_data, (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))),
                    2)
                print_text(f"{pos}")
                if crc == crc_now:
                    print_text(", ")
                    packets[pos] = received_data
                else:
                    print_text("X, ")
                    entrant.socket.sendto(create_wrong_packet(pos), entrant.dest_adrr_port)

            print_text("\n")
            if packet_type == 3:
                print_text(f"Uložený: {file_name.decode()}")
                packets = [x[1] for x in sorted(packets.items())]
                data = packets[0]
                for i in range(1, len(packets)):
                    data = data + packets[i]
                with open(file_name.decode(), "wb") as f:
                    f.write(data)
            else:
                print_text("Prijatá správa: ")
                for i in sorted(packets.keys()):
                    print_text(f'{packets[i].decode("utf-8")}')
                print_text("\n")
            entrant.socket.sendto(create_informative_packet(1), entrant.dest_adrr_port)


def start_server(port):
    global entrant
    entrant = Participant()
    entrant.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    entrant.socket.bind(("", int(port)))

    data, entrant.dest_adrr_port = entrant.socket.recvfrom(1500)
    packet_type, num_of_packets, file_name = decode_informative_packet(data)
    if packet_type != 0:
        print_text("Nepodarilo sa nadviazat spojenie.\n")
        entrant.socket.close()
        return
    print_text(f"Nadviazane spojenie z adresy {entrant.dest_adrr_port}\n")

    t1 = threading.Thread(target=server_listen)
    t1.start()

# endregion

# endregion


def connect():
    if not client_or_server.get():
        start_client(dest_ip.get(), int(port.get()))
    else:
        start_server(int(port.get()))


def send_message():
    global entrant
    message = message_input.get()

    size_fragments = int(fragment_input.get())
    while size_fragments <= 0 or size_fragments > 1496:
        print_text(f"Zly vstup.\n")
        size_fragments = int(fragment_input.get())

    if len(message) % size_fragments == 0:
        frag_num = int(len(message) / size_fragments)
    else:
        frag_num = int(len(message) / size_fragments) + 1

    entrant.socket.sendto(create_informative_packet(2, frag_num), entrant.dest_adrr_port)
    time.sleep(1)
    frags_to_send = []
    send_message_data(message.encode(), size_fragments, frag_num, frags_to_send)


def send_file():
    global entrant
    file = message_input.get()
    with open(file, "rb") as f:
        message = f.read()

    size_fragments = int(fragment_input.get())
    while size_fragments <= 0 or size_fragments > 1496:
        print_text(f"Zly vstup.\n")
        size_fragments = int(fragment_input.get())

    if len(message) % size_fragments == 0:
        frag_num = int(len(message) / size_fragments)
    else:
        frag_num = int(len(message) / size_fragments) + 1

    entrant.socket.sendto(create_informative_packet(3, frag_num, file.encode()), entrant.dest_adrr_port)
    time.sleep(1)
    frags_to_send = []
    send_message_data(message, size_fragments, frag_num, frags_to_send)


def send_keep_alive():
    global keep_alive, thread_keep
    keep_alive = not keep_alive
    if keep_alive:
        thread_keep = threading.Thread(target=start_keep_alive, args=(entrant.socket, entrant.dest_adrr_port))
        thread_keep.start()
    else:
        thread_keep.join()


def control_user():
    if not client_or_server.get():
        entry_1.config(state=tk.NORMAL)
        entry_2.config(state=tk.NORMAL)
        send_mess.config(state=tk.NORMAL)
        send_file.config(state=tk.NORMAL)
        keep_alive_check.config(state=tk.NORMAL)
        entry_ip.config(state=tk.NORMAL)
    else:
        entry_1.config(state=tk.DISABLED)
        entry_2.config(state=tk.DISABLED)
        send_mess.config(state=tk.DISABLED)
        send_file.config(state=tk.DISABLED)
        keep_alive_check.config(state=tk.DISABLED)
        entry_ip.config(state=tk.DISABLED)


def print_text(string):
    text_console.insert(END, string)
    text_console.see(tk.END)


root = tk.Tk()
root.title("Komunikator")
root.geometry("500x460")
text_console = tk.Text(background="#000000", foreground="#ffffff", height=10, width=50)
text_console.place(height=400, width=350, x=0, y=0)

message_input = StringVar()
entry_1 = tk.Entry(textvariable=message_input)
entry_1.place(width=300, x=5, y=405)

fragment_input = StringVar()
entry_2 = tk.Entry(textvariable=fragment_input)
entry_2.place(width=40, x=305, y=405)

label_1 = tk.Label(text="Cieľová IP adresa:")
label_1.place(x=360, y=80)

label_2 = tk.Label(text="Port:")
label_2.place(x=360, y=120)

port = StringVar()
entry_port = tk.Entry(textvariable=port)
entry_port.place(x=360, y=140)

dest_ip = StringVar()
entry_ip = tk.Entry(textvariable=dest_ip)
entry_ip.place(x=360, y=100)

send_mess = tk.Button(text="Pošli správu", command=send_message)
send_mess.place(x=5, y=430)

send_file = tk.Button(text="Pošli súbor", command=send_file)
send_file.place(x=90, y=430)

connect = tk.Button(text="Spoj", command=connect)
connect.place(x=380, y=170)

client_or_server = BooleanVar()
client_R = tk.Radiobutton(text="Client", variable=client_or_server, value=False, command=control_user)
client_R.place(x=370, y=10)

server_R = tk.Radiobutton(text="Server", variable=client_or_server, value=True, command=control_user)
server_R.place(x=370, y=40)

keep_alive_check = tk.Checkbutton(text="Keep alive", command=send_keep_alive)
keep_alive_check.place(x=365, y=200)

root.mainloop()
