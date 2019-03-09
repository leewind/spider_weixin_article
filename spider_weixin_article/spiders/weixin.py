# -*- coding: utf-8 -*-
import json
import time
import urllib
import pydash
import MySQLdb as mdb
import scrapy
import datetime
from ..items import LSpiderArticleInfo

class WeixinSpider(scrapy.Spider):
    name = "weixin"
    allowed_domains = ["mp.weixin.qq.com"]
    start_urls = ['https://mp.weixin.qq.com/']

    domain = "https://mp.weixin.qq.com"
    list_path = "/mp/profile_ext"

    public_content_list = [
        {
            'biz': 'MjM5ODY0MzY2NQ==',
            'name': u'书单号',
            'avatar': 'http://wx.qlogo.cn/mmhead/Q3auHgzwzM56G7qFdwFDrKdUsW5sRmjOaic4lw2NiayUDhOIIr5kc1Og/0'
        },
        {
            'biz': 'MjM5MDMyMzg2MA==',
            'name': '十点读书',
            'avatar': "http://wx.qlogo.cn/mmhead/Q3auHgzwzM7BmxMfFQA3ic4p0H3Syd79WFu4PiaM3gaB2gicGAXo9hFEQ/0"
        },
        {
            'biz': 'MzAwNTczMzcxMA==',
            'name': '书单来了',
            'avatar': 'http://wx.qlogo.cn/mmhead/Q3auHgzwzM6YiagjsmJUk1pPWBOMLd1RmobelFXZVm0QGUiafAXxOS0g/0'
        },
        {
            'biz': 'MzA5NTU0NzY2Mg==',
            'name': '书单',
            'avatar': 'http://wx.qlogo.cn/mmhead/Q3auHgzwzM4bb32o6aLiau3ibsLscZNv1KS4BYXmNRs5hyKSP0t5dIhw/0'
        },
        {
            'biz': 'MzA4NDMwMDQwNA==',
            'name': '博库悦读',
            'avatar': 'http://wx.qlogo.cn/mmhead/Q3auHgzwzM5TydtkAgH7kCbEdibfnka9anZ5EhJibaUC7ibSrvRibibaYZw/0'
        },
        {
            'biz': 'MjM5NDA3MzQ4MA==',
            'name': '咪咕阅读',
            'avatar': 'http://wx.qlogo.cn/mmhead/Q3auHgzwzM45bFVSQEREbS7T6ovbs4CicyaicCZeqzq2Rhy2M87BvFfA/0'
        },
        {
            'biz': 'MjM5ODA0MjA4MA==',
            'name': '豆瓣阅读',
            'avatar': 'http://wx.qlogo.cn/mmhead/Q3auHgzwzM5E00LQjb5kkRK6cFsicWdcKzncqhViaxyia3QbwChgvoeuA/0'
        }
    ]

    params = {
        'action': 'getmsg',
        'f': 'json',
        'count': 20,
        'scene': 123,
        'is_ok': 1,
        'uin': 'MjY1NjU5ODk4MQ==',
        'wxtoken': '',
        'x5': 0,
        'f': 'json',
    }

    cookies = {
        'wxuin': 2656598981
    }

    client = None

    def get_config(self):
        file_reader = open("config.json", "r")
        config_info = file_reader.read()
        config = json.loads(config_info)
        file_reader.close()
        return config

    def check_not_exist(self, custom_item_id):
        # 查看数据库中是否已经存在爬取数据
        cursor = self.client.cursor()
        query_count_sql = 'SELECT COUNT(*) FROM rough_article_info WHERE custom_item_id=%s'
        cursor.execute(query_count_sql, [
            custom_item_id
        ])
        count = cursor.fetchone()
        cursor.close()

        if count[0] == 0:
            return True
        else:
            return False

    def create_list_url(self, params):
        url = self.domain + self.list_path + '?' + urllib.urlencode(params)
        return url

    def start_requests(self):
        config = self.get_config()
        self.client = mdb.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            passwd=config["passwd"],
            db='spider_rough_base',
            charset=config["charset"]
        )
        self.client.autocommit(True)

        self.params["key"] = config["key"]
        self.params["pass_ticket"] = config["pass_ticket"]

        self.cookies["pass_ticket"] = config["pass_ticket"]
        self.cookies["wap_sid2"] = config["wap_sid2"]

        for public_content in self.public_content_list:
            params = self.params

            params['__biz'] = public_content['biz']
            params['frommsgid'] = 0
            url = self.create_list_url(params)

            meta = {
                'biz': params['__biz'],
                'source': public_content['name']
            }

            yield scrapy.Request(url,
                                 callback=self.parse_list,
                                 cookies=self.cookies,
                                 meta=meta)

    def parse_list(self, response):
        content = json.loads(response.body_as_unicode())

        if content['errmsg'] != 'ok':
            print response.body
        else:
            article_list = json.loads(content['general_msg_list'])
            now = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')

            for article in article_list['list']:
                if article.has_key('app_msg_ext_info'):
                    article_info = LSpiderArticleInfo(
                        abstract=article['app_msg_ext_info']['digest'],
                        go_detail_count=None,
                        article_type='article',
                        comments_count=None,
                        channel='weixin',
                        cover_image_url=article['app_msg_ext_info']['cover'],
                        title=article['app_msg_ext_info']['title'],
                        source=response.meta['source'],
                        detail_url=article['app_msg_ext_info']['content_url'],
                        created_time=now,
                        update_time=now,
                        published_time=datetime.datetime.fromtimestamp(article['comm_msg_info']['datetime']).strftime('%Y-%m-%d %H:%M:%S'),
                        custom_item_id='weixin_' +
                        str(article['comm_msg_info']['id']),
                    )

                    if self.check_not_exist(article_info.get('custom_item_id')):
                        yield scrapy.Request(article_info.get('detail_url'),
                                             callback=self.parse_content,
                                             cookies=self.cookies,
                                             meta={'article_info': article_info})

            # 对于增量需要再次做验证
            if content['can_msg_continue'] == 1:
                params = self.params

                params['__biz'] = response.meta['biz']

                min_one = pydash.numerical.min_by(
                    article_list['list'], 'comm_msg_info.id')
                params['frommsgid'] = min_one['comm_msg_info']['id']

                url = self.create_list_url(params)
                yield scrapy.Request(url,
                                     callback=self.parse_list,
                                     cookies=self.cookies,
                                     meta=response.meta)

    def parse_content(self, response):
        article_info = response.meta['article_info']

        context = response.css('#img-content').extract_first()
        article_info['context'] = context

        yield article_info
