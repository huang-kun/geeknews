import os
import re
import sys
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from geeknews.utils.logger import LOG
from geeknews.config import GeeknewsEmailConfig

class GeeknewsEmailNotifier:

    def __init__(self, config: GeeknewsEmailConfig):
        self.config = config
        self.re_email = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

        self.password = os.getenv('GMAIL_APP_PASSWORD', '')
        self.sender = os.getenv('GEEKNEWS_EMAIL_SENDER', '')
        self.tester = os.getenv('GEEKNEWS_EMAIL_TESTER', '')

        if not self.tester:
            LOG.error('请设置GEEKNEWS_EMAIL_TESTER环境变量')
            sys.exit(1)
        if not self.re_email.match(self.tester):
            LOG.error('GEEKNEWS_EMAIL_TESTER不是合法的邮箱地址')
            sys.exit(1)
        
        self.create_tester_file_if_not_exists()
        self.beta_testers = self.load_tester_emails()
        self.dry_run = False

    def get_email_tester_path(self):
        return self.config.beta_tester_path

    def load_tester_emails(self):
        with open(self.get_email_tester_path()) as f:
            content = f.read().strip()
        testers = content.split('\n')
        return list(filter(lambda x: len(x) > 0, testers))

    def create_tester_file_if_not_exists(self):
        tester_path = self.get_email_tester_path()
        if os.path.exists(tester_path):
            return

        tester_dir = os.path.dirname(tester_path)
        os.makedirs(tester_dir)

        if self.tester:
            with open(tester_path, 'w') as f:
                f.write(self.tester + '\n')

    def add_tester_email(self, email):
        if not self.re_email.match(email):
            LOG.error(f"无法加入测试邮箱: {email}")
            return False
        
        tester_path = self.get_email_tester_path()
        with open(tester_path, 'a') as f:
            f.write(email + '\n')
        
        return True

    def remove_tester_email(self, email):
        if not self.re_email.match(email):
            LOG.error(f"无法删除测试邮箱: {email}")
            return False
        
        found_index = -1
        for index, tester in enumerate(self.beta_testers):
            if tester == email:
                found_index = index
                break
        
        if found_index < 0:
            return False
        
        del self.beta_testers[found_index]

        tester_path = self.get_email_tester_path()
        with open(tester_path, 'w') as f:
            f.write('\n'.join(self.beta_testers))
        
        return True

    def notify(self, title, content, mime_type='html', debug=False):
        if not self.password:
            LOG.error(f'无法发送邮件, 请设置GMAIL_APP_PASSWORD环境变量')
            return
        if not self.sender:
            LOG.error(f'无法发送邮件, 请设置GEEKNEWS_EMAIL_SENDER环境变量')
            return
        if not self.tester:
            LOG.error(f'无法发送邮件, 请设置GEEKNEWS_EMAIL_TESTER环境变量')
            return
        
        LOG.info(f"准备发送邮件")

        host = self.config.smtp_server
        port = self.config.smtp_port
        sender = self.sender
        target = self.tester if debug else ', '.join(self.beta_testers)

        if self.dry_run:
            LOG.debug(f"模拟发送邮件 - from: {sender}, to: {target}, subject: {title}, content: {content[:10]}...")
            return

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = target
        msg['Subject'] = title
        msg.attach(MIMEText(content, mime_type))

        try:
            with smtplib.SMTP(host=host, port=port) as server:
                if debug:
                    server.set_debuglevel(1)
                LOG.debug("登录SMTP服务器")
                server.starttls()
                server.login(sender, self.password)
                server.sendmail(sender, target.split(', '), msg.as_string())
                LOG.info("邮件发送成功！")
        except Exception as e:
            LOG.error(f"发送邮件失败：{str(e)}")


def test_geeknews_email_notifier():
    config = GeeknewsEmailConfig.get_from_parser()
    notifier = GeeknewsEmailNotifier(config)
    notifier.notify(
        title='Email testing',
        content='<h1>Hacker News 今日热点</h1>',
        debug=True,
    )
