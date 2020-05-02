import asyncio
from aiofile import AIOFile, Reader, Writer
import logging
from datetime import datetime, timezone, timedelta

class XMLWriter():
    def __init__(self, filename: str):
        self.filename = filename


    async def write(self, urls, timezone_offset):
        async with AIOFile(self.filename, 'w') as aiodf:
            writer = Writer(aiodf)
            await writer('<?xml version="1.0" encoding="utf-8"?>\n')
            await writer(
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
                ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
                ' xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">\n')
            await aiodf.fsync()
            for data in urls:

                timestamp  = data[1][1]
                changefreq = data[1][2]
                priority   = data[1][3]
                url = "<loc>{}</loc>".format(data[0])

                if timestamp is not None:
                    timestamp = datetime.strptime(timestamp, "%a, %d %b %Y %H:%M:%S %Z").astimezone(tz=timezone(timedelta(hours=timezone_offset))).isoformat()
                    url += "<lastmod>{}</lastmod>".format(str(timestamp))

                if changefreq is not None:
                    url += "<changefreq>{}</changefreq>".format(str(changefreq))

                if priority is not None:
                    url += "<priority>{}</priority>".format(str(priority))

                await writer('<url>{}</url>\n'.format(url))

            await aiodf.fsync()

            await writer('</urlset>')
            await aiodf.fsync()
