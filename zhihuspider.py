# --------------------------------------------
# Author: flyer <flyer103@gmail.com>
# Date: 2015-01-23 22:48:36
# --------------------------------------------

"""抓取知乎问题的爬虫.
"""

import os
import sys
import json
import urllib

import requests
from lxml import etree
from lxml.html import document_fromstring

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import get_configs
from logger.mylogger import Logger

log_main = Logger.get_logger(__file__)


class ZhihuSpider(object):
    """抓取知乎问题的爬虫"""
    def __init__(self):
        self.dir_root = os.path.dirname(os.path.abspath(__file__))

        fname_settings = os.path.join(self.dir_root, 'settings.yaml')
        self.configs = get_configs(fname_settings)

        self.url_homepage = self.configs['URL']['HOMEPAGE']
        self.headers_base = self.configs['HEADERS']['BASE']

        self.url_login = self.configs['URL']['LOGIN']
        self.email = self.configs['AUTH']['EMAIL']
        self.password = self.configs['AUTH']['PASSWORD']
        self.payload_login = {
            'email': self.email,
            'password': self.password,
            'rememberme': 'y',
        }

        self.url_questions = self.configs['URL']['QUESTIONS']
        self.payload_question = self.configs['PAYLOAD']['QUESTION']

        self.url_question_prefix = self.configs['URL']['QUESTION_PREFIX']

        self.timeout_query = self.configs['TIMEOUT']['QUERY']

        self.offset = self.configs['OFFSET']

        self.spider = requests.Session()

    def login(self):
        """登陆"""
        xsrf = self._get_xsrf(url=self.url_homepage)
        self.payload_login['_xsrf'] = xsrf

        try:
            self.spider.post(self.url_login,
                             headers=self.headers_base,
                             data=self.payload_login,
                             timeout=self.timeout_query)
        except Exception as e:
            log_main.error('Failed to try to login. Error: {0}'.format(e))
            sys.exit(-1)

        if self._test_login():
            log_main.info('Login successfully!')
        else:
            log_main.info('Faile to Login! Exit.')
            sys.exit(-1)

    def crawl_questions(self, start=None, offset=None):
        """抓取知乎问题"""
        xsrf = self._get_xsrf(url=self.url_questions)
        self.payload_question['_xsrf'] = xsrf

        while True:
            self.payload_question['start'] = start
            self.payload_question['offset'] = offset

            try:
                res = self.spider.post(self.url_questions,
                                       headers=self.headers_base,
                                       data=self.payload_question,
                                       timeout=self.timeout_query)
            except Exception as e:
                log_main.error('Fail to fetch the page. Error: {0}.'.format(e))
                sys.exit(-1)

            start = self._parse_json(res.text)

    def run(self):
        """总控"""
        self.login()

        start = self._crawl_first_question()

        self.crawl_questions(start=start, offset=self.offset)

    def _get_xsrf(self, url=None):
        try:
            res = self.spider.get(url,
                                  headers=self.headers_base,
                                  timeout=self.timeout_query)
        except Exception as e:
            log_main.error('Failed to fetch {0}. Error: {1}'.format(url, e))
            sys.exit(-1)

        try:
            html_con = etree.HTML(res.text)
        except Exception as e:
            log_main.error('Fail to form dom tree. Error: {1}'.format(url, e))
            sys.exit(-1)

        node_xsrf = html_con.xpath("//input[@name='_xsrf']")[0]

        xsrf = node_xsrf.xpath("@value")[0]

        log_main.info('xsrf for {0}: {1}'.format(url, xsrf))

        return xsrf

    def _test_login(self):
        """测试是否登陆成功.

        Output:
        + 测试成功时返回 True，否则返回 False.
        """
        try:
            res = self.spider.get(self.url_homepage,
                                  headers=self.headers_base,
                                  timeout=self.timeout_query)
        except Exception as e:
            log_main.error('Error when testing login: {0}'.format(e))
            return False

        try:
            html_con = etree.HTML(res.text)
        except Exception as e:
            log_main.error('Failed to set dom tree: {0}'.format(e))
            return False

        node_list_title = html_con.xpath("//div[@id='zh-home-list-title']")

        if node_list_title:
            return True
        else:
            return False

    def _crawl_first_question(self):
        """抓取知乎问题首页第一个问题的编号"""
        try:
            res = self.spider.get(self.url_questions,
                                  headers=self.headers_base,
                                  timeout=self.timeout_query)
        except Exception as e:
            log_main.error('Fail to fetch question page. Error: {0}'.format(e))
            sys.exit(-1)

        try:
            html_con = etree.HTML(res.text)
        except Exception as e:
            log_main.error('Error: {0}'.format(e))
            sys.exit(-1)

        node_item = html_con.xpath("//div[@id='zh-global-logs-questions-wrap']/div")[0]

        _id = node_item.xpath("@id")[0].split('-')[-1]

        log_main.info('the id of the first question is: {0}'.format(_id))

        return _id

    def _parse_json(self, string):
        res_json = json.loads(string)['msg']
        try:
            html = document_fromstring(res_json[1])
        except Exception as e:
            log_main.error(e)
            sys.exit(-1)

        nodes = html.xpath("/html/body/div")

        for node in nodes:
            # logitem_id = int(node.xpath('@id')[0].split('-')[-1])

            title_node = node.xpath("./h2[@class='zm-item-title']/a")[0]
            question_url = title_node.xpath('@href')[0]
            question_url = urllib.parse.urljoin(self.url_question_prefix,
                                                question_url)
            question_title = title_node.text

            try:
                who_node = node.xpath("./div/a")[0]
                who_name = who_node.text
                who_url = who_node.xpath("@href")[0]
                who_url = urllib.parse.urljoin(self.url_question_prefix,
                                               who_url)
            except Exception as e:
                log_main.warning('Failed to get poster for {0}'.format(question_url))
                who_name = ''
                who_url = ''

            question_time = node.xpath(".//time")[0].text

            msg = "quesion: {0}[{1}]. people: {2}[{3}]. time: {4}".format(
                question_title,
                question_url,
                who_name,
                who_url,
                question_time
            )

            log_main.info(msg)

        last_id = int(nodes[-1].xpath('@id')[0].split('-')[-1])

        return last_id


if __name__ == '__main__':
    zhihu_spider = ZhihuSpider()
    zhihu_spider.run()
