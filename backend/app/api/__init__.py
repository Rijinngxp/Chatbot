from . import chat, documents, system, tools

routers = [system.router, chat.router, documents.router, tools.router]
