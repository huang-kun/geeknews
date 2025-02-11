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
        
        self.create_tester_file_if_not_exists()
        self.beta_testers = self.load_tester_emails()
        self.dry_run = False

    def get_email_tester_path(self):
        return self.config.beta_tester_path

    def load_tester_emails(self):
        tester_path = self.get_email_tester_path()
        if not os.path.exists(tester_path):
            return []
        
        with open(self.get_email_tester_path()) as f:
            content = f.read().strip()
        
        testers = content.split('\n')
        return list(filter(lambda x: self.re_email.match(x), testers))

    def create_tester_file_if_not_exists(self):
        tester_path = self.get_email_tester_path()
        if os.path.exists(tester_path):
            return

        tester_dir = os.path.dirname(tester_path)
        if not os.path.exists(tester_dir):
            os.makedirs(tester_dir)

        content = self.tester + '\n' if self.tester else ''
        with open(tester_path, 'w') as f:
            content

    def add_tester_email(self, email):
        if not self.re_email.match(email):
            LOG.error(f"无法加入测试邮箱: {email} 非邮箱格式")
            return False
        
        if email in self.beta_testers:
            LOG.error(f"无法加入测试邮箱: {email} 已经存在")
            return False
        
        tester_path = self.get_email_tester_path()
        file_mode = 'a' if os.path.exists(tester_path) else 'w'
        with open(tester_path, file_mode) as f:
            f.write(email + '\n')
        
        return True
    
    def merge_tester_emails(self, email_path):
        if not os.path.exists(email_path):
            LOG.error(f"无法加入测试邮箱: {email_path} 文件路径不存在")
            return False
        
        with open(email_path) as f:
            emails = f.read().strip().split('\n')
        
        valid_emails = []
        for email in emails:
            if not email:
                continue
            if email in self.beta_testers:
                continue
            if not self.re_email.match(email):
                LOG.error(f"无法加入测试邮箱: {email} 非邮箱格式")
                continue
            valid_emails.append(email)

        self.beta_testers.extend(valid_emails)
        tester_path = self.get_email_tester_path()
        with open(tester_path, 'w') as f:
            f.write('\n'.join(self.beta_testers) + '\n')
        
        LOG.info(f"新加入{len(valid_emails)}个测试邮箱")

    def remove_tester_email(self, email):
        if not self.re_email.match(email):
            LOG.error(f"无法删除测试邮箱: {email} 非邮箱格式")
            return False
        
        found_index = -1
        for index, tester in enumerate(self.beta_testers):
            if tester == email:
                found_index = index
                break
        
        if found_index < 0:
            LOG.error(f"无法删除测试邮箱: {email} 不存在")
            return False
        
        del self.beta_testers[found_index]

        tester_path = self.get_email_tester_path()
        with open(tester_path, 'w') as f:
            f.write('\n'.join(self.beta_testers) + '\n')
        
        return True

    def notify(self, title, content, mime_type='html', debug=False):
        if not self.password:
            LOG.error(f'无法发送邮件, 请设置GMAIL_APP_PASSWORD环境变量')
            return
        if not self.sender:
            LOG.error(f'无法发送邮件, 请设置GEEKNEWS_EMAIL_SENDER环境变量')
            return
        if debug and not self.tester:
            LOG.error(f'无法发送邮件, 请设置GEEKNEWS_EMAIL_TESTER环境变量')
            return
        if not debug and not self.beta_testers:
            LOG.error(f'无法发送邮件, beta测试邮箱列表为空')
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
                # if debug:
                #     server.set_debuglevel(1)
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
        content='<h1>HN今日热点</h1>',
        debug=True,
    )
