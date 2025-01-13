import os, sys
import time, signal, schedule

from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate

from geeknews.llm import LLM
from geeknews.notifier.email_notifier import GeeknewsEmailNotifier
from geeknews.configparser import GeeknewsConfigParser
from geeknews.config import GeeknewsEmailConfig

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.manager import HackernewsManager

from geeknews.manager import GeeknewsManager

# 借鉴彭老师的实现, 本人也是极客时间AI Agent的二期学员
# https://github.com/DjangoPeng/GitHubSentinel/blob/main/src/daemon_process.py

def graceful_shutdown(signum, frame):
    # 优雅关闭程序的函数，处理信号时调用
    LOG.info("[优雅退出]守护进程接收到终止信号")
    sys.exit(0)  # 安全退出程序


def hacker_news_daily_job(geeknews_manager: GeeknewsManager):
    LOG.info('[开始执行定时任务]Hacker News每日热点汇总')

    locale = 'zh_cn'
    date = GeeknewsDate.now()
    override = True

    report_path = geeknews_manager.hackernews_dpm.get_report_file_path(locale=locale, date=date, ext='.html')
    
    if not os.path.exists(report_path):
        geeknews_manager.hackernews_manager.generate_daily_report(locale=locale, date=date, override=override)
    if not os.path.exists(report_path):
        LOG.error("[定时任务]未发现任何报告")
        return
    
    with open(report_path) as f:
        report_html = f.read()

    geeknews_manager.email_notifier.notify(title='Hacker News 今日热点', content=report_html)

    LOG.info(f"[定时任务执行完毕]")


def start_process():
    # 设置信号处理器
    signal.signal(signal.SIGTERM, graceful_shutdown)

    geeknews_manager = GeeknewsManager()

    # 启动时立即执行（如不需要可注释）
    # hacker_news_daily_job(geeknews_manager)

    hn_freq_days = geeknews_manager.hackernews_config.update_freq_days
    hn_exec_time = geeknews_manager.hackernews_config.update_exec_time

    schedule.every(hn_freq_days).days.at(hn_exec_time).do(
        hacker_news_daily_job, 
        geeknews_manager,
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        LOG.error(f"主进程发生异常: {str(e)}")
        sys.exit(1)