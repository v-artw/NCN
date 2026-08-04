#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pbaostock_auto.py - Baostock A股数据自动下载器（非交互版）
用于 cron 定时任务或后台运行，通过配置文件或命令行参数配置。
输出目录默认为 ./PFrontStockData，与 SuperTrader 交易终端无缝对接。
"""

import baostock as bs
import pandas as pd
import os
import shutil
import datetime
import logging
import argparse
import json
import sys
import yaml
import socket
import multiprocessing
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

# 防止 baostock HTTP 请求无限挂起
socket.setdefaulttimeout(15)

# ---------------------------- 日志配置 ----------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, "baostock_download.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------- 默认配置 ----------------------------
DEFAULT_CONFIG = {
    "data_dir": "./PFrontStockData",       # 数据输出目录（前复权）
    "start_date": "1990-12-19",            # 全局开始日期
    "end_date": "",                        # 空表示当天
    "adjust_flag": "2",                    # 1后复权 2前复权 3不复权
    "clean_before_download": False,        # 是否清空目录再下载
    "max_workers": 2,                      # 并发线程数（RPi 建议 2）
    "query_timeout": 30,                   # 单次查询超时秒数
    "stock_list_date": ""                  # 获取股票列表的基准日期（空则用end_date）
}

CONFIG_FILE = os.path.join(PROJECT_ROOT, "yaml", "baostock_config.yaml")

def load_config():
    """从 YAML 文件加载配置，若不存在则创建默认"""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            yaml_cfg = yaml.safe_load(f)
            if yaml_cfg:
                config.update(yaml_cfg)
    else:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        logger.info(f"✅ 已生成默认配置文件: {CONFIG_FILE}")
    return config

def parse_args():
    """命令行参数优先级高于配置文件"""
    parser = argparse.ArgumentParser(description="Baostock A股数据自动下载器（非交互版）")
    parser.add_argument('--config', type=str, help='配置文件路径（默认 baostock_config.yaml）')
    parser.add_argument('--data-dir', type=str, help='输出目录')
    parser.add_argument('--start-date', type=str, help='开始日期 YYYY-MM-DD')
    parser.add_argument('--end-date', type=str, help='结束日期 YYYY-MM-DD')
    parser.add_argument('--stock-list-date', type=str, help='股票列表基准日期 YYYY-MM-DD')
    parser.add_argument('--adjust', type=str, choices=['1','2','3'], help='复权类型 1后复权 2前复权 3不复权')
    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument('--clean', action='store_true', help='下载前清空输出目录')
    clean_group.add_argument('--no-clean', action='store_true', help='下载前不清空输出目录（覆盖配置）')
    parser.add_argument('--workers', type=int, help='并发进程数')
    parser.add_argument('--max-failure-rate', type=float, default=0.10, help='失败+超时占比上限，范围 0 到 1')
    parser.add_argument('--summary-json', type=str, help='写出机器可读下载摘要 JSON')
    return parser.parse_args()

def clean_directory(target_dir):
    """清空指定目录"""
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            logger.info(f"🗑️ 已清空文件夹: {target_dir}")
        except Exception as e:
            logger.error(f"清空文件夹失败: {e}")
    os.makedirs(target_dir, exist_ok=True)

def _bs_login_with_retry(max_retries=3):
    """baostock 登录（带重试），可能因网络问题超时"""
    for attempt in range(max_retries):
        try:
            lg = bs.login()
            if lg.error_code == '0':
                logger.info("✅ baostock 登录成功")
                return lg
            logger.warning(f"baostock 登录返回错误: {lg.error_msg}，重试 {attempt+1}/{max_retries}")
        except Exception as e:
            logger.warning(f"baostock 登录异常: {e}，重试 {attempt+1}/{max_retries}")
    raise RuntimeError("baostock 登录失败，已达最大重试次数")

def get_stock_list_main(date_str):
    """获取指定日期的股票列表（主线程执行）"""
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        logger.info(f"stock_list_date 为空，使用当前日期: {date_str}")

    _bs_login_with_retry()
    logger.info(f"正在获取股票名单 (基准日期: {date_str})...")
    curr_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    final_list = []
    locked_trade_date = ""
    for i in range(10):
        query_date = curr_date.strftime("%Y-%m-%d")
        try:
            rs = bs.query_all_stock(day=query_date)
        except Exception as e:
            logger.warning(f"query_all_stock({query_date}) 异常: {e}")
            curr_date -= datetime.timedelta(days=1)
            continue
        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())
        if data_list:
            df_stocks = pd.DataFrame(data_list, columns=rs.fields)
            logger.info(f"✅ 成功锁定交易日: {query_date}，共获取 {len(df_stocks)} 只证券代码。")
            final_list = df_stocks['code'].tolist()
            locked_trade_date = query_date
            break
        curr_date -= datetime.timedelta(days=1)
    bs.logout()
    return final_list, locked_trade_date

def worker_init():
    """每个子进程启动时登录 baostock（带重试，socket 已设 15s 超时）"""
    for attempt in range(3):
        try:
            lg = bs.login()
            if lg.error_code == '0':
                return
            if attempt < 2:
                logger.warning(f"子进程 baostock 登录失败: {lg.error_msg}，重试 {attempt+2}/3")
        except Exception as e:
            if attempt < 2:
                logger.warning(f"子进程 baostock 登录异常: {e}，重试 {attempt+2}/3")
    logger.error("子进程 baostock 登录失败，该进程的查询任务将全部失败")

def process_one_stock(code, global_start_date, end_date, adjust_flag, output_dir):
    """
    单只股票的处理（运行在子进程中）
    返回值: (code, success, updated)
    """
    final_path = os.path.join(output_dir, f"{code}.parquet")
    real_start_date = global_start_date
    is_append = False

    # 增量检查
    if os.path.exists(final_path):
        try:
            df_old = pd.read_parquet(final_path, columns=['date'])
            if not df_old.empty:
                last_date = df_old['date'].iloc[-1]
                if isinstance(last_date, pd.Timestamp):
                    last_date_str = last_date.strftime('%Y-%m-%d')
                else:
                    last_date_str = str(last_date)
                if last_date_str >= end_date:
                    return (code, True, False)   # 已是最新
                last_dt = datetime.datetime.strptime(last_date_str, "%Y-%m-%d")
                next_dt = last_dt + datetime.timedelta(days=1)
                real_start_date = next_dt.strftime("%Y-%m-%d")
                if real_start_date > end_date:
                    return (code, True, False)
                is_append = True
        except Exception as e:
            logger.warning(f"{code} 读取已有文件失败，将重新下载: {e}")

    # 下载数据
    try:
        rs = bs.query_history_k_data_plus(code,
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
                start_date=real_start_date, end_date=end_date,
                frequency="d", adjustflag=adjust_flag)
        if rs.error_code != '0':
            return (code, False, False)

        data_list = []
        while (rs.error_code == '0') and rs.next():
            data_list.append(rs.get_row_data())
        if not data_list:
            return (code, False, False)

        df = pd.DataFrame(data_list, columns=rs.fields)
        df['date'] = pd.to_datetime(df['date'])
        numeric_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount', 'turn', 'pctChg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if is_append:
            df_old = pd.read_parquet(final_path)
            df_final = pd.concat([df_old, df], ignore_index=True)
            df_final = df_final.drop_duplicates(subset=['date'], keep='last')
            df_final.to_parquet(final_path, engine='pyarrow', compression='snappy', index=False)
        else:
            df.to_parquet(final_path, engine='pyarrow', compression='snappy', index=False)
        return (code, True, True)
    except Exception as e:
        logger.error(f"{code} 下载失败: {e}")
        return (code, False, False)

def build_download_summary(*, requested_end_date, effective_end_date, stock_list_date, locked_trade_date,
                           total, updated_count, failed_count, timeout_count, data_dir, max_failure_rate,
                           clean_before_download=False):
    failure_count = failed_count + timeout_count
    failure_rate = failure_count / total if total else 1.0
    status = "success" if total > 0 and failure_rate <= max_failure_rate else "failed"
    return {
        "schema_version": 1,
        "status": status,
        "requested_end_date": requested_end_date,
        "effective_end_date": effective_end_date,
        "stock_list_date": stock_list_date,
        "locked_trade_date": locked_trade_date,
        "total": total,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "timeout_count": timeout_count,
        "failure_count": failure_count,
        "failure_rate": failure_rate,
        "max_failure_rate": max_failure_rate,
        "data_dir": data_dir,
        "incremental": not clean_before_download,
        "clean_before_download": clean_before_download,
    }


def write_summary_json(path, payload):
    if not path:
        return
    target = os.path.abspath(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = target + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")
    os.replace(temporary, target)


def main():
    # 加载配置
    config = load_config()
    args = parse_args()
    if not 0 <= args.max_failure_rate <= 1:
        logger.error("--max-failure-rate 必须在 0 到 1 之间")
        return 2

    # 若指定了其他配置文件，则重新加载
    if args.config:
        global CONFIG_FILE
        CONFIG_FILE = args.config
        config = load_config()

    # 命令行覆盖
    if args.data_dir:
        config['data_dir'] = args.data_dir
    if args.start_date:
        config['start_date'] = args.start_date
    if args.end_date:
        config['end_date'] = args.end_date
    else:
        config['end_date'] = datetime.datetime.now().strftime("%Y-%m-%d")
    if args.stock_list_date:
        config['stock_list_date'] = args.stock_list_date
    if args.adjust:
        config['adjust_flag'] = args.adjust
    if args.clean:
        config['clean_before_download'] = True
    elif args.no_clean:
        config['clean_before_download'] = False
    if args.workers:
        config['max_workers'] = args.workers

    output_dir = config['data_dir']
    start_date = config['start_date']
    end_date = config['end_date']
    requested_end_date = end_date
    adjust_flag = config['adjust_flag']
    clean_flag = config['clean_before_download']
    max_workers = min(config['max_workers'], (os.cpu_count() or 2) * 2)
    query_timeout = config.get('query_timeout', 30)
    stock_list_date = config.get('stock_list_date', '')

    if not stock_list_date:
        stock_list_date = end_date
        logger.info(f"stock_list_date 未设置，使用 end_date: {stock_list_date}")

    # 处理目录
    if clean_flag:
        clean_directory(output_dir)
    else:
        os.makedirs(output_dir, exist_ok=True)

    # 获取股票列表
    try:
        stock_codes, locked_trade_date = get_stock_list_main(stock_list_date)
    except Exception as exc:
        logger.error(f"❌ 获取股票列表失败: {exc}")
        summary = build_download_summary(
            requested_end_date=requested_end_date,
            effective_end_date=end_date,
            stock_list_date=stock_list_date,
            locked_trade_date="",
            total=0,
            updated_count=0,
            failed_count=0,
            timeout_count=0,
            data_dir=output_dir,
            max_failure_rate=args.max_failure_rate,
            clean_before_download=clean_flag,
        )
        summary["error"] = str(exc)
        write_summary_json(args.summary_json, summary)
        return 1
    if not stock_codes:
        logger.error("❌ 未获取到股票列表，程序退出。")
        summary = build_download_summary(
            requested_end_date=requested_end_date,
            effective_end_date=end_date,
            stock_list_date=stock_list_date,
            locked_trade_date=locked_trade_date,
            total=0,
            updated_count=0,
            failed_count=0,
            timeout_count=0,
            data_dir=output_dir,
            max_failure_rate=args.max_failure_rate,
            clean_before_download=clean_flag,
        )
        write_summary_json(args.summary_json, summary)
        return 1
    if locked_trade_date and locked_trade_date < end_date:
        logger.info(f"📅 下载截止日从 {end_date} 回退到实际交易日 {locked_trade_date}")
        end_date = locked_trade_date

    # 子进程各自通过 worker_init 登录，无需主进程共享登录态
    logger.info(f"🚀 启动多进程下载 (进程数: {max_workers})")
    logger.info(f"📂 数据目录: {output_dir}")
    logger.info(f"📅 日期范围: {start_date} -> {end_date}")
    logger.info(f"🔧 复权类型: {adjust_flag}")

    updated_count = 0
    failed_count = 0
    timeout_count = 0
    total = len(stock_codes)

    with ProcessPoolExecutor(max_workers=max_workers, initializer=worker_init) as executor:
        futures = {executor.submit(process_one_stock, code, start_date, end_date, adjust_flag, output_dir): code for code in stock_codes}
        with tqdm(total=total, unit="stock", desc="下载进度") as pbar:
            for future in as_completed(futures):
                code = futures[future]
                try:
                    _, success, updated = future.result(timeout=query_timeout)
                    if not success:
                        failed_count += 1
                    elif updated:
                        updated_count += 1
                except TimeoutError:
                    logger.warning(f"{code} 查询超时 ({query_timeout}s)")
                    timeout_count += 1
                except Exception as e:
                    logger.error(f"{code} 进程异常: {e}")
                    failed_count += 1
                pbar.update(1)

    logger.info(f"✨ 任务完成！")
    logger.info(f"📊 总股票数: {total}")
    logger.info(f"✅ 成功更新/下载: {updated_count}")
    logger.info(f"❌ 失败: {failed_count}")
    logger.info(f"⏰ 超时: {timeout_count}")
    logger.info(f"📂 数据保存在: {output_dir}")

    summary = build_download_summary(
        requested_end_date=requested_end_date,
        effective_end_date=end_date,
        stock_list_date=stock_list_date,
        locked_trade_date=locked_trade_date,
        total=total,
        updated_count=updated_count,
        failed_count=failed_count,
        timeout_count=timeout_count,
        data_dir=output_dir,
        max_failure_rate=args.max_failure_rate,
        clean_before_download=clean_flag,
    )
    write_summary_json(args.summary_json, summary)
    logger.info(f"📉 失败率: {summary['failure_rate']:.2%} (门槛 {args.max_failure_rate:.2%})")
    if summary["status"] != "success":
        logger.error("❌ 下载失败率超过门槛，阻止后续生产扫描。")
        return 3
    return 0

if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
