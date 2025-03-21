import os
import re
import shutil
import mistune
import requests
import gh_md_to_html
import css_inline
from geeknews.utils.logger import LOG

# github css cdn
# https://cdnjs.com/libraries/github-markdown-css
GITHUB_MD_CSS_URL="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown.min.css"

# Wrap html tags around content
# https://github.com/KrauseFx/markdown-to-html-github-style/blob/master/convert.js
# "markdown-body" is dark mode supported.
HTML_GITHUB_TEMPLATE = """<!DOCTYPE html>
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

HTML_CSS_STYLE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta charset="utf-8" content="text/html"/>
<style>
{css_style}
</style>
</head>
<body>
{content}
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
        self.re_body_end = re.compile(r'<\/body>')
        self.re_line_terminators = re.compile(r'\n{2,}')
        self.re_comment = re.compile(r'<!-- .*? -->')
        self.re_main_title = re.compile(r'<h1>.*?<\/h1>')
        self.re_subtitle_tag = re.compile(r'<h[^12]>') # find <h3>, <h4> ...
        self.re_footnote = re.compile(r'\[\^(?P<fn>\d+)\]') # [^1], [^2] ...

        # load default css
        css_content = ''
        css_dir = os.path.join(os.getcwd(), 'css')
        css_files = list(filter(lambda x: x.endswith('.css'), os.listdir(css_dir)))
        if css_files:
            css_path = os.path.join(css_dir, css_files[0])
            with open(css_path) as f:
                css_content = f.read()
        self.default_css = css_content
    
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

    def generate_html_from_md_path(
            self, 
            markdown_path, 
            action='mistune', 
            title='', 
            footer=None, 
            css_inline_flag=False, 
            remove_h1=False, 
            compact=False
        ):
        if action == 'mistune':
            # prefers default (sspai styled) css rather then github styled css
            return self.generate_html(
                markdown_path, 
                self.default_css, 
                title, 
                footer, 
                css_inline_flag, 
                remove_h1, 
                compact
            )
        
        html = self.generate_html_by_gh_md(markdown_path, action, footer, css_inline_flag)
        html = self._modify_github_html(html, title)
        if css_inline_flag:
            html = css_inline.inline(html)
        
        return html
    
    def _modify_github_html(self, html_content, title=''):
        # Insert html head and body tags into generated content
        if '<html>' not in html_content[:20]:
            # remove css link from content
            html_content = self.re_link_css.sub('', html_content, count=1)
            # remove meta chatset from content
            html_content = self.re_meta_charset.sub('', html_content, count=1)
            # Insert html head and body tags
            html_content = HTML_GITHUB_TEMPLATE.format(
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
        
        # increate subtitle line spacing: insert <br> in front of each <h?> except <h1>
        subtitle_tag_match = self.re_subtitle_tag.search(html_content)
        if subtitle_tag_match:
            tag_with_br = '<br>\n' + subtitle_tag_match.group()
            html_content = self.re_subtitle_tag.sub(tag_with_br, html_content)
        
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
    
    def generate_html_by_gh_md(self, markdown_path, action, footer=None, css_inline_flag=False):
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
            use_css_link = not css_inline_flag

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
                enable_css_saving=use_css_link, # if false, then css will be inserted into html, no <link>
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
    
    def generate_html(
            self, 
            markdown_path, 
            css_style, 
            title='', 
            footer=None, 
            css_inline_flag=False, 
            remove_h1=False, 
            compact=False
        ):
        if not os.path.exists(markdown_path):
            return ''

        # parse md to html
        with open(markdown_path) as f:
            md_content = f.read()
        
        html_content = mistune.html(md_content)

        # remove h1
        if remove_h1:
            html_content = self.re_main_title.sub('', html_content, 1)

        # check footnotes
        if self.re_footnote.search(html_content):
            html_content = self.re_footnote.sub('<span class="footnote-tag">\g<fn></span>', html_content)
            if len(re.findall(r'<ol>', html_content)) == 1:
                html_content = re.sub(r'<ol>', '<ol id="footnotes">', html_content, count=1)

        # wrap html tags
        full_html = HTML_CSS_STYLE_TEMPLATE.format(
            title=title if title else 'geeknews',
            css_style=css_style,
            content=html_content,
        )

        # insert footer
        if footer:
            footer_content = f"<footer>\n<small>\n{footer}\n</small>\n</footer>\n"
            full_html = self.re_body_end.sub(footer_content+'</body>', full_html, count=1)
        
        # css inline
        if css_inline_flag:
            full_html = css_inline.inline(full_html)

        #remove \n
        if compact:
            full_html = full_html.replace('\n', '')

        return full_html