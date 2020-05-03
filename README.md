# pysitemap

> Sitemap generator

## Installation

```
pip install sitemap-generator
```

## Requirements

```
asyncio
aiofile
aiohttp
```

## Example 1

```
import sys
import logging
from pysitemap import crawler

if __name__ == '__main__':
    if '--iocp' in sys.argv:
        from asyncio import events, windows_events
        sys.argv.remove('--iocp')
        logging.info('using iocp')
        el = windows_events.ProactorEventLoop()
        events.set_event_loop(el)

    # root_url = sys.argv[1]
    root_url = 'https://www.haikson.com'
    crawler(root_url, out_file='sitemap.xml')
```

## Example 2

```
import sys
import logging
from pysitemap import crawler

if __name__ == '__main__':
    root_url = 'https://mytestsite.com/'
    crawler(
        root_url,
        out_file='sitemap.xml',
        maxtasks=100,
        verifyssl=False,
        exclude_urls=[
            '/git/.*(action|commit|stars|activity|followers|following|\?sort|issues|pulls|milestones|archive|/labels$|/wiki$|/releases$|/forks$|/watchers$)',
            '/git/user/(sign_up|login|forgot_password)',
            '/css',
            '/js',
            'favicon',
            '[a-zA-Z0-9]*\.[a-zA-Z0-9]*$',
            '\?\.php',
        ],
        exclude_imgs=[
            'logo\.(png|jpg)',
            'avatars',
            'avatar_default',
            '/symbols/'
        ],
        image_root_urls=[
            'https://mytestsite.com/photos/',
            'https://mytestsite.com/git/',
        ],
        headers={'User-Agent': 'Crawler'},
        # TZ offset in hours
        timezone_offset=3,
        changefreq={
          "/git/": "weekly",
          "/":     "monthly"
        },
        priorities={
          "/git/": 0.7,
          "/metasub/": 0.6,
          "/": 0.5
        }
    )
```

### TODO

-  big sites with count of pages more then 100K will use more then 100MB
   memory. Move queue and done lists into database. Write Queue and Done
   backend classes based on
-  Lists

-  SQLite database

-  Redis

-  Write api for extending by user backends

## Changelog

**v. 0.9.3**

Added features:

- Option to enable/disable website SSL certificate verification (True/False)

- Option to exclude URL patterns (`list`)

- Option to provide custom HTTP request headers to web server (`dict`)

- Add support for `<lastmod>` tags (XML)

    - Configurable timezone offset for lastmod tag

- Add support for `<changefreq>` tags (XML)

    - Input (`dict`): `{ url_regex: changefreq_value, url_regex: ... }`

- Add support for `<priority>` tags (XML)

    - Input (`dict`): `{ url_regex: priority_value, url_regex: ... }`

- Reduce default concurrent max tasks from `100` to `10`

**v. 0.9.2**

-  todo queue and done list backends

-  created very slowest sqlite backend for todo queue and done lists (1000 url writing for 3 minutes)

-  tests for sqlite_todo backend

**v. 0.9.1**

-  extended readme

-  docstrings and code commentaries

**v. 0.9.0**

-  since this version package supports only python version `>=3.7`

-  all functions recreated but api saved. If You use this package, then
   just update it, install requirements and run process

-  all requests works asynchronously

