#! /usr/bin/env python
#coding:utf-8

import threading
import sqlite3
import random
import urlparse
import re
import time
from datetime import datetime
from requests import Session
from requests.exceptions import ProxyError, ConnectTimeout
from bs4 import BeautifulSoup
from multiprocessing.dummy import Pool

from auto_proxy import Proxy

class SQLiteHelper:
    def __init__(self, db_path):
        self.db_path = db_path

    def conn_transaction(func):
        def connection(self, *args, **kwargs):
            conn = sqlite3.connect(self.db_path)
            kwargs['conn'] = conn
            result = func(self, *args, **kwargs)
            conn.close()
            return result
        return connection

    @conn_transaction
    def execute(self, command, params=None, conn=None):
        cursor = conn.cursor()
        result = 0
        try:
            if params:
                cursor.execute(command, params)
            else:
                cursor.execute(command)
            conn.commit()
        except Exception as e:
            print e
            conn.rollback()
            result = -1
        finally:
            cursor.close()
        return result

    @conn_transaction
    def fetch_data(self, command, conn=None):
        cursor = conn.cursor()
        result = []
        try:
            cursor.execute(command)
            result = cursor.fetchall()
        except Exception as e:
            print e
        finally:
            cursor.close()
        return result

    def format_insert_params(self, column_name_list, params):
        result = []
        for col in column_name_list:
            if col in params:
                result.append(params[col])
            else:
                result.append('')
        return tuple(result)

HEADER_UA_LIST = [{'User-Agent':'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6'},\
    {'User-Agent':'Mozilla/5.0 (Windows NT 6.2) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.12 Safari/535.11'},\
    {'User-Agent':'Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)'},\
    {'User-Agent':'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:34.0) Gecko/20100101 Firefox/34.0'},\
    {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/44.0.2403.89 Chrome/44.0.2403.89 Safari/537.36'},\
    {'User-Agent':'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'},\
    {'User-Agent':'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50'},\
    {'User-Agent':'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0'},\
    {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:2.0.1) Gecko/20100101 Firefox/4.0.1'},\
    {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1'},\
    {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'},\
    {'User-Agent':'Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; en) Presto/2.8.131 Version/11.11'},\
    {'User-Agent':'Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11'}]


class Crawler:
    def __init__(self):
        self.proxies_list = [] 

    def crawl(self, url):
        proxy = None
        if len(self.proxies_list) > 0:
            proxy = self.proxies_list[random.randint(0, len(self.proxies_list) - 1)]
            print(u'使用代理 {}'.format(self.timestamp))
        try:
            res = Session().get(url, headers=HEADER_UA_LIST[random.randint(0, len(HEADER_UA_LIST) - 1)], proxies=proxy, timeout=15)
            soup = BeautifulSoup(res.content, 'html.parser')

            soup_content = soup.encode_contents(encoding='utf-8')
            if soup_content.find(u'您所在的IP流量异常'.encode('utf-8')) != -1:
                return -2
        except (ProxyError, ConnectTimeout):
            self.proxies_list.remove(proxy)
            self.crawl(url)
            
        except Exception as e:
            print 'Crawl {} error: {}'.format(url, e) 
            return -1
        else:
            return self.extract_func(soup, res)

    def start_thread_pool(self, func, args, nums=8):
        thread_pool = Pool(processes=nums)
        thread_pool.map(func, args)
        thread_pool.close()
        thread_pool.join()
        del thread_pool

    def extract_func(self, soup, res):
        pass # 需要子类实现

    @property
    def timestamp(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M;%S')


class ChengquCrawler(Crawler):
    def __init__(self, database, base_url='http://bj.lianjia.com', path='/xiaoqu/'):
        Crawler.__init__(self)
        self.base_url = base_url
        self.path = path
        self.database = database

    def crawl(self):
        result = self.fetchall()
        if len(result) == 0:
            return Crawler.crawl(self, self.base_url + self.path)
        else:
            return 0

    def extract_func(self, soup, res):
        try:
            tag = soup.find('div', {'class' : 'position'}).find('a', {'href' : '/xiaoqu/'})
            city = tag['title'].replace(u'小区区域', '')
        except Exception as e:
            print '解析城市失败 {}'.format(e)
            return -1
        else:
            try:
                tag_list = soup.find('div', {'data-role' : 'ershoufang'}).find_all('a', href=True)
                info_dict = {}
                for t in tag_list:
                    try:
                        info_dict['url'] = self.base_url + t['href']
                        info_dict['name'] = t.text
                        info_dict['city'] = city
                        info_dict['status'] = 'n'
                        info_dict['timestamp'] = self.timestamp
                    except Exception as e:
                        print u'{} 解析城区失败 e: {}'.format(str(info_dict), e)
                        continue
                    else:
                        params = self.database.format_insert_params(['name', 'url', 'status', 'city', 'timestamp'], info_dict)
                        self.database.execute('insert into chengqu values(?, ?, ?, ?, ?)', params)
            except Exception as e:
                print e
                return -1
        return 0

    def fetchall(self):
        return self.database.fetch_data('select * from chengqu')

    def update_chengqu_crawled(self, url):
        return self.database.execute('update chengqu set status=?, timestamp=? where url=?', ('y', self.timestamp, url))

class XiaoquCrawler(Crawler):
    def __init__(self, database):
        Crawler.__init__(self)
        self.database = database
        self.failedpage_list = []
        self.did_start_thread_pool = False

    def crawl(self, url):
        code = Crawler.crawl(self, url)
        if code == -2 or code == -1:
            self.failedpage_list.append(url);
        return code
    
    def extract_func(self, soup, res):
        try:
            if not self.did_start_thread_pool:
                self.did_start_thread_pool = True
                div = soup.find('div', {'class':'page-box house-lst-page-box'})
                page_dic = 'page_dic=' + div['page-data']
                exec(page_dic)
                total_pages = page_dic['totalPage']
                url_need_handle = urlparse.urlparse(res.request.url)[0] + '://' + urlparse.urlparse(res.request.url)[1]
                url_need_handle = url_need_handle + div['page-url']
                page_urls = []
                for i in range(1, total_pages+1):
                    page_urls.append(url_need_handle.replace('{page}', str(i)))
                if len(page_urls) > 0:
                    self.start_thread_pool(self.crawl, page_urls)
            else:
                self.extract_xiaoqu(soup)
        except Exception as e:
            print '解析小区页数失败 e：{}'.format(e)
        finally:
            return 0


    def extract_xiaoqu(self, soup):
        xiaoqu_list = soup.find_all('li', {'class' : 'clear'})
        for xiaoqu in xiaoqu_list:
            info_dict = {}
            try:
                info_dict['name'] = xiaoqu.find('div', {'class' : 'title'}).find('a').text
                info_dict['url'] = xiaoqu.find('div', {'class' : 'title'}).find('a')['href']
                try:
                    info_dict['img'] = xiaoqu.find('img', {'class' : 'lj-lazy'})['src']
                    info_dict['district'] = xiaoqu.find('div', {'class' : 'positionInfo'}).find('a', {'class' : 'district'}).text
                    info_dict['bizcircle'] = xiaoqu.find('div', {'class' : 'positionInfo'}).find('a', {'class' : 'bizcircle'}).text

                    re_string = xiaoqu.find('div', {'class' : 'positionInfo'}).renderContents().strip().decode('utf-8')
                    re_match = re.split('</a>', re_string)
                    if len(re_match) > 1:
                        type_time = re_match[-1].strip().lstrip('/').split('/')
                        if len(type_time) >= 2:
                            xiaoqu_type = '/'.join(type_time[0:-1])
                            xiaoqu_time = type_time[-1].strip()
                            xiaoqu_time = re.search('\d*', xiaoqu_time).group()
                    
                            info_dict['type'] = xiaoqu_type
                            info_dict['time'] = xiaoqu_time
                    
                    house_info = xiaoqu.find('div', {'class' : 'houseInfo'})
                    for a_tag in house_info.find_all('a', href=True):
                        href = a_tag['href']
                        if re.match('.*/chengjiao/.*', href):
                            info_dict['cj_url'] = href
                        elif re.match('.*/zufang/.*', href):
                            info_dict['zf_url'] = href
                except:
                    print u'{} 某项信息提取失败, e:{}'.format(info_dict['name'])
                
                info_dict['cj_status'] = 'n'
                info_dict['zf_status'] = 'n'
                info_dict['timestamp'] = self.timestamp

                params = self.database.format_insert_params(['url', 'img', 'name', 'district', 'bizcircle', 'type', 'time', 'cj_url', 'zf_url', 'cj_status', 'zf_status', 'timestamp'], info_dict)
                self.database.execute('insert into xiaoqu values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', params)
            except Exception as e:
                print(u'提取某个小区失败; e: {}\n {}'.format(e, str(xiaoqu).decode('utf-8')))
                continue

    def fetchall(self):
        '''
        (url, cj_url, cj_status, zf_url, zf_status, name)
        '''
        return self.database.fetch_data('select url, cj_url, cj_status, zf_url, zf_status, name from xiaoqu')

    def fetchall_uncrawled_cj(self):
        '''
        (url, cj_url, cj_status)
        '''
        return self.database.fetch_data('select url, cj_url, cj_status from xiaoqu where cj_status="n"')

    def update_chengjiao_crawled(self, url):
        return self.database.execute('update xiaoqu set cj_status=?, timestamp=? where url=?', ('y', self.timestamp, url))

    def fetchall_uncrawled_zf(self):
        '''
        (url, zf_url, zf_status)
        '''
        return self.database.fetch_data('select url, zf_url, zf_status from xiaoqu where zf_status="n" and zf_url != ""')

    def update_zufang_crawled(self, url):
        return self.database.execute('update xiaoqu set zf_status=?, timestamp=? where url=?', ('y', self.timestamp, url))
    
    @property
    def failed_list(self):
        return self.failedpage_list


class ChengjiaoCrawler(Crawler):
    def __init__(self, database):
        Crawler.__init__(self)
        self.database = database
        self.failedpage_list = []
        self.did_start_thread_pool = []

    def crawl(self, url):
        code = Crawler.crawl(self, url)
        if code == -2 or code == -1:
            self.failedpage_list.append(url);
        return code
    
    def extract_func(self, soup, res):
        try:
            div = soup.find('div', {'class':'page-box house-lst-page-box'})
            if div == None:
                # 小区成交量为 0
                return 0

            if not self.did_start_thread_pool:
                self.did_start_thread_pool = True
                page_dic = 'page_dic=' + div['page-data']
                exec(page_dic)
                total_pages = page_dic['totalPage']
                url_need_handle = urlparse.urlparse(res.request.url)[0] + '://' + urlparse.urlparse(res.request.url)[1]
                url_need_handle = url_need_handle + div['page-url']
                page_urls = []
                for i in range(1, total_pages+1):
                    page_urls.append(url_need_handle.replace('{page}', str(i)))
                
                if len(page_urls) > 0:
                    self.start_thread_pool(self.crawl, page_urls)
            else:
                self.extract_chengjiao(soup)
        except Exception as e:
            print '解析成交页数失败 e：{}'.format(e)
        finally:
            return 0


    def extract_chengjiao(self, soup):
        li_tags = soup.find('ul', {'class' : 'listContent'}).find_all('li')
        for li_tag in li_tags:
            info_dict = {}
            tag = li_tag.find('div', {'class' : 'title'}).find('a', href=True)
            if tag == None:
                # 无成交详情数据, 忽略
                continue

            info_dict['url'] = tag['href']
            info_dict['timestamp'] = self.timestamp
            try:
                title_array = tag.text.strip().split(' ')
                info_dict['xq_name'], info_dict['house_type'], info_dict['size'] = title_array

                tag = li_tag.find('img', {'class' : 'lj-lazy'})
                if tag:
                    info_dict['img'] = tag['src']

                tag = li_tag.find('div', {'class' : 'houseInfo'})
                if tag:
                    house_info_content = tag.renderContents().strip().decode('utf-8')
                    house_info_text = re.match('.+</span>(.*)', house_info_content).group(1)
                    house_info_text = house_info_text.replace(' ', '')
                    house_infos = house_info_text.split('|')
                    info_dict['face'], info_dict['decorate'], info_dict['lift'] = house_infos

                tag = li_tag.find('div', {'class' : 'positionInfo'})
                if tag:
                    house_info_content = tag.renderContents().strip().decode('utf-8')
                    house_info_text = re.match('.+</span>(.*)', house_info_content).group(1)
                    info_dict['time'] = house_info_text

                tag = li_tag.find('span', {'class' : 'dealHouseTxt'})
                if tag:
                    span_tags = tag.find_all('span')
                    if len(span_tags) > 0:
                        info_dict['subway'] = span_tags[-1].text.strip()
                
                tag = li_tag.find('div', {'class' : 'dealDate'})
                if tag:
                    info_dict['deal_time'] = tag.text.strip()

                tag = li_tag.find('div', {'class' : 'totalPrice'}).find('span')
                if tag:
                    info_dict['price'] = tag.text.strip()
                tag = li_tag.find('div', {'class' : 'unitPrice'})
                if tag:
                    info_dict['price_unit'] = tag.find('span').text.strip()
            except Exception, e:
                print '{} 成交纪录信息提取异常 e: {}'.format(info_dict['url'], e)
            
            params = self.database.format_insert_params(['url', 'xq_name', 'img', 'house_type',
                                                        'size', 'face', 'decorate', 'lift',
                                                        'time', 'subway', 'deal_time', 'price',
                                                         'price_unit', 'timestamp'], info_dict)
            self.database.execute('insert into chengjiao values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', params)


class ZufangCrawler(Crawler):
    def __init__(self, database):
        Crawler.__init__(self)
        self.database = database
        self.failedpage_list = []
        self.did_start_thread_pool = []

    def crawl(self, url):
        code = Crawler.crawl(self, url)
        if code == -2 or code == -1:
            self.failedpage_list.append(url);
        return code
    
    def extract_func(self, soup, res):
        try:
            div = soup.find('div', {'class':'page-box house-lst-page-box'})
            if div == None:
                # 小区成交量为 0
                return 0

            if not self.did_start_thread_pool:
                self.did_start_thread_pool = True
                page_dic = 'page_dic=' + div['page-data']
                exec(page_dic)
                total_pages = page_dic['totalPage']
                url_need_handle = urlparse.urlparse(res.request.url)[0] + '://' + urlparse.urlparse(res.request.url)[1]
                url_need_handle = url_need_handle + div['page-url']
                page_urls = []
                for i in range(1, total_pages+1):
                    page_urls.append(url_need_handle.replace('{page}', str(i)))
                
                if len(page_urls) > 0:
                    self.start_thread_pool(self.crawl, page_urls)
            else:
                self.extract_zufang(soup)
        except Exception as e:
            print '解析租房页数失败 e：{}'.format(e)
        finally:
            return 0


    def extract_zufang(self, soup):
        li_tags = soup.find('ul', {'class' : 'house-lst'}).find_all('li')
        for li_tag in li_tags:
            info_dict = {}
            tag = li_tag.find('div', {'class' : 'pic-panel'}).find('a', href=True)
            if tag == None:
                # 无租房详情数据, 忽略
                continue

            info_dict['url'] = tag['href']
            info_dict['img'] = tag.find('img')['src']
            info_dict['timestamp'] = self.timestamp
            info_dict['ziru'] = 'y' if li_tag.find('div', {'class': 'ziroomTag zufang_ziroom'}) else 'n'
            try:
                tag = li_tag.find('div', {'class' : 'info-panel'}).find('h2').find('a')
                info_dict['name'] = tag.text
                
                where_tag = li_tag.find('div', {'class' : 'col-1'}).find('div', {'class' : 'where'})
                tag = where_tag.find('span', {'class' : 'region'})
                info_dict['xq_name'] = tag.text.strip()

                tag = where_tag.find('span', {'class' : 'zone'}).find('span')
                info_dict['house_type'] = tag.text.strip()

                tag = where_tag.find('span', {'class' : 'meters'})
                info_dict['size'] = re.search('\d+', tag.text).group()
                info_dict['face'] = tag.next_sibling.text.strip()

                where_tag = li_tag.find('div', {'class' : 'col-1'}).find('div', {'class' : 'con'})
                tag = where_tag.find('a')
                info_dict['group'] = tag.text.strip()
                info_dict['group_url'] = tag['href']

                tag = tag.next_sibling
                info_dict['floor'] = tag.next_sibling
                tag = tag.next_sibling.next_sibling
                info_dict['time'] = re.search('\d*', tag.next_sibling).group()

                try:
                    where_tag = li_tag.find('div', {'class' : 'col-1'}).find('div', {'class' : 'view-label left'})
                    tag = where_tag.find('span', {'class' : 'decoration-ex'})
                    if tag:
                        info_dict['decorate'] = tag.find('span').text

                    tag = where_tag.find('span', {'class' : 'heating-ex'})
                    if tag:
                        info_dict['heat'] = tag.find('span').text 

                    tag = where_tag.find('span', {'class' : 'fang-subway-ex'})
                    if tag:
                        info_dict['subway'] = tag.find('span').text 
                except Exception as e:
                    pass

                where_tag = li_tag.find('div', {'class' : 'col-3'})
                tag = where_tag.find('span', {'class' : 'num'})
                info_dict['price'] = tag.text

                tag = where_tag.find('div', {'class' : 'price-pre'})
                info_dict['update_time'] = tag.text.strip().split(' ')[0]

            except Exception, e:
                print '{} 租房纪录信息提取异常 e: {}'.format(info_dict['url'], e)
            
            params = self.database.format_insert_params(['url', 'xq_name', 'name', 'img', 'ziru',
                                                        'house_type', 'size', 'face', 'group_name',
                                                        'group_url', 'floor', 'time', 
                                                        'decorate', 'heat', 'subway', 'update_time', 
                                                        'price', 'timestamp'], info_dict)
            self.database.execute('insert into zufang values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', params)
    
    

def init_database(db_path='bj.db'):
    db = SQLiteHelper(db_path)
    command = 'create table if not exists chengqu(name text primary key unique, \
                                                  url text, \
                                                  status text,\
                                                  city text,\
                                                  timestamp text)'
    db.execute(command)
    command = ''

    command = 'create table if not exists xiaoqu(url text primary key unique, \
                                                  img text,\
                                                  name text,\
                                                  district text,\
                                                  bizcircle text, \
                                                  type text,\
                                                  time TEXT,\
                                                  cj_url TEXT,\
                                                  zf_url TEXT,\
                                                  cj_status text,\
                                                  zf_status text,\
                                                  timestamp text)'
    db.execute(command)                                                  
    command = 'create table if not exists chengjiao(url TEXT primary key UNIQUE,\
                                                    xq_name TEXT,\
                                                    img text,\
                                                    house_type TEXT, \
                                                    size TEXT, \
                                                    face TEXT, \
                                                    decorate TEXT, \
                                                    lift TEXT, \
                                                    time TEXT, \
                                                    subway TEXT, \
                                                    deal_time TEXT, \
                                                    price TEXT, \
                                                    price_unit TEXT,\
                                                    timestamp text)' 
    db.execute(command)

    command = 'create table if not exists zufang(url TEXT primary key UNIQUE,\
                                                    xq_name TEXT,\
                                                    name TEXT,\
                                                    img TEXT,\
                                                    ziru text,\
                                                    house_type TEXT, \
                                                    size TEXT, \
                                                    face TEXT, \
                                                    group_name TEXT, \
                                                    group_url TEXT,\
                                                    floor TEXT, \
                                                    time TEXT, \
                                                    decorate TEXT,\
                                                    heat TEXT,\
                                                    subway TEXT, \
                                                    update_time TEXT, \
                                                    price TEXT, \
                                                    timestamp text)' 
    db.execute(command)  
    return db

def main():
    auto_proxy = Proxy()
    proxy_pool = auto_proxy.get_proxy()

    db = init_database()
    chengqu = ChengquCrawler(db)
    if chengqu.crawl() != 0:
        print u'爬取城区失败'

    result = chengqu.fetchall()
    for cq in result: 
        if cq[2] == 'n': # 未被爬的城区下的各个小区
            xq = XiaoquCrawler(db)
            xq.crawl(cq[1])
            if len(xq.failed_list) == 0: # 爬取成功, 更新城区的状态为 y
                chengqu.update_chengqu_crawled(cq[1])
                print u'{} 城区爬取成功'.format(cq[0])
            else:
                print(u'以下链接未爬取成功{}'.format(str(xq.failed_list)))

    xiaoqu = XiaoquCrawler(db)
    result = xiaoqu.fetchall_uncrawled_cj() # 未被爬的城区下的各个小区
    count = 0
    for xq in result: # xq = (url, cj_url, cj_status)
        proxy_pool = auto_proxy.get_proxy()
        cj = ChengjiaoCrawler(db)
        if count != 0 and count % 2 == 0:
            cj.proxies_list = proxy_pool
        else:
            cj.proxies_list = []

        if count != 0 and count % 100 == 0:
            print(u'暂停 1 分钟')
            time.sleep(1*60)
        code = cj.crawl(xq[1])
        if code == -2:
            print(u'ip 被封，暂停 30 分钟')
            time.sleep(30 * 60)
        if len(cj.failedpage_list) == 0: # 爬取成功, 更新城区的状态为 y
            xiaoqu.update_chengjiao_crawled(xq[0])
            count += 1
            print u'已爬取 {}/{}\n'.format(str(count), str(len(result))),
        else:
            print(u'以下链接未爬取成功{}\n重新爬取。。。'.format(str(cj.failedpage_list)))
            cj.failedpage_list = []
            cj.proxies_list = [] # 基本是因为代理导致的链接失败
            cj.start_thread_pool(cj.crawl, cj.failedpage_list)
            if len(cj.failedpage_list) == 0:
                print(u'重新爬取成功！')
                xiaoqu.update_chengjiao_crawled(xq[0])
                count += 1
                print u'已爬取 {}/{}\n'.format(str(count), str(len(result))),
        del cj

    result = xiaoqu.fetchall_uncrawled_zf()
    count = 0
    for xq in result:
        proxy_pool = auto_proxy.get_proxy()
        zf = ZufangCrawler(db)
        if count != 0 and count % 2 == 0:
            zf.proxies_list = proxy_pool
        else:
            zf.proxies_list = []
        if count != 0 and count % 100 == 0:
            print(u'暂停 1 分钟')
            time.sleep(1*60)
        code = zf.crawl(xq[1])
        if code == -2:
            print(u'ip 被封，暂停 30 分钟')
            time.sleep(30 * 60)
        if len(zf.failedpage_list) == 0: # 爬取成功, 更新小区的状态为 y
            xiaoqu.update_zufang_crawled(xq[0])
            count += 1
            print u'已爬取 {}/{}\n'.format(str(count), str(len(result))),
        else:
            print(u'以下链接未爬取成功{}\n重新爬取。。。'.format(str(zf.failedpage_list)))
            zf.failedpage_list = []
            zf.proxies_list = [] # 基本是因为代理导致的链接失败
            zf.start_thread_pool(zf.crawl, zf.failedpage_list)
            if len(zf.failedpage_list) == 0:
                print(u'重新爬取成功！')
                xiaoqu.update_zufang_crawled(xq[0])
                count += 1
                print u'已爬取 {}/{}\n'.format(str(count), str(len(result))),
        del zf



if __name__ == '__main__':
    import sys
    sys.exit(int(main() or 0))
    

