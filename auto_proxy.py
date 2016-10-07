#! /usr/bin/env python
#coding:utf-8

from bs4 import BeautifulSoup 
import requests
import re
import time
from multiprocessing.dummy import Pool as ThreadPool


class Proxy(object):
    def __init__(self, max_page=1):
        self.timestamp = time.time()
        self.max_page = max_page
        self.proxies = []
        self.checked_proxies = []
        self.s = requests.Session()
        self.headers = {
            'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding' :'gzip, deflate, sdch',
            'Accept-Language' : 'zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,zh-TW;q=0.2',
            'Connection' : 'keep-alive',
            'Host' : 'www.xicidaili.com',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
        }
        self.s.headers.update(self.headers)
        self.url = 'http://www.xicidaili.com/nn/'

    def _parse_proxy(self):
        res = self.s.get(self.url)
        try:
            soup = BeautifulSoup(res.content, 'html.parser')
            tr_tags = soup.find('table', {'id' : 'ip_list'}).find_all('tr')
            for tr in tr_tags:
                tds = tr.find_all('td')
                if not tds: # ignore title
                    continue
                
                time_tag = tds[6].find('div', {'class' : 'bar'}, title=True)
                if time_tag:
                    time = re.search('\d+.\d+', str(time_tag)).group()
                    if float(time) > 4:
                        continue
                
                ip = tds[1].text
                port = tds[2].text
                schema = tds[5].text
                # conn_time = 
                if schema == 'HTTPS':
                    self.proxies.append({'https' : ip + ':' + port})
                else:
                    self.proxies.append({'http' : ip + ':' + port})
        except Exception as e:
            print(u'代理获取异常：{}'.format(e))

    def _check_proxy(self, proxy, anonymous=True):

        try:
            r = requests.get('http://httpbin.org/ip', proxies=proxy, timeout=3)
            data = r.json()
            # 高匿检测
            if anonymous:
                if data['origin'] == proxy.values()[0].split(':')[0]:
                    self.checked_proxies.append(proxy)
            else:
                self.checked_proxies.append(proxy)
        except Exception as e:
            pass

    def get_proxy(self):
        time_distance = time.time() - self.timestamp
        if len(self.checked_proxies) == 0 or time_distance > 60 * 30:
            print(u'刷新代理池...')
            self.proxies = []
            self.checked_proxies = []
            self._parse_proxy()
            pool = ThreadPool(8)
            pool.map(self._check_proxy, self.proxies)
            pool.close()
            pool.join()
            self.timestamp = time.time()
            print(u'新的代理池: \n{}\n'.format(self.checked_proxies))
        return self.checked_proxies


if __name__ == '__main__':
    ins = Proxy()
    print ins.get_proxy()