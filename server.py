import asyncio
import logging
import websockets
from websockets import WebSocketServerProtocol

import json
import asyncpg

import boto3
import settings
from datetime import datetime


async def db(message=None):
    conn = await asyncpg.connect(user='vitaliy', password='kpichat2021', 
                                 port=5432, database='chat', 
                                 host='database-1.cf5sj1knwsu7.eu-central-1.rds.amazonaws.com')
    if not message:
        values = await conn.fetch('SELECT * FROM message ORDER BY time DESC LIMIT 10;')
        await conn.close()
        values.reverse()
        return values
    else:
        await conn.fetch(f"INSERT INTO message(author, content, filename) VALUES('{message['from']}', '{message['message']}', '{message.get('filename')}')")
        await conn.close()


async def login(ws, message):
    conn = await asyncpg.connect(user='vitaliy', password='kpichat2021', 
                                 port=5432, database='chat', 
                                 host='database-1.cf5sj1knwsu7.eu-central-1.rds.amazonaws.com')

    login = await conn.fetch(f"SELECT login FROM users WHERE login='{message['login']}' AND password='{message['password']}'")
    print(login)
    if len(login) == 0:
        await ws.send(json.dumps({'login': False}))
    else:
        await ws.send(json.dumps({'login': True, 'username': login[0]['login']}))
    await conn.close()

async def register(ws, message):
    conn = await asyncpg.connect(user='vitaliy', password='kpichat2021', 
                                 port=5432, database='chat', 
                                 host='database-1.cf5sj1knwsu7.eu-central-1.rds.amazonaws.com')

    await conn.fetch(f"INSERT INTO users(login, email, password) VALUES('{message['login']}', '{message['email']}', '{message['password']}');")
    await ws.send(json.dumps({'register': True}))
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
            "from": author,
            "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S")}   

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
            while True:
                message = await ws.recv()
                await self.distribute(ws, message)
        except websockets.exceptions.ConnectionClosedOK as e:
            print(e)
        finally:
            await self.unregister(ws)

    async def distribute(self, ws, data):
        if isinstance(data, bytes):
                new_message = save_file(data, self.name_file, self.author)
                await db(new_message)
                await self.send_to_clients(new_message)
        else:   
            message = json.loads(data)
            if message['command'] == 'fetch_messages':
                await self.fetch_messages(ws)

            elif message['command'] == 'new_message':
                await db(message)
                message = {'command': 'new_message',
                            'message': message['message'],
                            'from': message['from'],
                            "time": datetime.now().strftime("%d.%m.%Y %H:%M:%S")}
                await self.send_to_clients(message)
            elif message['command'] == 'file':
                self.author = message['author']
                self.name_file = message['name']

            elif message['command'] == 'login':
                await login(ws, message)

            elif message['command'] == 'register':
                await register(ws, message)


    async def fetch_messages(self, ws):
        values = await db()
        messages = []
        for i in values:
            messages.append({'command': 'new_message',
                            'message': i['content'],
                            'from': i['author'],
                            'filename': i['filename'],
                            'time': i['time'].strftime("%d.%m.%Y %H:%M:%S")})
        await ws.send(json.dumps(messages))
    
server = Server()
start_server = websockets.serve(server.ws_handler, "localhost", 5000, max_size=500000000)
loop = asyncio.get_event_loop()
loop.run_until_complete(start_server)
loop.run_forever()
