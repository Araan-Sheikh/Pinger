import motor.motor_asyncio
import os
import asyncio
from datetime import datetime, timedelta
import urllib.parse
from pymongo import UpdateOne

print('database')

loop = asyncio.get_event_loop()

with open('bannedhosts.txt', 'r') as f:
	banned_hosts = f.read().splitlines()

class UrlAlreadyExists(Exception): pass

class Database:
	def __init__(self):
		self.username = os.getenv('dbuser')
		self.password = urllib.parse.quote_plus(os.getenv('dbpass'))
		connect_url = f'mongodb+srv://{self.username}:{self.password}@cluster0-eu9e0.mongodb.net/ping?retryWrites=true&w=majority'
		self.conn = motor.motor_asyncio.AsyncIOMotorClient(connect_url)
		self.db = self.conn['ping']
		self.data = self.db.data
		self.url_cache = set()

	async def delete_old(self):
		print('Deleting dead sites')
		async for url in self.data.find({
			'last_online': {'$lt': datetime.now() - timedelta(days=30)}
		}):
			print('deleting', url)
		await self.data.delete_many({
			'last_online': {'$lt': datetime.now() - timedelta(days=30)}
		})
		for host in banned_hosts:
			result = await self.data.delete_many({
				'host': host
			})
			print(host, result.deleted_count)

	async def add_url(self, raw_url):
		url = urllib.parse.urlparse(raw_url)
		host = url.netloc
		path = url.path.strip('/')
		raw_url = f'https://{host}/{path}'
		if host in banned_hosts: return print('attempted to add banned host >:(')
		await self.data.update_one({
			'url': raw_url
		}, {
			'$set': {
				'last_online': datetime.now(),
				'added_on': datetime.now(),
				'host': host
			}
		}, upsert=True)
	
	async def update_last_online(self, urls):
		requests = []
		now = datetime.now()
		for url in urls:
			if not url: continue
			requests.append(UpdateOne({
				'url': url
			}, {
				'$set': {
					'last_online': now
				}
			}))
		if not requests: return
		await self.data.bulk_write(requests)

	async def get_urls(self):
		async for website in self.data.find({}):
			if 'url' in website:
				yield website


db = Database()