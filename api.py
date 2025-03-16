"""
API server for the Remote Admin Tool
Provides HTTP endpoints for remote connection and control
"""

import os
import json
import logging
import threading
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import time

logger = logging.getLogger("RemoteAdminAPI")

class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Remote Admin API"""
    
    def __init__(self, *args, connection_manager=None, **kwargs):
        self.connection_manager = connection_manager
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr"""
        logger.info(f"{self.address_string()} - {format%args}")
    
    def send_json_response(self, data, status=200):
        """Send a JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # CORS
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle preflight requests for CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
        if path == '/api/status':
            # Return status information
            self.handle_status()
        
        elif path == '/api/connections':
            # List active connections
            self.handle_connections()
        
        elif path == '/api/screenshot':
            # Get a screenshot
            self.handle_screenshot(query)
        
        elif path == '/api/system-info':
            # Get system information
            self.handle_system_info()
        
        else:
            # Unknown endpoint
            self.send_json_response({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        request_body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(request_body) if content_length > 0 else {}
        except json.JSONDecodeError:
            self.send_json_response({'error': 'Invalid JSON'}, 400)
            return
        
        if path == '/api/connect':
            # Connect to a remote host
            self.handle_connect(data)
        
        elif path == '/api/disconnect':
            # Disconnect from a remote host
            self.handle_disconnect()
        
        elif path == '/api/start-hosting':
            # Start hosting
            self.handle_start_hosting(data)
        
        elif path == '/api/stop-hosting':
            # Stop hosting
            self.handle_stop_hosting()
        
        elif path == '/api/send-mouse-event':
            # Send a mouse event
            self.handle_mouse_event(data)
        
        elif path == '/api/send-keyboard-event':
            # Send a keyboard event
            self.handle_keyboard_event(data)
        
        else:
            # Unknown endpoint
            self.send_json_response({'error': 'Not found'}, 404)
    
    def handle_status(self):
        """Handle status request"""
        if not self.connection_manager:
            self.send_json_response({'error': 'Connection manager not available'}, 500)
            return
        
        status = {
            'connected': self.connection_manager.is_connected(),
            'hosting': self.connection_manager.is_hosting(),
            'remote_address': self.connection_manager.remote_address,
            'host_id': self.connection_manager.host_id,
            'timestamp': time.time()
        }
        
        self.send_json_response(status)
    
    def handle_connections(self):
        """Handle connections list request"""
        if not self.connection_manager:
            self.send_json_response({'error': 'Connection manager not available'}, 500)
            return
        
        connections = []
        
        # Add information about active connections
        if self.connection_manager.is_hosting():
            for addr, handler in self.connection_manager.connection_handlers.items():
                connections.append({
                    'address': addr,
                    'connected_time': handler.get('connected_time', 0)
                })
        
        self.send_json_response({'connections': connections})
    
    def handle_screenshot(self, query):
        """Handle screenshot request"""
        if not self.connection_manager:
            self.send_json_response({'error': 'Connection manager not available'}, 500)
            return
        
        # Get quality parameter
        quality = 70
        if 'quality' in query and query['quality']:
            try:
                quality = int(query['quality'][0])
                quality = max(1, min(100, quality))  # Clamp between 1-100
            except ValueError:
                pass
        
        # Get screenshot if connected
        if self.connection_manager.is_connected():
            screen_data = self.connection_manager.get_remote_screen(quality)
            if screen_data:
                # Send as image
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(screen_data)))
                self.end_headers()
                self.wfile.write(screen_data)
                return
        
        # If we get here, something went wrong
        self.send_json_response({'error': 'Unable to get screenshot'}, 400)
    
    def handle_system_info(self):
        """Handle system info request"""
        if not self.connection_manager:
            self.send_json_