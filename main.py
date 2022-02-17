import asyncio
import aiohttp
from aiohttp import web
from database import db
import urllib.parse


loop = asyncio.get_event_loop()

with open('index.html', 'r') as f:
	index_html = f.read()

with open('bannedhosts.txt', 'r') as f:
	banned_hosts = f.read().splitlines()


async def attempt_ping(url, s):
	try:
		async with s.get(url) as r: await r.read()
		return url
	except: return None

async def main():
	await db.delete_old()
	while True:
		timeout = aiohttp.ClientTimeout(total=3)
		async with aiohttp.ClientSession(timeout=timeout) as s:
			try:
				print(f'Pinging sites')
				futures = []
				url_count = 0
				async for website in db.get_urls():
					url = website['url']

					future = asyncio.ensure_future(
						attempt_ping(url, s)
					)
					futures.append(future)
					url_count += 1
					if len(futures) > 100:
						working_urls = await asyncio.gather(*futures)
						futures = []
						print('.')
				if len(futures) > 100:
					working_urls = await asyncio.gather(*futures)
				print(f'Pinged {url_count} urls')
				await db.update_last_online(working_urls)
				print('Updated database with last updated times')
			except Exception as e:
				print('ree', e)
		await asyncio.sleep(60 * 10)

def check_blacklisted(url):
	url = urllib.parse.urlparse(url)
	host = url.netloc
	return host in banned_hosts


async def check_valid_url(url):
	url = urllib.parse.urlparse(url)
	host = url.netloc
	path = url.path.strip('/')
	url = f'https://{host}/{path}'

	try:
		timeout = aiohttp.ClientTimeout(total=10)
		async with aiohttp.ClientSession(timeout=timeout) as s:
			r = await s.get(url)
			print(url, r.status)
			return True
	except Exception as e:
		print(e)
		return False

async def check_replit(url, s=None):
	url = urllib.parse.urlparse(url)
	host = url.netloc
	url = f'https://{host}/__repl'
	own_session = False
	if not s:
		timeout = aiohttp.ClientTimeout(total=30)
		s = aiohttp.ClientSession(timeout=timeout)
		own_session = True

	try:
		r = await s.get(url)
		if own_session: await s.close()
		if str(r.status)[0] == '4' and not str(r.url).startswith('https://replit.com/'):
			print(r.status, str(r.url))
			return False
		print(url, r.url, r.status)
		return True
	except Exception as e:
		print(type(e), e, 'bruh!')
		if own_session: await s.close()
		return True
		# return False

routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
	return web.Response(text=index_html, content_type='text/html')


@routes.post('/')
async def POST_add_url(request):
	post_data = await request.post()
	url = post_data.get('url').strip()
	if check_blacklisted(url):
		return
	if url in db.url_cache:
		output_text = 'Already submitted'
	else:
		is_valid = await check_valid_url(url)
		is_replit = await check_replit(url)
		if not is_replit and is_valid:
			return web.HTTPFound('/#Not a replit url')
			output_text = 'Not a replit url :('
		elif is_valid:
			output_text = 'Epic'
			await db.add_url(url)
			return web.HTTPFound('/#Added!')
		else:
			return web.HTTPFound('/#Invalid url (is the website down?).')
			output_text = 'Invalid url :('
	return web.Response(text=output_text, content_type='text/html')


app = web.Application()
app.add_routes(routes)
asyncio.ensure_future(main())
web.run_app(app, port=6969)