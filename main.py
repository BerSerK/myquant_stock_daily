# coding=utf-8
# from __future__ import log_function, absolute_import
from gm.api import *
import datetime as dt
import os
import pandas as pd
import time

FREQ_LIMIT = 20 #每秒报单限制

SKIP_STOCKS = ["SHSE.511620",
               "SHSE.511880",
               "SHSE.511990",
               "SHSE.600900"]

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
    now = dt.datetime.now()
    if now < dt.datetime(now.year, now.month, now.day, 9, 30, 5):
        schedule(schedule_func=algo, date_rule='1d', time_rule='09:30:05')
    else:
        # 设置time_rule为10秒以后.
        time_rule = now + dt.timedelta(seconds=10)
        time_rule = time_rule.strftime('%H:%M:%S')
        schedule(schedule_func=algo, date_rule='1d', time_rule=time_rule)
    log("==========init==========")
    cash = context.account().cash
    # print dict in a beautiful way.
    for k, v in cash.items():
        k_str = str(k)
        padding = " " * (30 - len(k_str))
        log("[AccountInfo] %s %s: %s" % (padding, k_str, v))
        
data_dir = "Z:\\alpha\\"

def std_ticker(raw_ticker):
    ex = raw_ticker[:2]
    code = raw_ticker[2:8]
    if ex == "SZ":
        ex = "SZSE"
    elif ex == "SH":
        ex = "SHSE"
    return ex + "." + code

def read_today_target():
    files = os.listdir(data_dir)
    if len(files) == 0:
        log("No target file found!")
        return None
    files.sort()
    filename = data_dir + files[-1]
    log("alpha file:", filename)
    # 仓位文件文件头: ticker  alpha    price
    today_target = pd.read_csv(filename)
    today_target['ticker'] = today_target['ticker'].apply(std_ticker)
    log("alpha:\n", today_target)
    return today_target

def algo(context):
    # 取消所有订单
    order_cancel_all()

    today_target = read_today_target()
    alpha = dict(zip(today_target['ticker'], today_target['alpha']))
    log("目标仓位:\n", today_target.head() )

    # 获取当前持仓
    positions = get_position()
    holdings = {}
    for position in positions:
        symbol = position['symbol']
        holdings[symbol] = position['volume']
    log("当前持仓")
    for k, v in holdings.items():
        log("持仓:", k, v)

    stock_list = today_target['ticker'].tolist() + [i for i in holdings.keys() if i not in today_target['ticker']]
    # 去重
    stock_list = list(set(stock_list))

    # 获取当前时间
    now = context.now
    now_str = now.strftime('%H:%M:%S')
    start_time_str = now_str
    end_time_referred = now + dt.timedelta(minutes=5)
    end_time_referred_str = end_time_referred.strftime('%H:%M:%S')
    end_time_str = end_time_referred_str

    # 获取停牌股和ST股列表
    date2 = context.now.strftime("%Y-%m-%d %H:%M:%S")
    df_code = get_history_instruments(symbols=stock_list, start_date=date2, end_date=date2, df=True)
    df_stop = df_code[(df_code['is_suspended'] == 1)]
    df_st = df_code[df_code['sec_level'] != 1]
    stop_list = df_stop['symbol'].tolist()
    st_list = df_st['symbol'].tolist()

    log("当前时间:", now_str, end_time_referred_str)
    order_list = []
    for stock in stock_list:
        symbol = stock
        if symbol in stop_list:
            log("停牌股，跳过:", symbol, "holding:", holdings.get(symbol, 0))
            continue
        
        if symbol in SKIP_STOCKS:
            log("现金管理, 跳过:", symbol, "holding:", holdings.get(symbol, 0))
            continue

        # new_price = history_n(symbol=symbol, frequency='1d', count=1, end_time=now_str, fields='close', adjust=ADJUST_PREV, adjust_end_time=context.backtest_end_time, df=False)[0]['close']
        # # 当前价（tick数据，免费版本有时间权限限制；实时模式，返回当前最新 tick 数据，回测模式，返回回测当前时间点的最近一分钟的收盘价）
        new_price = current(symbols=symbol)[0]['price']
        yesterday_close = history_n(symbol=symbol, frequency='1d', count=1, end_time=now_str, fields='close', adjust=ADJUST_NONE, adjust_end_time="", df=False)[0]['close']

        if stock in alpha:
            stock_code = stock.split('.')[1]
            if stock_code.startswith('688'):
                lot_size = 200
            else:
                lot_size = 100
            
            vol = round(alpha[stock] / yesterday_close / lot_size ) * lot_size
        else:
            vol = 0

        if symbol in EMPTY_STOCKS:
            log("空仓股，不持仓:", symbol, "holding:", holdings.get(symbol, 0), 'yesterday close price:', yesterday_close, 'new price:', new_price)
            vol = 0

        if symbol in st_list:
            log("ST股，不持仓:", symbol, "holding:", holdings.get(symbol, 0), 'yesterday close price:', yesterday_close, 'new price:', new_price)
            vol = 0

        if stock in holdings:
            holding = holdings[stock]
        else:
            holding = 0
        
        diff = vol - holding

        if abs(diff) < 100:
            diff = 0

        if diff != 0:
            abs_diff = abs(diff)
            symbol = stock
            # 基准价， 算法母单需要是限价单
            price = new_price
            order_info = {"symbol": symbol,
                          "from": holding,
                          "to": vol,
                          "diff": diff,
                          "volume": abs_diff,
                          "yesterday_close": yesterday_close,
                          "new_price": new_price,
                          "price": 0,
                          "side": OrderSide_Buy if diff > 0 else OrderSide_Sell,
                          "position_effect": PositionEffect_Open if diff > 0 else PositionEffect_Close,
                          "order_type": OrderType_Market}
            order_list.append(order_info)
        else:
            log("无需交易:", stock, "holding:", holding, "target:", vol, 'yesterday close price:', yesterday_close, 'new price:', new_price)
    
    # sort order_list by side, Sell first
    order_list.sort(key=lambda x: x['side'], reverse=True)

    tag = 'sell'
    for order in order_list:
        stock = order['symbol']
        symbol = stock
        holding = order['from']
        vol = order['to']
        diff = order['diff']
        abs_diff = order['volume']
        yesterday_close = order['yesterday_close']
        new_price = order['new_price']

        if tag == 'sell' and diff > 0:
            wait_time = 3
            log("刚执行完卖单, 等待{}秒".format(wait_time))
            time.sleep(wait_time)
            tag = 'buy'

        MARKET_ORDER_SAFE = 0.05
        if diff > 0: # buy
            order_price = min(max(yesterday_close, new_price) * (1.0 + MARKET_ORDER_SAFE), yesterday_close * 1.1)
            # round to 2 decimal.
            order_price = round(100 * order_price) / 100

            order = order_volume(symbol=symbol, volume=abs_diff, side=OrderSide_Buy,
                order_type=OrderType_Market, position_effect=PositionEffect_Open, price=order_price)
        else: # sell
            order_price = max(min(yesterday_close, new_price) * (1.0 - MARKET_ORDER_SAFE), yesterday_close * 0.9)
            # round to 2 decimal.
            order_price = round(100 * order_price) / 100

            order = order_volume(symbol=symbol, volume=abs_diff, side=OrderSide_Sell,
                order_type=OrderType_Market, position_effect=PositionEffect_Close, price=order_price)

        log("交易:", stock, "from", holding, "to", vol, 'diff:', diff, 'volume', abs_diff, 'yesterday close price:', yesterday_close, 'new price:', new_price, "order price:", order_price)
        
        if hasattr(context, 'order_id'): 
            context.order_id.append(order[0]['cl_ord_id'])
        else:
            context.order_id = [order[0]['cl_ord_id']]
        
        time.sleep(1.0/FREQ_LIMIT)
        
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
        filename='main.py',
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
