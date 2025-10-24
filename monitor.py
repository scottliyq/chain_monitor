
import string
import time
import os
import requests
from datetime import datetime
import sqlalchemy
import json
import configparser
import pandas as pd
from base import send_notice, sql_engine


import logging 
from logging import handlers

from apscheduler.schedulers.background import BackgroundScheduler

engine = sql_engine()

def check_event():
    logging.debug("start to invoke zapper api")
    sql = f"select * from m_event_notify_logs order by create_time desc"
    data = pd.read_sql(sql, engine)

    print(data)   

logger = logging.getLogger()
logger.setLevel(logging.INFO) 

from pathlib import Path
save_path = f"./temp"
Path(save_path).mkdir(parents=True, exist_ok=True)
logFile = './temp/chain_monitor.log'


# 创建一个FileHandler,并将日志写入指定的日志文件中
fileHandler = logging.FileHandler(logFile, mode='a')
fileHandler.setLevel(logging.INFO) 
 
 # 或者创建一个StreamHandler,将日志输出到控制台
streamHandler = logging.StreamHandler()
streamHandler.setLevel(logging.INFO)

# 定义Handler的日志输出格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler.setFormatter(formatter)
 
# 定义日志滚动条件，这里按日期-天保留日志
timedRotatingFileHandler = handlers.TimedRotatingFileHandler(filename=logFile, when='D')
timedRotatingFileHandler.setLevel(logging.INFO)
timedRotatingFileHandler.setFormatter(formatter)

# 添加Handler
# logger.addHandler(fileHandler)
logger.addHandler(streamHandler)
logger.addHandler(timedRotatingFileHandler)

def Log(*params):

    logging.info(params)

###################################
# main function

###################################
def main():
    #启动运行第一次
    check_event()
    send_notice('chain_notify', {'address':'start to monitor'})

    scheduler = BackgroundScheduler()
    # scheduler.add_job(check_zapper, 'interval', minutes=30)
    scheduler.add_job(check_event, 'cron', hour='*')
    scheduler.start()
    Log('Press Ctrl+{0} to exit'.format('Break' if os.name == 'nt' else 'C'))

    try:
        # This is here to simulate application activity (which keeps the main thread alive).
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        scheduler.shutdown()

# python cex_monitor.py -f binance_guptalee -p margin_monitor
if __name__ == '__main__':
    main()