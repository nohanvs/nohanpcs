from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
print("Servidor de deploy rodando em http://0.0.0.0:8080")
print("Arquivos disponiveis: app.py, start.vbs")
HTTPServer(('0.0.0.0', 8080), SimpleHTTPRequestHandler).serve_forever()
