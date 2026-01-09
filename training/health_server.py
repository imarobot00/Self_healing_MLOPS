#!/usr/bin/env python3
"""
Training Service HTTP Server for Health Checks and Metrics
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime
import threading
import time

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks"""
    
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'service': 'training',
                'timestamp': datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            # Simple metrics
            self.wfile.write(b'# HELP training_service_up Training service status\n')
            self.wfile.write(b'# TYPE training_service_up gauge\n')
            self.wfile.write(b'training_service_up 1\n')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logs"""
        pass

def start_health_server(port=8001):
    """Start health check server in background thread"""
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"✅ Health check server started on port {port}")
    return server

if __name__ == '__main__':
    server = start_health_server()
    print("Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
