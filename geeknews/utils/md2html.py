import os
import re
import shutil
import mistune
import requests
import gh_md_to_html
from geeknews.utils.logger import LOG

# github css cdn
# https://cdnjs.com/libraries/github-markdown-css
GITHUB_MD_CSS_URL="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css"

# Wrap html tags around content
# https://github.com/KrauseFx/markdown-to-html-github-style/blob/master/convert.js
# "markdown-body" is dark mode supported.
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="utf-8" content="text/html"/>
<link href="{css_path}" rel="stylesheet"/>
</head>
<body>
<div class="markdown-body">
{content}
</div>
</body>
</html>
"""

class MarkdownRenderer:
    '''Markdown to html'''
    
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        self.re_link_css = re.compile(r'<link href="(?P<href>.*)"\srel="stylesheet".*?>')
        self.re_meta_charset = re.compile(r'<meta charset=.*?>') # find <meta charset=...>
        self.re_style = re.compile(r'<style.*?\/style>', re.DOTALL) # find <style> tags
        self.re_head_end = re.compile(r'<\/head>')
        self.re_line_terminators = re.compile(r'\n{2,}')
        self.re_comment = re.compile(r'<!-- .*? -->')
    
    @staticmethod
    def get_cache_dir():
        cache_path = os.path.expanduser('~/data/geeknews/caches')
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        return cache_path
    
    @staticmethod
    def clean_all_caches():
        cache_path = MarkdownRenderer.get_cache_dir()
        if not os.path.exists(cache_path):
            return
        try:
            shutil.rmtree(cache_path)
        except OSError as e:
            LOG.error(f"清理渲染html缓存失败: {e.strerror}")
        except Exception as e:
            LOG.error(f"清理渲染html缓存失败: {e}")

    def generate_html_from_md_path(self, markdown_path, action='mistune', title='', footer=None):
        html = self.generate_html_by_gh_md(markdown_path, action, footer)
        return self._modify_html(html, title)
    
    def _modify_html(self, html_content, title=''):
        # Insert html head and body tags into generated content
        if '<html>' not in html_content[:20]:
            # remove css link from content
            html_content = self.re_link_css.sub('', html_content, count=1)
            # remove meta chatset from content
            html_content = self.re_meta_charset.sub('', html_content, count=1)
            # Insert html head and body tags
            html_content = HTML_TEMPLATE.format(
                title=title,
                css_path=GITHUB_MD_CSS_URL,
                content=html_content,
            )
        
        # move style tags from body to head
        styles = self.re_style.findall(html_content)
        if styles:
            html_content = self.re_style.sub('', html_content)
            styles.append('</head>')
            html_content = self.re_head_end.sub('\n'.join(styles), html_content)

        # remove comments
        html_content = self.re_comment.sub('', html_content)
        # remove extra \n
        html_content = self.re_line_terminators.sub('\n', html_content)
        
        return html_content

    def generate_html_by_github_api(self, markdown_text):
        '''markdown to html via github api'''
        # https://docs.github.com/en/rest/markdown/markdown?apiVersion=2022-11-28#render-a-markdown-document

        url = "https://api.github.com/markdown"
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': 'Bearer ' + self.github_token,
            'X-GitHub-Api-Version': '2022-11-28',
        }
        data = {
            'text': markdown_text
        }
        try:
            response = requests.post(url=url, json=data, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            LOG.error(f'github api渲染html失败: {str(e)}')
        
        return ''
    
    def generate_html_by_gh_md(self, markdown_path, action, footer=None):
        '''markdown to html with github css style'''
        # https://github.com/phseiff/github-flavored-markdown-to-html

        basename = os.path.basename(markdown_path)
        filename, _ = os.path.splitext(basename)
        output_name = filename + '.html'

        convert_func = gh_md_to_html.markdown_to_html_via_github_api
        if action == 'mistune':
            convert_func = mistune.html
        elif action == 'github_api' and self.github_token:
            convert_func = self.generate_html_by_github_api

        try:
            html = gh_md_to_html.main(
                md_origin=markdown_path, 
                origin_type='file',
                website_root=self.get_cache_dir(),
                destination=filename,
                css_paths='github-markdown-css',
                output_name=output_name,
                footer=self.get_footer(footer),
                math='false', # if true, then parse some chars (like $) to formulas and generate svg tags
                core_converter=convert_func,
                box_width='800px',
                enable_css_saving=True, # if false, then css will be inserted into html, no <link>
            )
            
            return html

        except Exception as e:
            LOG.error(f'gh_md_to_html渲染html失败: {str(e)}')

        return ''

    def get_footer(self, footer=None):
        if not footer:
            return None
        
        footer_style = "font-size: 0.875rem; line-height: 1.25; text-align: center; padding: 20px 0;"
        return f"<footer style=\"{footer_style}\">\n<p style=\"margin: 0;\">{footer}</p>\n</footer>"
