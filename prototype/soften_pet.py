"""把 rainbow-bridge.png 里那条清晰的狗狗背影局部模糊掉，背景保持原清晰度。

用法：python3 soften_pet.py [半径]
半径是源图像素；页面上以 cover 缩放约 0.56，故屏幕观感 ≈ 半径 * 0.56。
"""
import sys
from PIL import Image, ImageDraw, ImageFilter

SRC = 'assets/rainbow-bridge.png'
DST = 'assets/rainbow-bridge-soft.png'
# 狗狗（含光环、尾巴、四条腿）的外接椭圆
CENTER, RX, RY = (517, 768), 148, 178
FEATHER = 42          # 蒙版羽化，越大过渡越自然


def soften(radius, dst=DST):
    im = Image.open(SRC).convert('RGB')
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).ellipse(
        [CENTER[0] - RX, CENTER[1] - RY, CENTER[0] + RX, CENTER[1] + RY], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(FEATHER))
    out = Image.composite(im.filter(ImageFilter.GaussianBlur(radius)), im, mask)
    out.save(dst)
    return dst


if __name__ == '__main__':
    r = float(sys.argv[1]) if len(sys.argv) > 1 else 14
    print(soften(r), 'radius=', r)
