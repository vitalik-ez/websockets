import asyncio
import websockets

async def produce(message: str, host: str, port: int) -> None:
	async with websockets.connect(f"ws://{host}:{port}") as ws:
		await ws.send(message)
		await ws.recv()


loop = asyncio.get_event_loop()
loop.run_until_omplete(produce(message='hi', host='localhost', port=4000))
#asyncio.run()