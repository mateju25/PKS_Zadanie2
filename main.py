import socket
import struct
import time
import threading


class Participant:
    socket = None
    dest_adrr_port = None


keep_alive = False


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


def send_keep_alive(dest_socket, addr_port):
    global keep_alive
    while True:
        dest_socket.sendto(create_informative_packet(1), addr_port)
        print("Spojenie ostava.")
        for i in range(0, 10):
            time.sleep(1)
            if not keep_alive:
                return


def start_keep_alive(dest_socket, addr_port):
    t1 = threading.Thread(target=send_keep_alive, args=(dest_socket, addr_port))
    t1.start()
    return t1


# endregion

# region Client


def client_menu():
    print("Moznosti:")
    print("s - sprava")
    print("f - subor")
    print("k - keep alive")
    return input("Vyber: ")


def send_message_data(client, message, size_fragments, frag_num, frags_to_send: []):
    for i in range(frag_num, 0, -1):
        frags_to_send.append(i)

    first = True
    everything_good = [False]

    t2 = threading.Thread(target=listen_to_wrong_data, args=(client, everything_good, frags_to_send))
    t2.start()

    while True:
        while len(frags_to_send) > 0:
            i = frags_to_send.pop()
            if i == frag_num:
                temp = message[(i - 1) * size_fragments:]
            else:
                temp = message[(i-1)*size_fragments:(i)*size_fragments]
            # temp = separated_data[i - 1]
            crc = int(''.join(str(x) for x in create_crc(temp, (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))), 2)
            if first:
                first = False
                crc = crc - 1
            client.socket.sendto(create_data_packet(i, crc, temp), client.dest_adrr_port)

        if everything_good[0]:
            t2.join()
            break


def listen_to_wrong_data(client, everything_good, frags_to_send: []):
    while True:
        data, addr = client.socket.recvfrom(1500)
        if len(data) != 2:
            everything_good[0] = True
            return
        else:
            frags_to_send.append(decode_wrong_packet(data))


def start_client(address, port):
    global keep_alive
    t1 = None
    client = Participant()
    client.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.dest_adrr_port = (address, int(port))
    client.socket.sendto(create_informative_packet(0), client.dest_adrr_port)

    print(f"Pripojeny na adresu {client.dest_adrr_port}\n")

    while True:
        choice = client_menu()
        if choice == 'k':
            keep_alive = not keep_alive
            if keep_alive:
                t1 = threading.Thread(target=send_keep_alive, args=(client.socket, client.dest_adrr_port))
                t1.start()
            else:
                t1.join()

        elif choice == 's' or choice == 'f':
            file = ''
            if choice == 'f':
                file = input("Zadaj cestu: ")
                with open(file, "rb") as f:
                    message = f.read()
            else:
                message = input("Zadaj spravu: ").encode()

            size_fragments = int(input("Zadaj velkost fragmetov: "))
            while size_fragments <= 0 or size_fragments > 1496:
                print("Zly vstup.")
                size_fragments = int(input("Zadaj velkost fragmetov: "))

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
        else:
            return


# endregion

# region Server
def start_server(port):
    server = Participant()
    server.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.socket.bind(("", int(port)))

    data, server.dest_adrr_port = server.socket.recvfrom(1500)
    packet_type, num_of_packets, file_name = decode_informative_packet(data)
    if packet_type != 0:
        print("Nepodarilo sa nadviazat spojenie.")
        server.socket.close()
        return
    print("Nadviazane spojenie z adresy ", server.dest_adrr_port, "\n")

    while True:
        data, addr = server.socket.recvfrom(1500)
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        if packet_type == 1:
            print("Spojenie ostava - prišiel keep alive.")
        elif packet_type == 2 or packet_type == 3:

            if packet_type == 3:
                print("Prišiel súbor: ", file_name.decode())
            else:
                print("Prišla správa.")

            print("Pakety: ", end='')
            packets = {}
            while len(packets) < num_of_packets:
                data, addr = server.socket.recvfrom(1500)
                pos, crc, received_data = decode_data_packet(data)
                crc_now = int(
                    ''.join(str(x) for x in create_crc(received_data, (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))),
                    2)
                print(f"{pos}", end="")
                if crc == crc_now:
                    print(", ", end="")
                    packets[pos] = received_data
                else:
                    print("X, ", end="")
                    server.socket.sendto(create_wrong_packet(pos), server.dest_adrr_port)

            print()
            if packet_type == 3:
                print("Uložený: ", file_name.decode())
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
            server.socket.sendto(create_informative_packet(1), server.dest_adrr_port)


# endregion


if input("o,p") == 'o':
    # start_client("localhost", "5000")
    start_client("192.168.2.152", "5000")
else:
    start_server("5000")
