#!/usr/bin/env python3
"""把 index.html + style.css + app.js + assets 打包成单文件 dist/index.html。
输出不含 <html>/<head>/<body> 包裹，可直接作为 Artifact 发布，也能用浏览器打开。"""
import base64, pathlib, re

root = pathlib.Path(__file__).parent
html = (root / "index.html").read_text(encoding="utf-8")
css  = (root / "style.css").read_text(encoding="utf-8")
js   = (root / "app.js").read_text(encoding="utf-8")

body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
body = body.replace('<link rel="stylesheet" href="style.css">', "")
body = body.replace('<script src="app.js"></script>', "")

for f in sorted((root / "assets").glob("*.webp")):
    uri = "data:image/webp;base64," + base64.b64encode(f.read_bytes()).decode()
    ref = f"assets/{f.name}"
    body = body.replace(ref, uri)
    js = js.replace(ref, uri)

fonts = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Noto+Sans+SC:wght@300;400;500&family=Noto+Serif+SC:wght@300;400;500'
         '&family=Nunito:wght@400;600&display=swap">')

out = (root / "dist"); out.mkdir(exist_ok=True)
(out / "index.html").write_text(
    "<title>记忆家园 Memory Home</title>\n" + fonts + "\n<style>\n" + css + "\n</style>\n"
    + body.strip() + "\n<script>\n" + js + "\n</script>\n", encoding="utf-8")
print("dist/index.html", (out / "index.html").stat().st_size, "bytes")
