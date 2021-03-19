import asyncio
import logging
import websockets
from websockets import WebSocketServerProtocol

import json
import asyncpg

import boto3
import settings

async def db(message=None):
    conn = await asyncpg.connect(user='postgres', password='123',
                                 database='chat', host='127.0.0.1')
    if not message:
        values = await conn.fetch('SELECT * FROM message')
        await conn.close()
        return values
    else:
        await conn.fetch(f"INSERT INTO message(author, content) VALUES('{message['from']}', '{message['message']}')")
        await conn.close()
    




logging.basicConfig(level=logging.INFO)


def save_file(data, filename, author):
    with open("upload/" + filename, "wb") as f:
        f.write(data) 
    s3 = boto3.client('s3', region_name='eu-central-1', 
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
    s3.upload_file(Filename='upload/' + filename, 
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME, 
                    Key='upload/' + filename)
    s3_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.eu-central-1.amazonaws.com/upload/{filename}"
    return {"command":"new_message",
            "message": s3_url,
            "filename": filename,
            "from": author}   

class Server:
    clients = set()

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
            if isinstance(data, bytes):
                new_message = save_file(data, self.name_file, self.author)
                await self.send_to_clients(new_message)
            else:   
                message = json.loads(data)
                if message['command'] == 'fetch_messages':
                    await self.fetch_messages(ws)

                elif message['command'] == 'new_message':
                    await db(message)
                    message = {'command': 'new_message',
                                'message': message['message'],
                                'from': message['from']}
                    await self.send_to_clients(message)
                elif message['command'] == 'file':
                    self.author = message['author']
                    self.name_file = message['name']




    async def fetch_messages(self, ws):
        values = await db()
        messages = []
        for i in values:
            messages.append({'command': 'new_message',
                            'message': i['content'],
                            'from': i['author'],
                            'time': i['time'].strftime("%d.%m.%Y %H:%M:%S")})
        await ws.send(json.dumps(messages))
    
server = Server()
start_server = websockets.serve(server.ws_handler, "localhost", 5000, max_size=500000000)
loop = asyncio.get_event_loop()
loop.run_until_complete(start_server)
loop.run_forever()
