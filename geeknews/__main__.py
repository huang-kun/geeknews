# from geeknews.hackernews.api_client import test_hackernews_client
# from geeknews.hackernews.article_editor import test_hackernews_article_editor
# from geeknews.hackernews.summary_writer import test_hackernews_summary_writer
# from geeknews.hackernews.report_writer import test_hackernews_report_writer
# from geeknews.hackernews.manager import test_hackernews_manager
# from geeknews.notifier import test_geeknews_email_notifier

from geeknews.daemon_process import start_process
from geeknews.command_tool import start_command_tool

if __name__ == '__main__':
    start_process()