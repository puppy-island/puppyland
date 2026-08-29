#!/usr/bin/env python3
"""把 index.html + style.css + app.js + assets 打包成单文件网页。"""
import base64, pathlib, re

root = pathlib.Path(__file__).parent
html = (root / "index.html").read_text(encoding="utf-8")
css  = (root / "style.css").read_text(encoding="utf-8")
js   = (root / "app.js").read_text(encoding="utf-8")

body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
body = body.replace('<link rel="stylesheet" href="style.css">', "")
body = body.replace('<script src="app.js"></script>', "")

for f in sorted((root / "assets").iterdir()):
    if not f.is_file():
        continue
    mime = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}.get(f.suffix.lower())
    if not mime:
        continue
    uri = "data:" + mime + ";base64," + base64.b64encode(f.read_bytes()).decode()
    ref = f"assets/{f.name}"
    body = body.replace(ref, uri)
    js = js.replace(ref, uri)
    css = css.replace(ref, uri)

fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/font-awesome/6.5.0/css/all.min.css">'
         '<link rel="stylesheet" href="https://cdn.bootcdn.net/ajax/libs/normalize/8.0.1/normalize.min.css">'
         '<link rel="stylesheet" href="https://fonts.googleapis.cn/css2?family=Noto+Sans+SC:wght@300;400;500&family=Noto+Serif+SC:wght@300;400;500&family=Nunito:wght@400;600&family=Schoolbell&display=swap" crossorigin>')

out = (root / "dist"); out.mkdir(exist_ok=True)
# 注意：必须包含 <meta charset="utf-8">，否则部署服务器（C locale）浏览器会乱码
artifact = ("<!doctype html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<title>Puppyland</title>\n" + fonts + "\n<style>\n" + css + "\n</style>\n</head>\n<body>\n"
            + body.strip() + "\n<script>\n" + js + "\n</script>\n</body>\n</html>\n")
(out / "index.html").write_text(artifact, encoding="utf-8")

standalone = ("<!doctype html>\n<html lang=\"zh-CN\">\n<head>\n"
              "<meta charset=\"utf-8\">\n"
              "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
              "<title>Puppyland 完整版</title>\n" + fonts + "\n<style>\n" + css + "\n</style>\n"
              "</head>\n<body>\n" + body.strip()
              + "\n<script>window.PUPPYLAND_FULL_DEMO=true;</script>\n<script>\n" + js
              + "\n</script>\n</body>\n</html>\n")
(out / "Puppyland完整版.html").write_text(standalone, encoding="utf-8")

for name in ("index.html", "Puppyland完整版.html"):
    print("dist/" + name, (out / name).stat().st_size, "bytes")

canvas_source = (root / "review-canvas.html")
if canvas_source.exists():
    canvas = canvas_source.read_text(encoding="utf-8").replace(
        "index.html?reviewScene", "../index.html?reviewScene")
    canvas = canvas.replace("assets/review-shots/", "../assets/review-shots/")
    (out / "Puppyland批注画布.html").write_text(canvas, encoding="utf-8")
    print("dist/Puppyland批注画布.html", (out / "Puppyland批注画布.html").stat().st_size, "bytes")

logic_source = root / "narrative-logic-canvas.html"
if logic_source.exists():
    logic = logic_source.read_text(encoding="utf-8").replace(
        "assets/review-shots/", "../assets/review-shots/")
    (out / "Puppyland叙事逻辑画布.html").write_text(logic, encoding="utf-8")
    print("dist/Puppyland叙事逻辑画布.html", (out / "Puppyland叙事逻辑画布.html").stat().st_size, "bytes")
