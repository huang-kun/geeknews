from geeknews.configparser import GeeknewsConfigParser

class GeeknewsEmailConfig:

    section = 'Email'

    smtp_server: str
    smtp_port: int
    beta_tester_path: str

    @classmethod
    def get_from_parser(cls, configparser: GeeknewsConfigParser = GeeknewsConfigParser()):
        cls.smtp_server = configparser.get(cls.section, 'smtp_server')
        cls.smtp_port = configparser.get_integer(cls.section, 'smtp_port')
        cls.beta_tester_path = configparser.get_abs_path(cls.section, 'beta_tester_path')
        return cls()
    

class GeeknewsWechatPPConfig:

    section = 'WechatPP'

    access_token_path: str

    @classmethod
    def get_from_parser(cls, configparser: GeeknewsConfigParser = GeeknewsConfigParser()):
        cls.access_token_path = configparser.get_abs_path(cls.section, 'access_token_path')
        return cls()