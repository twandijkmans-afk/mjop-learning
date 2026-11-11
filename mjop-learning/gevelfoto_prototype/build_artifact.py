"""Maakt van index.html de variant voor een claude.ai-artifact: dezelfde pagina zonder doctype/html/head/body
(die voegt het platform zelf toe). Gebruik: python build_artifact.py <uitvoerbestand>"""
import re
import sys
from pathlib import Path

src = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
head = re.search(r"<head>(.*?)</head>", src, re.S).group(1)
body = re.search(r"<body>(.*?)</body>", src, re.S).group(1)
head = re.sub(r"<meta (charset|name=\"viewport\")[^>]*>\n?", "", head).strip()
Path(sys.argv[1]).write_text(head + "\n" + body.strip() + "\n", encoding="utf-8")
