import asyncio
import signal
from pysitemap.base_crawler import Crawler


def crawler(
    root_url, out_file, out_format='xml',
    maxtasks=10, exclude_urls=list, exclude_imgs=list, image_root_urls=list,
    verifyssl=True, headers=None, timezone_offset=0, changefreq=None,
    priorities=None):
    """
    run crowler
    :param root_url: Site root url
    :param out_file: path to the out file
    :param out_format: format of out file [xml, txt]
    :param maxtasks: max count of tasks
    :param exclude_urls: excludable url paths
    :param exclude_imgs: excludable img url paths
    :param image_root_urls: recognized image root urls on the domain
    :param verifyssl: verify website certificate?
    :param headers: Send these headers in every request
    :param timezone_offset: timezone offset for lastmod tags
    :param changefreq: dictionary, where key is site sub url regex, and value is changefreq
    :param priorities: dictionary, where key is site sub url regex, and value is priority float
    :return:
    """
    loop = asyncio.get_event_loop()

    c = Crawler(root_url, out_file=out_file, out_format=out_format,
                maxtasks=maxtasks, exclude_urls=exclude_urls, exclude_imgs=exclude_imgs,
                image_root_urls=image_root_urls, verifyssl=verifyssl,
                headers=headers, timezone_offset=timezone_offset,
                changefreq=changefreq, priorities=priorities)

    loop.run_until_complete(c.run())

    try:
        loop.add_signal_handler(signal.SIGINT, loop.stop)
    except RuntimeError:
        pass
    print('todo_queue:', len(c.todo_queue))
    print('busy:', len(c.busy))
    print('done:', len(c.done), '; ok:', sum(list(zip(*c.done.values()))[0]) )
    print('tasks:', len(c.tasks))
