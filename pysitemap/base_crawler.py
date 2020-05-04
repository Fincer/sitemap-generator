import logging
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

    def __init__(self, rooturl, out_file, out_format='xml', maxtasks=10, exclude_urls=[], exclude_imgs=[],
                 image_root_urls=[], verifyssl=True, headers=None, timezone_offset=0, changefreq=None, priorities=None,
                 todo_queue_backend=set, done_backend=dict, done_images=list):
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
        :param exclude_imgs: excludable img url paths relative to root url
        :type exclude_imgs: list
        :param image_root_urls: recognized image root urls on the domain
        :type image_root_urls: list
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
        self.exclude_imgs = exclude_imgs
        self.image_root_urls = image_root_urls
        self.todo_queue = todo_queue_backend()
        self.busy = set()
        self.done = done_backend()
        self.done_images = done_images()
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

    async def mimechecker(self, url, expected):
        """
        Check url resource mimetype
        """

        self.todo_queue.remove(url)
        self.busy.add(url)

        try:
            resp = await self.session.get(url)
        except Exception as exc:
            pass
        else:
            mime = resp.headers.get('content-type')
            if (resp.status == 200 and
                bool(re.search(re.compile(r'{}'.format(expected)), mime))):
                resp.close()
                self.busy.remove(url)
                return True
        resp.close()
        self.busy.remove(url)
        return False

    async def fetchtags(self, data, url, tag_input, fields=[]):
        """
        Find and sort all target tags from website data
        """
        tags = []
        lines_join = []
        for line in data.split('\n'):
            lines_join.append(line)

        tags_raw = re.findall(re.compile(r'<{}.*?>'.format(tag_input)), ' '.join(lines_join))

        for tag_raw in tags_raw:
            tag_raw = re.sub(re.compile(r'<{}(.*?)>'.format(tag_input)), '\\1', tag_raw)

            # Regex lookahead + lookbehind
            # Find patterns, where pattern start with "<word>=" and ends with " <word>="
            # Include the first pattern, which will be used to determine
            # value which the pattern holds in it

            # TODO Note: this method is error-prone, since it assumes that...
            #  ... no argument value inside <img ... /> tag has value of "<somechar>="
            #  If this happens, args regex findall & splitting (below) fails.
            args_raw = re.findall(r'(?i)(?=[\w]+[=]|[\w\"\'])(.*?)(?=\s[\w]+[=])', tag_raw)
            tag = []
            for arg_raw in args_raw:
                arg = arg_raw.split('=')
                if len(arg) != 2:
                    print("warning: failure on tag data parsing operation.")
                    continue

                arg_dict = {}
                key = arg[0]
                # Remove leading and trailing quote marks from value
                value = re.sub(r'^["\']?(.*?)["\']?$', '\\1', arg[1])

                for field in fields:
                    if key == field:
                        arg_dict[field] = value
#                    else:
#                        print("warning: ignoring tag data value:", key)

                if len(arg_dict) == 1:
                    tag.append(arg_dict)
            tags.append(tag)
        return tags

    async def addtagdata(self, tagdata, url, source_url_field,
                            mimetype, tag_root_urls=[], excludes=[],
                            done_list=[], this_domain=True):
        """
        Validate existence of url in given tagdata
        :return: dictionary of validated tags (of single type)
        """
        tags = []
        for data in tagdata:
            for tag in data:
                if not source_url_field in tag:
                    continue
                if not await self.contains(tag[source_url_field], excludes, rlist=True):

                    if this_domain:
                        if not tag[source_url_field].startswith('http'):
                            for tag_root_url in tag_root_urls:
                                if url.startswith(tag_root_url):
                                    tag[source_url_field] = tag_root_url + tag[source_url_field]
                                    break
                    else:
                        if not tag[source_url_field].startswith('http'):
                            continue

                    if (tag[source_url_field].startswith('http') and
                        data not in done_list and
                        tag[source_url_field] not in self.busy and
                        tag[source_url_field] not in self.todo_queue):
                        self.todo_queue.add(tag[source_url_field])
                        # Acquire semaphore
                        await self.sem.acquire()
                        # Create async task
                        task = asyncio.ensure_future(self.mimechecker(tag[source_url_field], mimetype))
                        # Add collback into task to release semaphore
                        task.add_done_callback(lambda t: self.sem.release())
                        # Callback to remove task from tasks
                        task.add_done_callback(self.tasks.remove)
                        # Add task into tasks
                        self.tasks.add(task)
                        try:
                            result = await asyncio.wait_for(task, timeout=20)
                            if (result):
                                tags.append(data)

                        except asyncio.TimeoutError:
                            print("couldn't add tag data:", tag[source_url_field])
                            task.cancel()
                            pass

            done_list.extend(tags)
        return tags

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
        imgs = []

        try:
            resp = await self.session.get(url)  # await response
        except Exception as exc:
            # on any exception mark url as BAD
            print('...', url, 'has error', repr(str(exc)))
            self.done[url] = [False, lastmod, cf, pr, imgs]
        else:
            # only url with status == 200 and content type == 'text/html' parsed
            if (resp.status == 200 and
                    ('text/html' in resp.headers.get('content-type'))):
                data = (await resp.read()).decode('utf-8', 'replace')
                urls = re.findall(r'(?i)href=["\']?([^\s"\'<>]+)', data)

                lastmod = resp.headers.get('last-modified')

                # Ref: https://support.google.com/webmasters/answer/178636?hl=en
                img_data = await self.fetchtags(
                            data, url, 'img',
                            fields=['src', 'title', 'caption', 'geo_location', 'license']
                )
                imgs = await self.addtagdata(
                        tagdata=img_data, url=url,
                        source_url_field='src', mimetype='^image\/',
                        tag_root_urls=self.image_root_urls,
                        excludes=self.exclude_imgs,
                        done_list=self.done_images,
                        this_domain=True
                )

                asyncio.Task(self.addurls([(u, url) for u in urls]))

                try: pr = await self.urldict(url, self.changefreq)
                except IndexError: pass

                try: cf = await self.urldict(url, self.priorities)
                except IndexError: pass

            # even if we have no exception, we can mark url as good
            resp.close()

            self.done[url] = [True, lastmod, cf, pr, imgs]

        self.busy.remove(url)
        logging.info(len(self.done), 'completed tasks,', len(self.tasks),
              'still pending, todo_queue', len(self.todo_queue))
