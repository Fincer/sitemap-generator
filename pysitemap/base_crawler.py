kimport logging
import asyncio
import re
import urllib.parse
from pysitemap.format_processors.xml import XMLWriter
from pysitemap.format_processors.text import TextWriter
import aiohttp


class Crawler:

    format_processors = {
        'xml': XMLWriter,
        'txt': TextWriter
    }

    def __init__(self, rooturl, out_file, out_format='xml', maxtasks=10, exclude_urls=[], verifyssl=True,
                 headers=None, timezone_offset=0, changefreq=None, priorities=None,
                 todo_queue_backend=set, done_backend=dict):
        """
        Crawler constructor
        :param rooturl: root url of site
        :type rooturl: str
        :param out_file: file to save sitemap result
        :type out_file: str
        :param out_format: sitemap type [xml | txt]. Default xml
        :type out_format: str
        :param maxtasks: maximum count of tasks. Default 10
        :type maxtasks: int
        :param exclude_urls: excludable url paths relative to root url
        :type exclude_urls: list
        :param verifyssl: verify website certificate?
        :type verifyssl: boolean
        :param timezone_offset: timezone offset for lastmod tags
        :type timezone_offset: int
        :param changefreq: dictionary, where key is site sub url regex, and value is changefreq
        :type changefreq: dict
        :param priorities: dictionary, where key is site sub url regex, and value is priority float
        :type priorities: dict
        """
        self.rooturl = rooturl
        self.exclude_urls = exclude_urls
        self.todo_queue = todo_queue_backend()
        self.busy = set()
        self.done = done_backend()
        self.tasks = set()
        self.sem = asyncio.Semaphore(maxtasks)
        self.timezone_offset = timezone_offset
        self.changefreq = changefreq
        self.priorities = priorities

        # connector stores cookies between requests and uses connection pool
        self.session = aiohttp.ClientSession(
            headers=headers,
            connector=aiohttp.TCPConnector(verify_ssl=verifyssl)
        )
        self.writer = self.format_processors.get(out_format)(out_file)

    async def run(self):
        """
        Main function to start parsing site
        :return:
        """
        t = asyncio.ensure_future(self.addurls([(self.rooturl, '')]))
        await asyncio.sleep(1)
        while self.busy:
            await asyncio.sleep(1)

        await t
        await self.session.close()
        await self.writer.write([(key, value) for key, value in self.done.items() if key and value], self.timezone_offset)

    async def contains(self, url, regex, rlist=True):
        """
        Does url path matches a value in regex_list?
        """
        retvalue = False
        if rlist:
            for exc in regex:
                retvalue = bool(re.search(re.compile(r"{}".format(exc)), url))
                if retvalue: return retvalue
        else:
            retvalue = bool(re.search(re.compile(r"{}".format(regex)), url))
        return retvalue

    async def urldict(self, url, url_dict):
        """
        Parse URL regex (key) and value pairs
        """
        for urlkey, regvalue in url_dict.items():
            if await self.contains(url, urlkey, rlist=False):
                return regvalue
        return None

    async def addurls(self, urls):
        """
        Add urls in queue and run process to parse
        :param urls:
        :return:
        """
        for url, parenturl in urls:
            url = urllib.parse.urljoin(parenturl, url)
            url, frag = urllib.parse.urldefrag(url)

            if (url.startswith(self.rooturl) and
                    not await self.contains(url, self.exclude_urls, rlist=True) and
                    url not in self.busy and
                    url not in self.done and
                    url not in self.todo_queue):
                self.todo_queue.add(url)
                # Acquire semaphore
                await self.sem.acquire()
                # Create async task
                task = asyncio.ensure_future(self.process(url))
                # Add collback into task to release semaphore
                task.add_done_callback(lambda t: self.sem.release())
                # Callback to remove task from tasks
                task.add_done_callback(self.tasks.remove)
                # Add task into tasks
                self.tasks.add(task)

    async def process(self, url):
        """
        Process single url
        :param url:
        :return:
        """
        print('processing:', url)

        # remove url from basic queue and add it into busy list
        self.todo_queue.remove(url)
        self.busy.add(url)

        lastmod = None
        cf = None
        pr = None

        try:
            resp = await self.session.get(url)  # await response
        except Exception as exc:
            # on any exception mark url as BAD
            print('...', url, 'has error', repr(str(exc)))
            self.done[url] = [False, lastmod, cf, pr]
        else:
            # only url with status == 200 and content type == 'text/html' parsed
            if (resp.status == 200 and
                    ('text/html' in resp.headers.get('content-type'))):
                data = (await resp.read()).decode('utf-8', 'replace')
                urls = re.findall(r'(?i)href=["\']?([^\s"\'<>]+)', data)
                lastmod = resp.headers.get('last-modified')

                asyncio.Task(self.addurls([(u, url) for u in urls]))

                try: pr = await self.urldict(url, self.changefreq)
                except IndexError: pass

                try: cf = await self.urldict(url, self.priorities)
                except IndexError: pass

            # even if we have no exception, we can mark url as good
            resp.close()

            self.done[url] = [True, lastmod, cf, pr]

        self.busy.remove(url)
        logging.info(len(self.done), 'completed tasks,', len(self.tasks),
              'still pending, todo_queue', len(self.todo_queue))
