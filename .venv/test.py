import os

font_path = "/Users/gimtaehyeong/Desktop/코딩/개발/AIPDF/.venv/fonts/NanumGothic.ttf"

if os.path.exists(font_path):
    print("✅ 폰트 파일이 존재합니다!")
else:
    print("❌ 폰트 파일이 존재하지 않습니다.")