import asyncio
import logging
import websockets
from websockets import WebSocketServerProtocol

import json
import asyncpg

async def data_from_db():
    conn = await asyncpg.connect(user='postgres', password='123',
                                 database='chat', host='127.0.0.1')
    values = await conn.fetch('SELECT * FROM message')
    await conn.close()
    return values


logging.basicConfig(level=logging.INFO)

class Server:
    clients = set()
    #conn = connect_to_db()

    async def register(self, ws: WebSocketServerProtocol) -> None:
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects.')

    async def unregister(self, ws: WebSocketServerProtocol) -> None:
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects.')

    async def send_to_clients(self, message: str) -> None:
        if self.clients:
            await asyncio.wait([client.send(json.dumps(message)) for client in self.clients])

    async def ws_handler(self, ws: WebSocketServerProtocol, url: str) -> None:
        await self.register(ws)
        try:
            await self.distribute(ws)
        finally:
            await self.unregister(ws)

    async def distribute(self, ws: WebSocketServerProtocol) -> None:
        async for data in ws:
            message = json.loads(data)
            if message['command'] == 'fetch_messages':
                await self.fetch_messages(ws)
            else:
                message = {'command': 'new_message',
                            'message': 'hello from server',
                            'from': 'server'}
            
                await self.send_to_clients(message)

    async def fetch_messages(self, ws):
        values = await data_from_db()
        messages = []
        for i in values:
            messages.append({'command': 'new_message',
                            'message': i['content'],
                            'from': i['author'],
                            'time': i['time'].strftime("%d.%m.%Y %H:%M:%S")})
        await ws.send(json.dumps(messages))
    
server = Server()
start_server = websockets.serve(server.ws_handler, "localhost", 5000)
loop = asyncio.get_event_loop()
loop.run_until_complete(start_server)
loop.run_forever()
