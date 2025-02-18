import os
import socket
import struct
import time
import threading
import zlib


class Participant:
    my_socket = None
    dest_adrr_port = None


# region Protokol


# vytvori informacny paket
def create_informative_packet(packet_type, packets=0, name_of_file=''):
    # pouzi len pole Type
    if packets == 0 and name_of_file == '':
        return struct.pack(f"B", packet_type)

    # pouzi len pole Type a Packets
    if name_of_file == '':
        return struct.pack("B", packet_type) + \
               packets.to_bytes(3, byteorder='big')
    else:

        # pouzi vsetky polia
        return struct.pack("B", packet_type) + \
               packets.to_bytes(3, byteorder='big') + \
               struct.pack(f"{len(name_of_file)}s", name_of_file)


# vytvori datovy paket
def create_data_packet(packet_number, crc, data):
    return packet_number.to_bytes(3, byteorder='big') + \
           crc.to_bytes(4, byteorder='big') + \
           struct.pack(f"{len(data)}s", data)


# dekoduje informacny paket
def decode_informative_packet(data):
    # pouzi len pole Type
    if len(data) == 1:
        return struct.unpack(f"B", data)[0], None, None

    # pouzi len pole Type a Packets
    elif len(data) == 4:
        packet_type, data = struct.unpack(f"B{3}s", data)
        return packet_type, int.from_bytes(data, byteorder='big'), None

    # pouzi vsetky polia
    elif len(data) > 3:
        packet_type, num, data = struct.unpack(f"B{3}s{len(data) - 4}s", data)
        num = int.from_bytes(num, byteorder='big')
        return packet_type, num, struct.unpack(f"{len(data)}s", data)[0]


# dekoduje datovy paket
def decode_data_packet(data):
    num, crc, data = struct.unpack(f"{3}s{4}s{len(data) - 7}s", data)
    crc = int.from_bytes(crc, byteorder='big')
    num = int.from_bytes(num, byteorder='big')
    return num, crc, data


# endregion

# region Keep alive
keep_alive = False


# zacne posielanie keep alive paketov
def start_keep_alive(dest_socket, addr_port):
    global keep_alive
    time.sleep(0.01)

    while True:
        # posli keep alive serveru
        dest_socket.sendto(create_informative_packet(1), addr_port)

        # cakaj sekundu na odpoved od servera
        try:
            dest_socket.settimeout(2)
            data, addr = dest_socket.recvfrom(1500)
        except (ConnectionResetError, socket.timeout):
            if not keep_alive:
                return
            print("Neprisiel ACK keep alive.")
            keep_alive = False
            return

        # dekoduj ak prisiel paket
        packet_type, num_of_packets, file_name = decode_informative_packet(data)

        # ak prisiel iny typ paket, tak ukonci
        if packet_type != 1:
            print("Neprisiel spravny ACK keep alive.")
            keep_alive = False
            return

        # ostava spojenie
        print("Spojenie ostava.")
        for i in range(0, 30):
            time.sleep(1)
            if not keep_alive:
                return


# endregion

# region Client


# vypis hlavicku pre klienta a vrat vyber
def client_menu():
    global keep_alive
    print()
    print("****************************************************")
    print("*Moznosti:   s - sprava           f - subor        *")
    if keep_alive:
        print("*            k - keep alive OFF   c - zmenit rolu  *")
    else:
        print("*            k - keep alive ON    c - zmenit rolu  *")
    print("*            e - ukoncit                           *")
    print("****************************************************")
    return input("Vyber: \n")


# posli data serveru metodou SELECTIVE ARQ
def send_data(client, data, frags_to_send, wrong, size_of_fragment):
    # vsetko prislo spravne?
    everything_good = [False]
    # uspesne odoslane pakety
    stack = [x for x in frags_to_send]
    # vytvor thread na pocuvanie odpovedi od serveru
    t2 = threading.Thread(target=listen_to_wrong_data,
                          args=(client, everything_good, stack, frags_to_send), daemon=True)
    t2.start()

    while True:
        while len(stack) > 0:
            # vyber prvy paket
            i = stack.pop()
            # vyber ktory fragment poslat
            try:
                temp = data[(i - 1) * size_of_fragment:i * size_of_fragment]
            except IndexError:
                temp = data[(i - 1) * size_of_fragment:]

            # vytvor crc
            crc = zlib.crc32(temp)
            # pridaj zle crc
            if i in wrong:
                crc = int(crc / 2)
                wrong.remove(i)

            # posli fragment

            client.my_socket.sendto(create_data_packet(i, crc, temp), client.dest_adrr_port)
            #time.sleep(0.0001)

        time.sleep(0.5)
        if len(stack) > 0:
            continue
        # skontroluj ci je vsetko v poriadku, a ak nie, tak dopln zasobnik o pakety, ktore neboli potvrdene ako prijate
        if everything_good[0]:
            t2.join()
            print("Všetko odoslané.")
            break
        else:
            for x in frags_to_send:
                stack.append(x)
            # if len(sent_frags) != len(frags_to_send):
            #     for x in frags_to_send:
            #         if x not in sent_frags:
            #             stack.append(x)


# pocuvaj odpovede od serveru
def listen_to_wrong_data(client, everything_good, stack, frags_to_send: []):
    client.my_socket.settimeout(20)
    while True:
        data, addr = client.my_socket.recvfrom(1500)
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        # rozhodni o aku odpoved ide
        # paket je v poriadku
        if packet_type == 4:
            if num_of_packets in frags_to_send:
                frags_to_send.remove(num_of_packets)
            #sent_frags.append(num_of_packets)
        # paket je zly
        elif packet_type == 5:
            stack.append(num_of_packets)
        # ukoncovaci paket
        elif packet_type == 6:
            everything_good[0] = True
            client.my_socket.sendto(create_informative_packet(6), client.dest_adrr_port)
            return


# zacni klientovu stranu
def start_client(address, port):
    client = Participant()
    # vytvor socket
    client.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.dest_adrr_port = (address, int(port))
    # posli inicializacy paket
    client.my_socket.sendto(create_informative_packet(0), client.dest_adrr_port)

    data, client.dest_adrr_port = client.my_socket.recvfrom(1500)
    packet_type, num_of_packets, file_name = decode_informative_packet(data)
    # neprisla spravna odpoved na inicializaciu
    if packet_type != 0:
        print("Nepodarilo sa nadviazat spojenie.")
        client.my_socket.close()
        return
    print(f"Pripojeny na adresu {client.dest_adrr_port}")
    print("----------------------------------------------------")
    main_client(client)


# hlavy cyklus klienta
def main_client(client):
    global keep_alive
    t1 = None
    while True:
        my_choice = client_menu()

        # moznost pre keep alive
        if my_choice == 'k':
            keep_alive = not keep_alive
            if keep_alive:
                t1 = threading.Thread(target=start_keep_alive, args=(client.my_socket, client.dest_adrr_port))
                t1.start()
            else:
                t1.join()

        # moznost pre zmenu role
        elif my_choice == 'c':
            # vypni keep alive
            if keep_alive:
                keep_alive = False
                t1.join()
            os.system('cls')
            header()
            server_header(client.my_socket.getsockname()[1])
            main_server(client)
            return

        # moznost pre poslanie spravy a
        elif my_choice == 's' or my_choice == 'f':
            client.my_socket.sendto(create_informative_packet(1), client.dest_adrr_port)
            try:
                client.my_socket.settimeout(2)
                data, addr = client.my_socket.recvfrom(1500)
            except (ConnectionResetError, socket.timeout):
                print("Server nepocuva.")
                continue

            # vypni keep alive
            refresh = False
            if keep_alive:
                refresh = True
                keep_alive = False
                t1.join()

            # vypytaj si data
            file = ''
            if my_choice == 'f':
                file = input("Zadaj cestu: ")
                while os.path.exists(file) is False:
                    print("Súbor neexistuje")
                    file = input("Zadaj cestu: ")
                with open(file, "rb") as f:
                    message = f.read()
                print("Posielam súbor z ", os.path.abspath(file))
            else:
                message = input("Zadaj spravu: ").encode()

            # zadaj velkost fragmentu
            size_fragments = int(input("Zadaj velkosť fragmetov (1-1465): "))
            while size_fragments <= 0 or size_fragments > 1465:
                print("Zlý vstup.")
                size_fragments = int(input("Zadaj velkosť fragmetov (1-1465): "))

            # vyrataj pocet fragmentov
            if len(message) % size_fragments == 0:
                frag_num = int(len(message) / size_fragments)
            else:
                frag_num = int(len(message) / size_fragments) + 1

            # pocet zlych paketov
            choice = int(input(f"Zadaj počet chybných paketov(0-{frag_num}): "))
            while choice < 0 or choice > frag_num:
                print("Zlý vstup.")
                choice = int(input(f"Zadaj počet chybných paketov(0-{frag_num}): "))

            # vytvor zasobnik na posielanie paketov
            frags_to_send = []
            for i in range(frag_num, 0, -1):
                frags_to_send.append(i)

            # vyvot pole zlych paketov
            wrong = frags_to_send[frag_num - 1:frag_num - 1 - choice:-1]
            # for i in range(0, choice):
            #     wrong.append(frags_to_send[frag_num-i-1])

            # posli inicializacny paket
            if my_choice == 'f':
                client.my_socket.sendto(create_informative_packet(3, frag_num, file.encode()), client.dest_adrr_port)
            else:
                client.my_socket.sendto(create_informative_packet(2, frag_num), client.dest_adrr_port)

            # posli data
            print("Bude poslaných ", frag_num, "paketov.")

            send_data(client, message, frags_to_send, wrong, size_fragments)

            # zapni keep alive ak bol predtym zapnuty
            if refresh:
                keep_alive = True
                t1 = threading.Thread(target=start_keep_alive, args=(client.my_socket, client.dest_adrr_port))
                t1.start()

        # vypni program a upovedom server
        elif my_choice == 'e':
            client.my_socket.sendto(create_informative_packet(7), client.dest_adrr_port)
            if keep_alive:
                keep_alive = False
                t1.join()
            client.my_socket.close()
            return


# endregion

# region Server


# vypis hlavicku pre server
def server_menu(server):
    print()
    print("****************************************************")
    print("*Moznosti:   c - zmenit rolu   e - ukoncit         *")
    print("*            p - pokracovat                        *")
    print("****************************************************")
    while True:
        my_choice = input("Vyber: \n")
        # moznost pre pokracovanie
        if my_choice == "p":
            return 0
        # moznost pre vymenu role
        elif my_choice == "c":
            os.system('cls')
            header()
            client_header(server.dest_adrr_port)
            main_client(server)
            return 1
        # moznost pre ukoncenie programu
        elif my_choice == "e":
            print("Uzavieram spojenie.")
            server.my_socket.close()
            return 1


# zapni funkciu serveru
def start_server(port):
    server = Participant()
    # vytvor socket
    server.my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.my_socket.settimeout(60)
    try:
        server.my_socket.bind(("", int(port)))

        # prijmi inicializacny paket a odosli taky isty
        data, server.dest_adrr_port = server.my_socket.recvfrom(1500)
        packet_type, num_of_packets, file_name = decode_informative_packet(data)
        if packet_type != 0:
            print("Nepodarilo sa nadviazat spojenie.")
            server.my_socket.close()
            return
        print("Nadviazane spojenie z adresy ", server.dest_adrr_port)
        server.my_socket.sendto(create_informative_packet(0), server.dest_adrr_port)
        print("----------------------------------------------------")
        print()

        main_server(server)
        return
    # ak vyprsi cas, tak zavri spojenie
    except socket.timeout:
        print("Uzavieram spojenie.")
        server.my_socket.close()
        return


# pocuvaj data ak prisiel inicializacny paket
def listen_to_data(server, packet_type, num_of_packets, file_name):
    if packet_type == 3:
        print("Príde súbor.")
    else:
        print("Prišla správa.")

    print("Pakety: ", end='')
    packets = {}

    good = 0
    bad = 0
    # pocuvaj kym nemas vsetky pakety
    while len(packets) < num_of_packets:
        data, addr = server.my_socket.recvfrom(1500)
        pos, crc, received_data = decode_data_packet(data)
        crc_now = zlib.crc32(received_data)
        # dobre crc
        if crc == crc_now:
            print(f"{pos}, ", end="")
            packets[pos] = received_data
            server.my_socket.sendto(create_informative_packet(4, pos), server.dest_adrr_port)
            good += 1
        # zle crc
        else:
            print(f"{pos}X, ", end="")
            server.my_socket.sendto(create_informative_packet(5, pos), server.dest_adrr_port)
            bad += 1

    # posli ukoncovaci paket a prijmi odpoved
    server.my_socket.sendto(create_informative_packet(6), server.dest_adrr_port)
    data, addr = server.my_socket.recvfrom(1500)

    print("\nVeľkosť fragmetov: ", len(packets[1]), "Počet fragmentov: ", good,
          "\nCelkovo prišlo: ", good + bad, "paketov a z toho bolo", bad, "zlých.")
    print()
    # uloz data do suboru
    if packet_type == 3:
        print("Uložený na ", os.path.abspath(file_name))
        packets = [x[1] for x in sorted(packets.items())]
        data = packets[0]
        for i in range(1, len(packets)):
            data = data + packets[i]
        with open(file_name, "wb") as f:
            f.write(data)
    # vypis spravu do konzoly
    else:
        print("Prijatá správa: ", end="")
        end = "".encode()
        for i in sorted(packets.keys()):
            end += packets[i]
        print(end.decode())
        print()
    print()


# hlavny cyklus serveru
def main_server(server):
    server.my_socket.settimeout(60)
    choice = input("Zadaj kam chceš ukladať súbory( '.' aktuálny adresár): ")
    try:
        if server_menu(server):
            return
        while True:
            data, addr = server.my_socket.recvfrom(1500)

            packet_type, num_of_packets, file_name = decode_informative_packet(data)
            if packet_type == 1:
                # prisiel keep alive
                print("Prišiel keep alive.")
                server.my_socket.sendto(create_informative_packet(1), server.dest_adrr_port)

            elif packet_type == 2 or packet_type == 3:
                # prisiel pociatocny paket pre poslanie dat
                server.my_socket.sendto(create_informative_packet(1), server.dest_adrr_port)
                if packet_type == 3:
                    if choice == '.':
                        file_name = file_name.decode()
                    else:
                        file_name = os.path.join(choice, file_name.decode())
                listen_to_data(server, packet_type, num_of_packets, file_name)

                if server_menu(server):
                    return

            elif packet_type == 7:
                # prislo oznamenie, ze klient skoncil
                print("Klient už skončil.")
                passx = input("Stlac cokolvek pre ukoncenie: ")
                server.my_socket.close()
                return

    except socket.timeout:
        print("Uzavieram spojenie.")
        server.my_socket.close()
        return


# endregion

# region Hlavicky


# vypis hlavnu hlavicku programu
def header():
    print()
    print("*****************************************************************************")
    print("                              UDP komunikátor                                ")
    print("                           Autor: Matej Delinčák                             ")
    print("*****************************************************************************")
    print()


# vypis hlavicky pre server
def server_header(port):
    print("Počúvam na porte ", port)
    print("----------------------------------------------------")
    print()


# vypis hlavicky pre klienta
def client_header(addr_port):
    print(f"IP adresa servera {addr_port[0]} a počúva na porte {addr_port[1]}")
    print("----------------------------------------------------")
    print()


# vypis zacatie komunikacie
def menu():
    header()
    choice = input("Odosielatel - o, Prijimatel - p: ")
    if choice == 'o':
        start_client(input("IP adresa serveru: "), input("Port serveru: "))
        # start_client("localhost", "5000")
        # start_client("192.168.2.152", "5000")
    elif choice == 'p':
        # start_server(5000)
        start_server(input("Port serveru: "))


# endregion


while True:
    menu()
    choice = input("Znova pustit program? a/n")
    if choice != 'a':
        break
