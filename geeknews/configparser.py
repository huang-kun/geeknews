import configparser
import os

class GeeknewsConfigParser:

    def __init__(self, config_path='geeknews_config.ini'):
        self.configparser = configparser.ConfigParser()
        self.configparser.read(config_path)

    def get(self, section, key):
        return self.configparser[section][key]
    
    def get_abs_path(self, section, key):
        value = self.get(section, key)
        if value.startswith('~/'):
            value = os.path.expanduser(value)
        if value.startswith('/'):
            return value
        else:
            return None
        
    def get_integer(self, section, key):
        value = self.get(section, key)
        return int(value)

    def get_bool(self, section, key):
        value = self.get(section, key)
        if value == 'true' or value == 'True' or value == '1':
            return True
        elif value == 'false' or value == 'False' or value == '0':
            return False
        else:
            return bool(value)
