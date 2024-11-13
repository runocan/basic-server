import os
import socket
import mimetypes
from pathlib import Path
from urllib.parse import unquote

# Basic implementation of an HTTP server from scratch
# Using object oriented practices
# So far supports GET and POST methods

# TODO Implement other HTTP methods
# TODO Implement caching
# TODO Implement cookies
# TODO Implement HTTPs

class TCPServer:
    # Base server class for handling TCP connections
    # HTTP server inherits from this class
    def __init__(self, host='127.0.0.1', port=10000):
        self.host = host
        self.port = port

    def start(self):
        # Method for starting the server
        # create socket object
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # binds the socket object with the server address and server port
        sock.bind((self.host, self.port))

        sock.listen(5)

        # print("Listening at", sock.getsockname())
    
        while True:
            print("waiting for connection...")
            # accept any new connection
            connection, address = sock.accept()
            try:
                print("Connected by ", address)
                while True:
                    # read the data by the client
                    data = connection.recv(1024)
                    print('recieved {!r}'.format(data))
                    response = self.handle_request(data)
                    if response:
                        # send back the data to the client
                        print("send data back to client")
                        connection.sendall(response)
                        break
                    else:
                        print("no data from...", address)
                        break
            finally:
                # close the connection
                connection.close()
    
    def handle_request(self, data):
        # Handles incoming data and returns a response
        # Override this in subclass.
        return data


class HTTPServer(TCPServer):
    # Actual HTTP server class
    # Inherits from TCPServer
    # Handles HTTP requests and responses
    headers = {
        'Server': 'Crude Server',
        'Content-Type': 'text/html', # Adding Content-Length, 0 here prevents from loading the page
    }

    status_codes = {
        200: 'OK',
        404: 'Not Found',
        501: 'Not Implemented',
        403: 'Forbidden',
    }

    allowed_files = {'index.html', 'hello.html', 'home.html'}
    allowed_extensions = {'.html', '.css', '.js', '.jpg', '.jpeg', '.png', '.gif'}
    base_directory = Path('Public')

    def handle_request(self, data):
        # Handles incoming requests

        request = HTTPRequest(data) # Gets a parsed HTTP request

        try:
            # Call the corresponding handler method for the current
            # request's method
            handler = getattr(self, 'handle_%s' % request.method)
        except AttributeError:
            handler = self.HTTP_501_handler
        
        response = handler(request)

        return response
    
    def HTTP_501_handler(self, request):
        # Returns 501 HTTP resonse if the request hasn't been implemented
        response_line = self.response_line(status_code=501)

        response_headers = self.response_headers()

        blank_line = b"\r\n"

        response_body = b"<h1>501 Not Implemented</h1>"

        return b"".join([response_line, response_headers, blank_line, response_body])
    
    def is_an_allowed_file(self, filename):
        if filename in self.allowed_files:
            return True
        
        _, ext = os.path.splitext(filename)
        if ext in self.allowed_extensions:
            return True
        return False
    
    def handle_GET(self, request):
        # Handler for GET HTTP method
        filename = unquote(request.uri.strip('/')) # removes the slash from the request
        print(f"Requested file: {filename}")

        if not filename:
            filename = 'home.html'
            print("Default to homepage html file")

        requested_path = self.base_directory / filename
        print(f"Requested path: {requested_path}")

        if not requested_path.is_relative_to(self.base_directory):
            return self.response_line(status_code=403)

        if self.is_an_allowed_file(filename):
            if requested_path.exists():
                response_line = self.response_line(status_code=200)

                # find out a file's MIME type
                # if nothing is found, sends 'text/html'
                content_type = mimetypes.guess_type(filename)[0] or 'text/html'

                with requested_path.open('rb') as f:
                    response_body = f.read()

                extra_headers = {
                    'Content-Type': content_type,
                    'Content-Length': len(response_body)}
                
                response_headers = self.response_headers(extra_headers)
                
            else:
                response_line = self.response_line(status_code=404)
                response_headers = self.response_headers()
                response_body = b"<h1>404 Not Found</h1>"
        else:
            response_line = self.response_line(status_code=403)
            response_headers = self.response_headers()
            response_body = b"<h1>403 Forbidden</h1>"
        
        blank_line = b"\r\n"

        return b"".join([response_line, response_headers, blank_line, response_body])
    
    # TODO Implement POST method
    def handle_POST(self, request):
        # Handler for POST HTTP method
        print("Handling POST request, this is the data: ", request.body)
        content_length = request.headers.get('Content-Length', 0)
        content_length = int(content_length)

        body = request.body[:content_length].decode()
        print("Recieved POST data")

        response_line = self.response_line(status_code=200)
        response_headers = self.response_headers()
        response_body = body.encode()

        blank_line = b"\r\n"
        return b"".join([response_line, response_headers, blank_line, response_body])
    
    def response_line(self, status_code):
        # Returns response line as bytes
        reason = self.status_codes[status_code]
        line = "HTTP/1.1 %s %s\r\n" % (status_code, reason)

        return line.encode() # converts from str to bytes
    
    def response_headers(self, extra_headers=None):
        # Returns headers as bytes
        # extra_headers can be a dict for sending extra headers for current response
        headers_copy = self.headers.copy()

        if extra_headers:
            headers_copy.update(extra_headers)
        
        headers = ""

        for h in headers_copy:
            headers += "%s: %s\r\n" % (h, headers_copy[h])

        return headers.encode()

class HTTPRequest:
    # Parser for HTTP Requests
    # Takes raw data and extracts the information about the request
    #
    # Instances of the HTTPRequest class have the attributes:
    #   self.method:        The current HTTP request method sent by the client (string)
    #   self.uri:           URI for the current request (string)
    #   self.http_version:  HTTP version used by the client (string)
    #   self.headers:       A dictionary of headers sent by the client
    #   self.body:          The body of the request (bytes)
    def __init__(self, data):
        self.method = None
        self.uri = None
        self.http_version = "1.1" # default to HTTP:.1,1 if request doesn't provide a version
        self.headers = {}
        self.body = b""

        # call self.parse method to parse the request data
        self.parse(data)
    
    def parse(self, data):
        lines = data.split(b"\r\n")

        request_line = lines[0] # request line is the first line of the data

        words = request_line.split(b" ") # split request line into seperate words

        self.method = words[0].decode() # call decode to convert bytes to string

        if len(words) > 1:
            # incase browser doesn't send URI with the request for homepage
            self.uri = words[1].decode()
        if len(words) > 2:
            # incase browsers don't send HTTP version
            self.http_version = words[2]

        # if the request has a body, it is the last line of the data
        header_lines = lines[1:]
        for i, line in enumerate(header_lines):
            if line == b"": # end of headers
                self.body = b"\r\n".join(header_lines[i+1:])
                break
            key,value = line.split(b": ", 1)
            self.headers[key.decode()] = value.decode()

if __name__ == '__main__':
    server = HTTPServer()
    server.start()