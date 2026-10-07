from . import chat, documents, memory, system, tools

routers = [system.router, chat.router, documents.router, memory.router, tools.router]
