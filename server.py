"""An example of a simple HTTP server."""
from __future__ import print_function

import json
import mimetypes
import pickle
import socket
from os.path import isdir

try:
    from urllib.parse import unquote_plus
except ImportError:
    from urllib import unquote_plus

# Pickle file for storing data
PICKLE_DB = "db.pkl"

# Directory containing www data
WWW_DATA = "www-data"

# Header template for a successful HTTP request
HEADER_RESPONSE_200 = """HTTP/1.1 200 OK
content-type: %s
content-length: %d
connection: Close

"""

# Represents a table row that holds user data
TABLE_ROW = """
<tr>
    <td>%d</td>
    <td>%s</td>
    <td>%s</td>
</tr>
"""

# Template for a 404 (Not found) error
RESPONSE_404_BODY = """
<!doctype html>
<h1>404 Page not found</h1>
<p>Page cannot be found.</p>"""

RESPONSE_404 = """HTTP/1.1 404 Not found
content-type: text/html
content-length: %d
connection: Close
%s
""" % (len(RESPONSE_404_BODY), RESPONSE_404_BODY)

RESPONSE_400_BODY = """
<!doctype html>
<h1>400 Bad request</h1>
<p>Bad request.</p>"""

RESPONSE_400 = """HTTP/1.1 400 Bad request
content-type: text/html
Content-Length: %d
connection: Close
%s
""" % (len(RESPONSE_400_BODY), RESPONSE_400_BODY)

RESPONSE_405_BODY = """
<!doctype html>
<h1>405 Method not allowed</h1>
<p>Method not allowed.</p>"""

RESPONSE_405 = """HTTP/1.1 405 Method not allowed
content-type: text/html
Content-Length: %d
connection: Close
%s
""" % (len(RESPONSE_405_BODY), RESPONSE_405_BODY)

RESPONSE_301 = """HTTP/1.1 301 Moved Permanently
Location: %s

"""


def save_to_db(first, last):
    """Create a new user with given first and last name and store it into
    file-based database.

    For instance, save_to_db("Mick", "Jagger"), will create a new user
    "Mick Jagger" and also assign him a unique number.

    Do not modify this method."""

    existing = read_from_db()
    existing.append({
        "number": 1 if len(existing) == 0 else existing[-1]["number"] + 1,
        "first": first,
        "last": last
    })
    with open(PICKLE_DB, "wb") as handle:
        pickle.dump(existing, handle)


def read_from_db(criteria=None):
    """Read entries from the file-based DB subject to provided criteria

    Use this method to get users from the DB. The criteria parameters should
    either be omitted (returns all users) or be a dict that represents a query
    filter. For instance:
    - read_from_db({"number": 1}) will return a list of users with number 1
    - read_from_db({"first": "bob"}) will return a list of users whose first
    name is "bob".

    Do not modify this method."""
    if criteria is None:
        criteria = {}
    else:
        # remove empty criteria values
        for key in ("number", "first", "last"):
            if key in criteria and criteria[key] == "":
                del criteria[key]

        # cast number to int
        if "number" in criteria:
            criteria["number"] = int(criteria["number"])

    try:
        with open(PICKLE_DB, "rb") as handle:
            data = pickle.load(handle)

        filtered = []
        for entry in data:
            predicate = True

            for key, val in criteria.items():
                if val != entry[key]:
                    predicate = False

            if predicate:
                filtered.append(entry)

        return filtered
    except (IOError, EOFError):
        return []


def parse_headers(client):
    headers = dict()

    while True:
        line = client.readline().decode("utf-8").strip()
        if line == "":
            return headers
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        headers[key] = value


def parse_post_request(data):
    student = dict()
    data = data.strip().split("&")

    if len(data) != 2:
        return False

    for atribut in data:
        key, value = unquote_plus(atribut).strip().split("=", 1)

        # if key != "first" or key != "last":
        #     return False

        if value != "" and (key == "first" or key == "last"):
            student[key] = value

    save_to_db(student["first"], student["last"])
    return True


def parse_get_request(data):
    student = {}

    try:
        data = data.strip().split("?", 1)[-1].split("&")
        assert len(data) > 0 and data[0] != ""

        for attribute in data:
            key, value = unquote_plus(attribute).strip().split("=", 1)
            try:
                if key == "number":
                    a = int(value)
            except Exception as e:
                return None

            if value != "" and (key == "number" or key == "first" or key == "last"):
                student[key] = value

        return student
    except Exception as e:
        return None


def create_table_response(uri):
    search = read_from_db()
    response_table = ""

    try:
        if "?" in uri:
            search = read_from_db(parse_get_request(uri))

        for student in search:
            response_table += TABLE_ROW % (student["number"], student["first"], student["last"])

        with open(WWW_DATA + "/app_list.html", "rt") as data:
            response_page = data.read().replace("{{students}}", response_table)

        return response_page.encode("utf-8")
    except Exception as e:
        return "".encode("utf-8")


def create_json_response(uri):
    search = read_from_db()

    if "?" in uri:
        search = read_from_db(parse_get_request(uri))

    return json.dumps(search).encode("utf-8")


def handle_errors(client, e):
    if e.args[0].startswith('405'):
        client.write(RESPONSE_405.encode("utf-8"))
    elif e.args[0].startswith('404'):
        client.write(RESPONSE_404.encode("utf-8"))
    else:
        client.write(RESPONSE_400.encode("utf-8"))


def process_request(connection, address, port):
    """Process an incoming socket request.

    :param connection is a socket of the client
    :param address is a 2-tuple (address(str), port(int)) of the client
    :param port of listening
    """

    # Make reading from a socket like reading/writing from a file
    # Use binary mode, so we can read and write binary data. However,
    # this also means that we have to decode (and encode) data (preferably
    # to utf-8) when reading (and writing) text
    client = connection.makefile("wrb")

    # Read one line, decode it to utf-8 and strip leading and trailing spaces
    try:
        # Read and parse the request line
        method, uri, version = client.readline().decode("utf-8").strip().split()

        assert version == "HTTP/1.1", "400 Invalid version %s" % version

        if uri.startswith("/app-add"):
            assert method == "POST", "405 Invalid method: %s" % method

        elif uri.startswith("/app-index"):
            assert method == "GET", "405 Invalid method: %s" % method

        elif uri.startswith("/app-json"):
            assert method == "GET", "405 Invalid method: %s" % method

        else:
            assert method == "GET" or method == "POST", "405 Invalid method: %s" % method
            assert method == "GET" or method == "POST", "405 Invalid method: %s" % method
            assert uri[0] == "/", "404 Invalid uri: %s" % uri

    except (ValueError, AssertionError) as e:
        print("[%s:%d] ERROR: %s" % (address[0], port, e))
        handle_errors(client, e)
        client.close()
        return

    # Read and parse headers
    headers = parse_headers(client)

    # print("[%s:%d] metoda: %s,  uri: %s, verzija: %s, headers: %s" % (address[0], address[1], method,
    #                                                                   uri, version, headers))

    # Create a response
    try:
        # print(uri)
        if uri == "/app-add":
            data = client.read(int(headers["content-length"])).decode("utf-8")

            # Read and parse the body of the request (if applicable)
            is_save_to_db = parse_post_request(data)

            assert is_save_to_db, "400 Fail to complete"
            uri = "/app_add.html"

        elif uri == "/app-index" or uri.startswith("/app-index?"):
            data = create_table_response(uri)
            response_header = HEADER_RESPONSE_200 % ("text/html", len(data))

            client.write(response_header.encode("utf-8"))
            client.write(data)
            client.close()
            return

        elif uri == "/app-json" or uri.startswith("/app-json?"):
            data = create_json_response(uri)
            response_header = HEADER_RESPONSE_200 % ("application/json", len(data))

            client.write(response_header.encode("utf-8"))
            client.write(data)
            client.close()
            return

        elif uri.endswith("/"):
            uri += "index.html"
            client.write((RESPONSE_301 % f"http://{headers['host']}{uri}").encode("utf-8"))
            client.close()
            return

        if "?" in uri:
            uri = uri.split("?")[0]

        if isdir(WWW_DATA + uri):
            uri += "/index.html"
            client.write((RESPONSE_301 % f"http://{headers['host']}{uri}").encode("utf-8"))
            client.close()
            return

        with open(WWW_DATA + uri, "rb") as handle:
            data = handle.read()

        mimetype, _ = mimetypes.guess_type(uri[1:])
        if mimetype is None:
            mimetype = "application/octet-stream"

        response_header = HEADER_RESPONSE_200 % (mimetype, len(data))

        # Write the response to the socket
        client.write(response_header.encode("utf-8"))
        client.write(data)

    except (ValueError, AssertionError) as e:
        handle_errors(client, e)

    except FileNotFoundError:
        client.write(RESPONSE_404.encode("utf-8"))

    except Exception as e:
        client.write(RESPONSE_400.encode("utf-8"))

    # Closes file-like object
    finally:
        client.close()


def main(port):
    """Starts the server and waits for connections."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", port))
    server.listen(1)

    print("Listening on %d" % port)

    while True:
        connection, address = server.accept()
        print("[%s:%d] CONNECTED" % (address[0], address[1]))
        process_request(connection, address, port)
        connection.close()
        print("[%s:%d] DISCONNECTED" % (address[0], address[1]))


if __name__ == "__main__":
    main(8080)
