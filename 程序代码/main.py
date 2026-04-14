from urllib import request
from urllib.parse import urljoin
# 导入urllib.request模块
from bs4 import BeautifulSoup
# 单页访问链接myurl
import sqlite3
# 导入数据库
import schedule
from tkinter import *
# 导入tkinter模块制作前端界面
import os  # 删除文件
# 邮件发送包
from email.mime.text import MIMEText
import smtplib
from email.header import Header
import time


# 此处封装邮件发送模块
def send_email(tit_title, tit_time, tit_url, to_addr):
    from_addr = 'adn714714@163.com'
    password = 'CJMGJIJTCHIDIMHS'
    # 收信方邮箱
    # to_addr = '312931440@qq.com'
    try:
        # 设置要登录的邮箱
        smtp_obj = smtplib.SMTP('smtp.163.com')
        # 登录邮箱  这里需要填写你的qq邮箱地址和生成的授权码
        smtp_obj.login(from_addr, password)
        # 编辑内容
        # 邮箱正文内容，第一个参数为内容，第二个参数为格式(plain 为纯文本)，第三个参数为编码
        mail_text = f"您好，您的学校有一则新的通知：\n标题:{tit_title}\n发布时间:{tit_time}\n链接:{tit_url}\n祝好\n"
        # plain 原生文本模式
        msg_body = MIMEText(mail_text, 'plain', 'utf-8')
        # 设置从哪发送的
        msg_body['From'] = Header('大美女', 'utf-8')  # 设置发送人
        msg_body['Subject'] = Header('你有一则新通知', 'utf-8')  # 设置内容主题
        # 发送邮件  这里第一个邮箱填自己的，第二个填收件人的邮箱地址
        smtp_obj.sendmail(from_addr, to_addr, msg_body.as_string())
        print('邮件发送成功')
    except Exception as e:
        print('邮件发送失败，请查看下方原因')
        print(e)


def creat_db():
    # 链接数据库
    conn = sqlite3.connect('xiaoyuanwang.db')
    # 创建游标
    cur = conn.cursor()
    # 建表,表名：pachong；id为递增主键
    sql_table = """CREATE TABLE IF NOT EXISTS pachong 
        (id INTEGER PRIMARY KEY AUTOINCREMENT , 
        title varchar(50),
        my_day varchar(50),
        link varchar(50),
        unique(title,my_day,link));"""  # 定义3个字段的唯一性，为去重做准备
    cur.execute(sql_table)
    return cur, conn


# 关闭数据库，每一次都要衡量是否新增通知，那么不能删除数据库。
def close_db(cur, conn):
    # 关闭游标
    cur.close()
    # 关闭连接
    conn.close()
    # 删除数据库
    # os.remove('xiaoyuanwang.db')


# 建email table
def add_table_email():
    # 链接数据库
    conn = sqlite3.connect('xiaoyuanwang.db')
    # 创建游标
    cur = conn.cursor()
    # 建表,表名：youxiang；id为递增主键
    sql_table = """CREATE TABLE IF NOT EXISTS youxiang 
        (id INTEGER PRIMARY KEY AUTOINCREMENT , 
        email varchar(50),
        unique(email));"""  # 定义3个字段的唯一性，为去重做
    cur.execute(sql_table)
    return cur, conn


# 新增邮箱函数
def add_email(email_str):
    # email_str=input("请输入新增邮箱,多个输入请以英文','作为分隔符：")
    email_lis = email_str.split(',')
    # 创建emial table
    email_cur, email_conn = add_table_email()
    # 插入邮箱
    for item in email_lis:
        # 插入数据,insert or ignore 不存在insert，存在则ignore
        sql = "insert or ignore into youxiang (email) values(?)"
        para = tuple([item])
        # 插入
        email_cur.execute(sql, para)
        # 提交
        email_conn.commit()

    # 查询邮箱
    sql_find = """select * from youxiang"""
    email_cur.execute(sql_find)
    data = email_cur.fetchall()
    # 关闭邮箱
    close_db(cur=email_cur, conn=email_conn)
    return data


def get_content(myurl, cur, conn, email_lis):
    responese = request.urlopen(myurl)
    # 提取响应内容
    html = responese.read().decode('utf-8')
    # print(html) # 打印响应内容
    request.encoding = "utf-8"
    soup = BeautifulSoup(html, 'html.parser')
    news = soup.find("div", attrs={"class": "list-search"})
    li_lis = news.find_all('li')
    for li in li_lis:
        url1 = "http://www.gdut.edu.cn/"
        url2 = li.find('a').get('href').strip()
        url = urljoin(url1, url2)
        tit = li.find('a').find('p').text.strip()
        date = li.find('a').find('i').text.strip()

        # 插入数据,insert or ignore 不存在insert，存在则ignore
        sql = "insert or ignore into pachong (title,my_day,link) values(?,?,?)"
        para = tuple([tit, date, url])
        # 插入
        cur.execute(sql, para)
        # 提交
        conn.commit()
        # 插入成功响应
        inst_curr = cur.lastrowid
        # 单键查询
        sql_find = f"""select * from pachong where id={inst_curr}"""
        cur.execute(sql_find)
        data = cur.fetchall()
        # 判断查询内容
        if len(data) == 0:  # 没有内容
            print('没有新通知')
        else:
            data_item = data[0]  # 递增键查找，全部有的话，返回列表，元素为tuple
            print("***有新通知，准备发送邮件***")
            for email_item in email_lis:
                print(email_item)
                send_email(tit_title=data_item[1], tit_time=data_item[2], tit_url=data_item[3], to_addr=email_item[1])
                time.sleep(1)


# 实际的链接
# 一共6页，第一页，没有页码260
# 第2页页码为5，最后一页，页码为1
def main(email_lis):
    print('开始运行一次')
    # 建库、表
    cur, conn = creat_db()
    for i in range(1, 7):
        if i == 1:
            myurl = "https://www.gdut.edu.cn/index/tzgg.htm"
            get_content(myurl=myurl, cur=cur, conn=conn, email_lis=email_lis)
        else:
            p = 7 - i
            myurl = f"https://www.gdut.edu.cn/index/tzgg/{p}.htm"
            get_content(myurl=myurl, cur=cur, conn=conn, email_lis=email_lis)

    close_db(cur=cur, conn=conn)
    print('一次运行结束')


# 增加邮箱
def my_crawl(email_str):
    email_lis = add_email(email_str=email_str)
    main(email_lis=email_lis)
    schedule.every(1).minute.do(main, email_lis=email_lis)
    while True:
        schedule.run_pending()


# 获取文本框内容,文本框全部内容
def get_email():
    email_str = textExample.get("1.0", "end")
    return email_str


def my_run():
    # if btn1.cget('bg') == 'gray':   # Check current color
    btn1.config(bg='green', activebackground='green')
    # elif btn1.cget('bg') == 'green':   # Check current color
    #     KEY=False
    #     btn1.config(bg='gray', activebackground='gray')

    # 开始抓取
    email_str = get_email()
    my_crawl(email_str=email_str.strip())


def my_tkinter():
    root = Tk()
    # 标题
    root.title('校园新闻推送助手')
    # 窗口尺寸
    root.geometry('400x240')  # 这里的乘号不是 * ，而是小写英文字母 x
    # 文本说明label
    lb1 = Label(root, text='请输入您的邮箱，多个邮箱请用逗号隔开')
    lb1.place(relx=0.1, rely=0.1, relwidth=0.8, relheight=0.1)
    # 文本框
    global textExample
    textExample = Text(root, height=10)  # 创建文本输入框
    textExample.insert("0.0", "1819336672@qq.com")
    textExample.place(relx=0.2, rely=0.2, relwidth=0.6, relheight=0.4)
    # 按钮
    global btn1
    btn1 = Button(root, text='订阅推送', command=my_run, bg='gray', activebackground='gray')
    btn1.place(relx=0.4, rely=0.6, relwidth=0.2, relheight=0.1)
    root.mainloop()  # 主窗口进入消息事件循环【必要步骤】


if __name__ == '__main__':
    my_tkinter()





