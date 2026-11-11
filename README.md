# ClipHUB

[![ClipHUB CI](https://github.com/wasuratsomdet9009/ClipHub/actions/workflows/build.yml/badge.svg)](https://github.com/wasuratsomdet9009/ClipHub/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/wasuratsomdet9009/ClipHub)](https://github.com/wasuratsomdet9009/ClipHub/releases/latest)

เดสก์ท็อปแอปจัดการและแปลงสื่อ พร้อมถอดซับไตเติลด้วย AI สำหรับ Windows 11 และ macOS
ทำด้วย PySide6, FFmpeg, yt-dlp และ faster-whisper (โครงงานรายวิชา SDD2)

## ดาวน์โหลด

[![Download for Windows](https://img.shields.io/badge/Download-Windows%20(.exe)-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/wasuratsomdet9009/ClipHub/releases/latest/download/ClipHUB-Windows.exe)
[![Download for macOS](https://img.shields.io/badge/Download-macOS%20(.dmg)-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/wasuratsomdet9009/ClipHub/releases/latest/download/ClipHUB-macOS.dmg)

| ระบบ | ไฟล์ | วิธีติดตั้ง |
|---|---|---|
| Windows 11 | `ClipHUB-Windows.exe` | ดับเบิลคลิกเพื่อเปิดได้เลย |
| macOS (Apple Silicon) | `ClipHUB-macOS.dmg` | เปิดไฟล์ แล้วลาก ClipHUB ไปไว้ในโฟลเดอร์ Applications |

> **ก่อนใช้งาน:** ต้องติดตั้ง FFmpeg ก่อน ใช้สำหรับแปลงไฟล์ บีบอัด และถอดซับไตเติล
> - macOS: `brew install ffmpeg`
> - Windows: `winget install ffmpeg`
>
> **ไฟล์ติดตั้งยังไม่ได้ลงนามดิจิทัล:** Windows อาจขึ้นคำเตือน SmartScreen ให้กด *More info → Run anyway* ส่วน macOS ให้คลิกขวาที่ ClipHUB แล้วเลือก *Open* หรือไปที่ *System Settings → Privacy & Security → Open Anyway*

## ฟีเจอร์

1. **ดาวน์โหลดวิดีโอ YouTube** วางลิงก์ เลือกความละเอียด หรือดึงเฉพาะเสียงเป็น MP3 แล้วเลือกโฟลเดอร์ปลายทาง
2. **แปลงฟอร์แมต** แปลงวิดีโอและเสียงเป็นฟอร์แมตที่ต้องการ หรือแยกเสียงออกจากวิดีโอ
3. **บีบอัดวิดีโอ** ใช้ H.264/AAC มีโหมด High, Balanced, Small หรือกำหนด kbps เอง พร้อมประเมินขนาดไฟล์ก่อนทำ
4. **ซับไตเติลด้วย AI** ถอดเสียงพูดเป็นไฟล์ `.srt` และ `.vtt` ด้วย faster-whisper รองรับภาษาไทยและอังกฤษ พร้อมดูตัวอย่างก่อนส่งออก

ทุกงานเข้าคิวด้านขวาของหน้าต่าง ดูความคืบหน้า ยกเลิก หรือรอให้เสร็จได้

## รันจากซอร์ส

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## สร้างไฟล์ติดตั้งเอง

```bash
pip install pyinstaller
pyinstaller --noconfirm packaging/ClipHUB.spec
```

macOS จะได้ `dist/ClipHUB.app` ส่วน Windows จะได้ `dist/ClipHUB.exe`

## การปล่อยเวอร์ชัน (สำหรับทีม)

สร้าง tag ที่ `main` แล้วผลักขึ้น GitHub ระบบ CI จะ build ทั้งสองระบบ และสร้าง Release ให้อัตโนมัติ โดยใช้ชื่อไฟล์เดิมเสมอ เพื่อให้ปุ่มดาวน์โหลดด้านบนชี้ไปที่เวอร์ชันล่าสุดได้

```bash
git tag -a v1.0.0 -m "ClipHUB v1.0.0"
git push origin v1.0.0
```

## ทดสอบ

```bash
python3 -m unittest discover -s tests -t . -v
```

## เอกสาร

- ข้อกำหนดความต้องการซอฟต์แวร์ (SRS): [cliphub-srs.md](cliphub-srs.md)
- บันทึกการเปลี่ยนแปลง: [CHANGELOG.md](CHANGELOG.md)

## ทีมพัฒนา

1. นางสาววรัทยา รอดเมล์ รหัสนักศึกษา 68030258
2. นายวศิน แก้วมรกต รหัสนักศึกษา 68030262
3. นายวสุรัชต์ สมเด็จ รหัสนักศึกษา 68030263
4. นายวัฒนพงศ์ พรหมภิราม รหัสนักศึกษา 68030265

## สัญญาอนุญาต

ยังไม่ได้กำหนด รอทีมตัดสินใจ (FFmpeg ที่มาพร้อม libx264 เป็น GPL จึงยังไม่ได้รวมไว้ในไฟล์ติดตั้ง)
