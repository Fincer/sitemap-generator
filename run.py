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

