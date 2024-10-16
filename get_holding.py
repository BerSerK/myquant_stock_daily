# coding=utf-8
# from __future__ import log_function, absolute_import
from gm.api import *
import datetime as dt
import os
import pandas as pd
import time
from config import *
FREQ_LIMIT = 20 #每秒报单限制
DEFAULT_CASH = 250000 # 目标仓位文件中的默认现金

SKIP_STOCKS = ["SHSE.511620", # 货币基金ETF
               "SHSE.511880", # 银华日利ETF
               "SHSE.511990", # 华宝添益
               "SHSE.600900", # 长江电力
               "SHSE.560510", # 泰康中证A500ETF
               ]

EMPTY_STOCKS = ["SHSE.600321"]

# 定义一个log函数，用于打印日志，输入参数与print函数一致
def log(*args):
    filename = "log/" + dt.datetime.now().strftime("%Y-%m-%d") + ".log"
    with open(filename, 'a', encoding='utf-8') as f:
        msg = " ".join([str(i) for i in args])
        line = "[%s] %s\n" % (dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg)
        f.write(line)
        print(line.strip())
        f.close()    

def init(context):
    # 每天14:50 定时执行algo任务,
    # algo执行定时任务函数，只能传context参数
    # date_rule执行频率，目前暂时支持1d、1w、1m，其中1w、1m仅用于回测，实时模式1d以上的频率，需要在algo判断日期
    # time_rule执行时间， 注意多个定时任务设置同一个时间点，前面的定时任务会被后面的覆盖

    log("==========init==========")
    cash = context.account().cash
    # print dict in a beautiful way.
    for k, v in cash.items():
        k_str = str(k)
        padding = " " * (30 - len(k_str))
        log("[AccountInfo] %s %s: %s" % (padding, k_str, v))

    # 获取当前持仓
    positions = get_position()
    holdings = {}
    for position in positions:
        symbol = position['symbol']
        holding = position['volume']
        print("Holding: %s %s" % (symbol, holding))
        
def on_order_status(context, order):
    if order['status'] == 3:
        log("Order completed:", order)
    else:
        log("Order status updated:", order)

# 查看最终的回测结果
def on_backtest_finished(context, indicator):
    log(indicator)


if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
        backtest_match_mode市价撮合模式，以下一tick/bar开盘价撮合:0，以当前tick/bar收盘价撮合：1
    '''
    run(strategy_id='57166f01-0741-11ef-9f26-a4bb6dd1a9cc',
        filename='get_holding.py',
        # mode=MODE_BACKTEST,
        mode=MODE_LIVE,
        token='03fefdbeb25d9507525802de467f18e1058d364b',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=1000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
