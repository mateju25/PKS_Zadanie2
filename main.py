import os
import random
import socket
import struct
import time
import threading
import zlib


class Participant:
    socket = None
    dest_adrr_port = None

# region Protokol


def create_informative_packet(packet_type, packets=0, name_of_file=''.encode()):
    if packets == 0 and name_of_file == ''.encode():
        return struct.pack(f"B", packet_type)
    if name_of_file == '':
        return struct.pack("B", packet_type) + packets.to_bytes(3, byteorder='big')
    else:
        return struct.pack("B", packet_type) + packets.to_bytes(3, byteorder='big') + struct.pack(f"{len(name_of_file)}s",
                                                                                                  name_of_file)


def create_data_packet(packet_number, crc, data):
    return packet_number.to_bytes(3, byteorder='big') + crc.to_bytes(4, byteorder='big') + struct.pack(f"{len(data)}s", data)


def decode_informative_packet(data):
    if len(data) == 1:
        return struct.unpack(f"B", data)[0], None, None
    if len(data) == 4:
        packet_type, data = struct.unpack(f"B{3}s", data)
        return packet_type, int.from_bytes(data, byteorder='big'), None
    if len(data) > 3:
        packet_type, num, data = struct.unpack(f"B{3}s{len(data) - 4}s", data)
        num = int.from_bytes(num, byteorder='big')
        return packet_type, num, struct.unpack(f"{len(data)}s", data)[0]


def decode_data_packet(data):
    num, crc, data = struct.unpack(f"{3}s{4}s{len(data) - 7}s", data)
    crc = int.from_bytes(crc, byteorder='big')
    num = int.from_bytes(num, byteorder='big')
    return num, crc, data


# endregion

# region Keep alive
keep_alive = False


def start_keep_alive(dest_socket, addr_port):
    global keep_alive
    while True:
        dest_socket.sendto(create_informative_packet(1), addr_port)
        try:
            dest_socket.settimeout(10)
            data, addr = dest_socket.recvfrom(1500)
        except (ConnectionResetError, socket.timeout):
            print("Neprisiel ACK keep alive.")
            dest_socket.close()
            return
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        if packet_type != 1:
            print("Neprisiel ACK keep alive.")
            dest_socket.close()
            return
        print("Spojenie ostava.")
        for i in range(0, 30):
            time.sleep(1)
            if not keep_alive:
                return


# endregion

# region Client


def client_menu():
    print()
    print("****************************************************")
    print("*Moznosti:   s - sprava        f - subor           *")
    print("*            k - keep alive    c - zmenit rolu     *")
    print("*            e - ukoncit                           *")
    print("****************************************************")
    return input("Vyber: \n")


def send_message_data(client, message, size_fragments, frag_num, frags_to_send: []):
    for i in range(frag_num, 0, -1):
        frags_to_send.append(i)

    everything_good = [False]
    sent_frags = []

    t2 = threading.Thread(target=listen_to_wrong_data,
                          args=(client, everything_good, frags_to_send, sent_frags), daemon=True)
    t2.start()

    while True:
        while len(frags_to_send) > 0:
            i = frags_to_send.pop()
            if i == frag_num:
                temp = message[(i - 1) * size_fragments:]
            else:
                temp = message[(i-1)*size_fragments:i * size_fragments]

            crc = zlib.crc32(temp)
            if random.random() < 0.3:
                crc = crc - 1
            # time.sleep(0.01)

            client.socket.sendto(create_data_packet(i, crc, temp), client.dest_adrr_port)

        if everything_good[0]:
            t2.join()
            print("Všetko odoslané.")
            break
        else:
            if len(sent_frags) != frag_num:
                for x in range(1, frag_num + 1):
                    if (x not in sent_frags) and (x not in frags_to_send):
                        frags_to_send.append(x)


def listen_to_wrong_data(client, everything_good, frags_to_send: [], sent_frags: []):
    while True:
        data, addr = client.socket.recvfrom(1500)
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        if packet_type == 4:
            sent_frags.append(num_of_packets)
        elif packet_type == 5:
            frags_to_send.append(num_of_packets)
        elif packet_type == 6:
            everything_good[0] = True
            return


def is_someone_there(client):
    client.socket.sendto(create_informative_packet(1), client.dest_adrr_port)
    try:
        client.socket.settimeout(10)
        data, addr = client.socket.recvfrom(1500)
    except (ConnectionResetError, socket.timeout):
        print("Server nepočúva.")
        return 1
    return 0


def start_client(address, port):
    client = Participant()
    client.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.dest_adrr_port = (address, int(port))
    client.socket.sendto(create_informative_packet(0), client.dest_adrr_port)

    data, client.dest_adrr_port = client.socket.recvfrom(1500)
    packet_type, num_of_packets, file_name = decode_informative_packet(data)
    if packet_type != 0:
        print("Nepodarilo sa nadviazat spojenie.")
        client.socket.close()
        return
    print(f"Pripojeny na adresu {client.dest_adrr_port}")
    print("----------------------------------------------------")
    main_client(client)


def main_client(client):
    global keep_alive
    t1 = None
    while True:
        choice = client_menu()
        if choice == 'k':
            if is_someone_there(client):
                continue
            keep_alive = not keep_alive
            if keep_alive:
                t1 = threading.Thread(target=start_keep_alive, args=(client.socket, client.dest_adrr_port))
                t1.start()
            else:
                t1.join()

        elif choice == 'c':
            if keep_alive:
                keep_alive = False
                t1.join()

            if is_someone_there(client):
                continue

            client.socket.sendto(create_informative_packet(7), client.dest_adrr_port)

            main_server(client)
            return

        elif choice == 's' or choice == 'f':
            refresh = False
            if keep_alive:
                refresh = True
                keep_alive = False
                t1.join()

            if is_someone_there(client):
                continue

            file = ''
            if choice == 'f':
                file = input("Zadaj cestu: ")
                with open(file, "rb") as f:
                    message = f.read()
                print("Posielam súbor z ", os.path.abspath(file))
            else:
                message = input("Zadaj spravu: ").encode()

            size_fragments = int(input("Zadaj velkosť fragmetov (1-1462): "))
            while size_fragments <= 0 or size_fragments > 1462:
                print("Zlý vstup.")
                size_fragments = int(input("Zadaj velkosť fragmetov (1-1462): "))

            if len(message) % size_fragments == 0:
                frag_num = int(len(message) / size_fragments)
            else:
                frag_num = int(len(message) / size_fragments) + 1

            if choice == 'f':
                client.socket.sendto(create_informative_packet(3, frag_num, file.encode()), client.dest_adrr_port)
            else:
                client.socket.sendto(create_informative_packet(2, frag_num), client.dest_adrr_port)

            frags_to_send = []
            send_message_data(client, message, size_fragments, frag_num, frags_to_send)

            if refresh:
                keep_alive = True
                t1 = threading.Thread(target=start_keep_alive, args=(client.socket, client.dest_adrr_port))
                t1.start()
        elif choice == 'e':
            return


# endregion

# region Server

close_server = False


def start_server(port):
    server = Participant()
    server.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.socket.settimeout(60)
    try:
        server.socket.bind(("", int(port)))

        data, server.dest_adrr_port = server.socket.recvfrom(1500)
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        if packet_type != 0:
            print("Nepodarilo sa nadviazat spojenie.")
            server.socket.close()
            return
        print("Nadviazane spojenie z adresy ", server.dest_adrr_port)
        server.socket.sendto(create_informative_packet(0), server.dest_adrr_port)
        print("----------------------------------------------------")
        print()
        main_server(server)
    except socket.timeout:
        print("Uzavieram spojenie.")
        server.socket.close()
        return


def listen_to_data(server, packet_type, num_of_packets, file_name):
    if packet_type == 3:
        print("Príde súbor.")
    else:
        print("Prišla správa.")

    print("Pakety: ", end='')
    packets = {}
    while len(packets) < num_of_packets:
        data, addr = server.socket.recvfrom(1500)
        pos, crc, received_data = decode_data_packet(data)
        crc_now = zlib.crc32(received_data)
        print(f"{pos}", end="")
        if crc == crc_now:
            print(", ", end="")
            packets[pos] = received_data
            server.socket.sendto(create_informative_packet(4, pos), server.dest_adrr_port)
        else:
            print("X, ", end="")
            server.socket.sendto(create_informative_packet(5, pos), server.dest_adrr_port)

    print()
    if packet_type == 3:
        print("Uložený na ", os.path.abspath(file_name.decode()))
        packets = [x[1] for x in sorted(packets.items())]
        data = packets[0]
        for i in range(1, len(packets)):
            data = data + packets[i]
        with open(file_name.decode(), "wb") as f:
            f.write(data)
    else:
        print("Prijatá správa: ", end="")
        for i in sorted(packets.keys()):
            print(packets[i].decode("utf-8"), end='')
        print()
    print()
    server.socket.sendto(create_informative_packet(6), server.dest_adrr_port)


def main_server(server):
    server.socket.settimeout(60)
    try:
        while True:
            data, addr = server.socket.recvfrom(1500)
            packet_type, num_of_packets, file_name = decode_informative_packet(data)
            if packet_type == 1:
                print("Spojenie ostava - prišiel keep alive.")
                server.socket.sendto(create_informative_packet(1), server.dest_adrr_port)

            elif packet_type == 2 or packet_type == 3:
                listen_to_data(server, packet_type, num_of_packets, file_name)
            elif packet_type == 7:
                break

    except socket.timeout:
        print("Uzavieram spojenie.")
        server.socket.close()
        return

    main_client(server)

# endregion


print()
print("*****************************************************************************")
print("                              UDP komunikátor                                ")
print("                           Autor: Matej Delinčák                             ")
print("*****************************************************************************")
print()
choice = input("Odosielatel - o, Prijimatel - p: ")
if choice == 'o':
    start_client(input("IP adresa serveru: "), input("Port serveru: "))
    #start_client("localhost", "5000")
    # start_client("192.168.2.152", "5000")
elif choice == 'p':
    #start_server(5000)
    start_server(input("Port serveru: "))
