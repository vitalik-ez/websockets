import asyncio
import asyncpg

async def run():
    conn = await asyncpg.connect(user='postgres', password='123',
                                 database='chat', host='127.0.0.1')
    values = await conn.fetch('SELECT * FROM message')
    print(values[0]['id'])
    await conn.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(run())