import json
import socket
import threading
import time
import unittest

from voice_guidance import CommandError, NullPublisher, SayCommand, TcpJsonLink, parse_command

TIMEOUT = 3.0


class ParseCommandTest(unittest.TestCase):
    def test_valid_say_command(self):
        self.assertEqual(parse_command(b'{"cmd": "say", "text": " Lite n\xc3\xa4rmare. "}'), SayCommand("Lite närmare."))
        self.assertEqual(parse_command('{"cmd":"say","text":"Hej"}'), SayCommand("Hej"))

    def test_rejects_everything_else(self):
        bad_lines = [b"inte json", b"\xff\xfe", b"[]", b'{"cmd": "stop"}', b'{"cmd": "say"}',
                     b'{"cmd": "say", "text": 5}', b'{"cmd": "say", "text": "   "}',
                     b'{"cmd": "say", "text": "' + b"x" * 121 + b'"}',
                     b'{"cmd": "say", "text": "rad\\nbrytning"}']
        for line in bad_lines:
            with self.subTest(line=line[:30]):
                with self.assertRaises(CommandError):
                    parse_command(line)

    def test_extra_fields_cannot_raise_the_priority(self):
        # priority ignoreras: kommandot har inget sådant fält, och uppspelningen sker alltid på nivå 3
        self.assertEqual(parse_command(b'{"cmd": "say", "text": "x", "priority": 1}'), SayCommand("x"))


class TcpJsonLinkTest(unittest.TestCase):
    def setUp(self):
        self.said = []
        self.said_event = threading.Event()

        def on_say(command):
            self.said.append(command.text)
            self.said_event.set()

        self.link = TcpJsonLink(port=0, on_say=on_say)
        self.port = self.link.start()
        self.addCleanup(self.link.close)

    def connect(self):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=TIMEOUT)
        self.addCleanup(sock.close)
        return sock, sock.makefile("rb")

    def read_json(self, reader):
        return json.loads(reader.readline())

    def wait_for_clients(self, count):
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            with self.link._lock:
                if len(self.link._clients) == count:
                    return
            time.sleep(0.01)
        self.fail(f"länken har inte {count} klienter")

    def test_new_client_gets_hello_with_protocol_version(self):
        _, reader = self.connect()
        self.assertEqual(self.read_json(reader), {"type": "hello", "protocol": 1})

    def test_published_events_reach_every_client_as_json_lines(self):
        _, first = self.connect()
        _, second = self.connect()
        self.read_json(first), self.read_json(second)
        self.wait_for_clients(2)
        self.link.publish({"type": "guidance", "text": "Lite närmare.", "ean": None})
        for reader in (first, second):
            self.assertEqual(self.read_json(reader), {"type": "guidance", "text": "Lite närmare.", "ean": None})

    def test_say_command_reaches_the_callback(self):
        sock, reader = self.connect()
        self.read_json(reader)
        sock.sendall(b'{"cmd": "say", "text": "Hej"}\n')
        self.assertTrue(self.said_event.wait(TIMEOUT))
        self.assertEqual(self.said, ["Hej"])

    def test_commands_split_over_several_packets_still_work(self):
        sock, reader = self.connect()
        self.read_json(reader)
        for part in (b'{"cmd": "sa', b'y", "text": "Del', b'ad"}\n'):
            sock.sendall(part)
            time.sleep(0.05)
        self.assertTrue(self.said_event.wait(TIMEOUT))
        self.assertEqual(self.said, ["Delad"])

    def test_bad_command_gets_an_error_reply_and_the_link_keeps_working(self):
        sock, reader = self.connect()
        self.read_json(reader)
        sock.sendall(b"inte json\n")
        reply = self.read_json(reader)
        self.assertEqual(reply["type"], "error")
        sock.sendall(b'{"cmd": "say", "text": "Efter fel"}\n')
        self.assertTrue(self.said_event.wait(TIMEOUT))
        self.assertEqual(self.said, ["Efter fel"])

    def test_oversized_line_disconnects_the_client(self):
        sock, reader = self.connect()
        self.read_json(reader)
        sock.sendall(b"x" * 5000)
        self.assertEqual(self.read_json(reader)["type"], "error")
        self.assertEqual(reader.readline(), b"")   # därefter stängd

    def test_publishing_to_a_departed_client_does_not_raise(self):
        sock, reader = self.connect()
        self.read_json(reader)
        self.wait_for_clients(1)
        sock.close()
        reader.close()
        for _ in range(50):
            self.link.publish({"type": "read", "data": "x" * 10000})
        self.wait_for_clients(0)

    def test_close_disconnects_clients(self):
        _, reader = self.connect()
        self.read_json(reader)
        self.link.close()
        self.assertEqual(reader.readline(), b"")

    def test_refuses_to_listen_outside_localhost(self):
        with self.assertRaises(ValueError):
            TcpJsonLink(host="0.0.0.0")


class LinkWithoutCallbackTest(unittest.TestCase):
    def test_say_without_callback_is_answered_with_an_error(self):
        link = TcpJsonLink(port=0)
        port = link.start()
        self.addCleanup(link.close)
        sock = socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT)
        self.addCleanup(sock.close)
        reader = sock.makefile("rb")
        reader.readline()
        sock.sendall(b'{"cmd": "say", "text": "Hej"}\n')
        self.assertEqual(json.loads(reader.readline())["type"], "error")


class NullPublisherTest(unittest.TestCase):
    def test_does_nothing(self):
        publisher = NullPublisher()
        publisher.publish({"type": "read"})
        publisher.close()


if __name__ == "__main__":
    unittest.main()
