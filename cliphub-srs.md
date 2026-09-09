# เอกสารข้อกำหนดความต้องการซอฟต์แวร์ (Software Requirements Specification: SRS)
## ซอฟต์แวร์จัดการและแปลงสื่อมัลติมีเดีย พร้อมระบบถอดความซับไตเติล (ClipHUB)
### เวอร์ชัน 1.0 (โครงงานรายวิชา SDD2)

---

## 1. บทนำ (Introduction)

### 1.1 วัตถุประสงค์ (Purpose)
เอกสารนี้อธิบายข้อกำหนดความต้องการซอฟต์แวร์สำหรับ **ClipHUB** ซึ่งเป็นเดสก์ท็อปแอปพลิเคชันมัลติแพลตฟอร์ม (Cross-Platform Desktop Application) สำหรับผู้สร้างสรรค์คอนเทนต์ (Content Creators) และคนทำงานวิดีโอ (Video Editors) โดยมีวัตถุประสงค์หลักเพื่อ:
- รวบรวมเครื่องมือจำเป็นเบื้องต้นในการเตรียมทรัพยากรวิดีโอและเสียงไว้ในโปรแกรมเดียว
- อำนวยความสะดวกในการดาวน์โหลดวิดีโอ การแปลงนามสกุลไฟล์ การบีบอัดไฟล์ และการแยกเสียง
- ให้บริการแปลงเสียงพูดในวิดีโอเป็นข้อความซับไตเติลแบบอัตโนมัติพร้อมการซิงก์ Timecode ด้วย AI
- ประยุกต์ใช้หลักการเขียนโปรแกรมเชิงวัตถุ (Object-Oriented Programming: OOP) ในการออกแบบสถาปัตยกรรมซอฟต์แวร์ด้วยภาษา Python
- ฝึกฝนกระบวนการทำงานร่วมกันแบบทีมซอฟต์แวร์ผ่านระบบ Git Branching Strategy และการสร้างระบบ CI/CD ด้วย GitHub Actions

### 1.2 ขอบเขตของระบบ (Scope)
ระบบจะทำงานในรูปแบบ **Desktop Application** ที่รองรับการคอมไพล์เพื่อใช้งานบนระบบปฏิบัติการ **Windows 11** และ **macOS (Intel & Apple Silicon)** โดยรองรับการทำงานหลักดังนี้:
1. **การดาวน์โหลดสื่อภายนอก (Media Downloader):** ดึงคลิปวิดีโอจากแพลตฟอร์ม YouTube ผ่าน URL พร้อมเลือกความละเอียดและฟอร์แมต
2. **การแปลงฟอร์แมตและแยกสื่อ (Format Converter & Audio Separator):** เปลี่ยนนามสกุลไฟล์วิดีโอ/เสียง และแยกสตรีมเสียงออกจากไฟล์วิดีโอ
3. **การบีบอัดขนาดไฟล์ (Media Compressor):** ลดขนาดไฟล์วิดีโอและเสียงด้วยการปรับเปลี่ยน Bitrate และ Preset อัตราส่วนโดยไม่เสียความคมชัดเกินจำเป็น
4. **การถอดความเสียงและสร้างซับไตเติล (AI Speech-to-Text):** แปลงเสียงพูดภาษาไทย/อังกฤษเป็นข้อความ พร้อมคำนวณตำแหน่งเวลาและส่งออกเป็นไฟล์ `.srt`
5. **การประมวลผลเบื้องหลัง (Background Task Management):** มีระบบจัดการคิวงานพร้อม Progress Bar แสดงผล UI ที่ไหลลื่น ไม่ค้างขณะประมวลผลไฟล์ขนาดใหญ่

### 1.3 โครงสร้างทีมและการแบ่งบทบาท (Team Roles & Responsibilities)
โครงการนี้แบ่งความรับผิดชอบออกเป็น 4 ฟีเจอร์หลัก โดยมอบหมายให้สมาชิกในทีม 4 คนรับผิดชอบคนละ 1 ฟีเจอร์ควบคู่กับตำแหน่งทางซอฟต์แวร์ ดังนี้:

| คนที่ | สมาชิก | ตำแหน่งในทีม (Software Role) | ฟีเจอร์หลักที่รับผิดชอบ |
| :---: | :--- | :--- | :--- |
| 1 | สมาชิกคนที่ 1 | **Project Lead & UI Developer** | **Feature 1:** Video Downloader Engine (ดาวน์โหลดสื่อจาก YouTube ผ่าน URL) |
| 2 | สมาชิกคนที่ 2 | **Git Master & System Architect** | **Feature 2:** Format Converter & Audio Separator (แปลงฟอร์แมตและแยกเสียง) |
| 3 | สมาชิกคนที่ 3 | **DevOps & QA Engineer** | **Feature 3:** Media Compressor & Multi-Platform CI/CD (บีบอัดไฟล์ และคุม GitHub Actions) |
| 4 | สมาชิกคนที่ 4 | **Data & Model Specialist** | **Feature 4:** Speech-to-Text & Subtitle Engine (ถอดเสียงเป็นข้อความและทำซับไตเติล) |

### 1.4 ข้อกำหนดการใช้ระบบควบคุมเวอร์ชัน (Git Branching Strategy)
เพื่อจำลองกระบวนการพัฒนาซอฟต์แวร์มาตรฐาน ทีมพัฒนาต้องปฏิบัติตามข้อกำหนด Git ต่อไปนี้:
- **`main` Branch:** ใช้สำหรับบรรจุโค้ดที่ผ่านการทดสอบสมบูรณ์และพร้อมสำหรับคอมไพล์เป็นไฟล์ติดตั้งบน Windows (`.exe`) และ macOS (`.dmg`) ส่งอาจารย์เท่านั้น
- **`develop` Branch:** เป็นสาขาหลักรวมโค้ดของการพัฒนาที่ผ่านการ Code Review แล้ว
- **Feature Branches:** แต่ละคนจะสร้าง Branch ของตนเองแยกจาก `develop` โดยใช้โครงสร้างชื่อ ดังนี้:
  - `feature/downloader` (สำหรับสมาชิกคนที่ 1)
  - `feature/converter` (สำหรับสมาชิกคนที่ 2)
  - `feature/compressor` (สำหรับสมาชิกคนที่ 3)
  - `feature/subtitles` (สำหรับสมาชิกคนที่ 4)
- **ข้อปฏิบัติตามมาตรฐาน:** ห้าม Commit ตรงเข้าสาขา `main` หรือ `develop` โดยเด็ดขาด การรวมโค้ดต้องผ่านกระบวนการ Pull Request (PR) และได้รับอนุมัติจาก Git Master หรือเพื่อนร่วมทีมอย่างน้อย 1 คน

---

## 2. โครงสร้างสถาปัตยกรรมและการออกแบบเชิงวัตถุ (Architecture & OOP Design)

### 2.1 สถาปัตยกรรมระบบ (Layered Architecture)
ระบบถูกออกแบบออกเป็น 4 ชั้นหลัก เพื่อลดการยึดติดกันของโค้ด (Loosely Coupled):
1. **Presentation Layer (GUI):** สร้างด้วย `PySide6` (Qt for Python) เพื่อให้ได้ Native Look & Feel บนทั้ง Windows 11 และ macOS
2. **Task Scheduler Layer:** ใช้ `QThread` เพื่อรันงานประมวลผลเบื้องหลัง ป้องกันหน้าจอหยุดตอบสนอง (Freeze)
3. **Core Processing Engine (OOP Layer):** คลาสประมวลผลงานมีโครงสร้างสืบทอดมาจาก Abstract Base Class เดียวกัน (`BaseMediaTask`)
4. **External Services & Binaries Layer:** ส่วนเชื่อมต่อกับ External Tools ได้แก่ `FFmpeg Binary`, `yt-dlp`, และ `faster-whisper`

### 2.2 การออกแบบเชิงวัตถุ (OOP Class Hierarchy)
ระบบประยุกต์ใช้หลักการ **Abstraction, Inheritance, Encapsulation, และ Polymorphism** เพื่อให้เขียนโค้ดง่าย ขยายระบบสะดวก และตรงตามโจทย์วิชา SDD2:

```text
               +-----------------------+
               |  <<Abstract Class>>   |
               |    BaseMediaTask      |
               +-----------------------+
               | - input_path: str     |
               | - output_path: str    |
               | - progress: int       |
               +-----------------------+
               | + process()*: bool    |
               | + get_progress(): int |
               | + cancel_task(): void |
               +-----------------------+
                           ^
                           | (Inheritance)
     +---------------------+---------------------+---------------------+
     |                     |                     |                     |
+----+----------------+ +--+-----------------+ +-+-----------------+ +-+-------------------+
|   DownloaderTask    | |   ConverterTask    | |   CompressTask    | |   SubtitleTask      |
+---------------------+ +--------------------+ +-------------------+ +---------------------+
| - url: str          | | - target_fmt: str  | | - bitrate: str    | | - model_size: str   |
| - quality: str      | | - extract_audio:bool| | - preset: str     | | - language: str     |
+---------------------+ +--------------------+ +-------------------+ +---------------------+
| + process(): bool   | | + process(): bool  | | + process(): bool | | + process(): bool   |
+---------------------+ +--------------------+ +-------------------+ +---------------------+
```

---

## 3. ความต้องการด้านฟังก์ชันการทำงาน (Functional Requirements)

### 3.1 ระบบดาวน์โหลดสื่อวิดีโอผ่าน URL (Video Downloader Engine) [สมาชิกคนที่ 1]
#### 3.1.1 การรับข้อมูลและตรวจสอบ URL
1. ระบบต้องมีช่องสำหรับรับลิงก์วิดีโอ (URL) จากแพลตฟอร์ม YouTube
2. ระบบต้องทำการตรวจสอบความถูกต้องของ URL (URL Validation) ก่อนเริ่มดาวน์โหลด
3. ระบบต้องดึงข้อมูลเมทาดาต้า (Video Title, Duration, Thumbnail, Available Resolutions) มาแสดงบน UI

#### 3.1.2 การดาวน์โหลดและบันทึกไฟล์
1. ระบบต้องให้ผู้ใช้เลือกความละเอียดของวิดีโอที่ต้องการดาวน์โหลดได้ (เช่น 360p, 720p, 1080p, Best Quality)
2. ระบบต้องสามารถเลือกดาวน์โหลดเฉพาะไฟล์เสียง (Audio-only MP3/M4A) จาก URL ได้
3. ระบบต้องกำหนดโฟลเดอร์ปลายทางในการบันทึกไฟล์ได้
4. ระบบต้องประมวลผลการดาวน์โหลดโดยเรียกใช้ไลบรารี `yt-dlp` ผ่านการควบคุมด้วย Class `DownloaderTask`

---

### 3.2 ระบบแปลงฟอร์แมตและแยกเสียง (Format Converter & Audio Separator Engine) [สมาชิกคนที่ 2]
#### 3.2.1 การแปลงฟอร์แมตวิดีโอและเสียง (Format Conversion)
1. ระบบต้องรองรับการนำเข้าไฟล์วิดีโอหลายประเภท เช่น MP4, MKV, AVI, MOV, WEBM
2. ระบบต้องแปลงไฟล์ไปเป็นนามสกุลเป้าหมายที่เลือก ได้แก่ MP4, MKV, AVI, MOV
3. ระบบต้องแปลงไฟล์เสียงไปเป็นนามสกุล MP3, WAV, AAC, FLAC ได้

#### 3.2.2 การแยกสตรีมเสียงออกจากวิดีโอ (Audio Extraction)
1. ระบบต้องมีโหมดสำหรับดึงสตรีมเสียงออกจากไฟล์วิดีโอโดยเฉพาะ (Audio Separator)
2. ระบบต้องบันทึกไฟล์เสียงที่แยกได้เป็นฟอร์แมต MP3 หรือ WAV โดยที่วิดีโอต้นฉบับไม่เสียหาย
3. การประมวลผลการแปลงและแยกเสียงต้องถูกส่งต่อไปยัง Class `ConverterTask` ที่เรียกใช้งาน `FFmpeg Binary`

---

### 3.3 ระบบบีบอัดขนาดไฟล์สื่อ (Media Compressor Engine) [สมาชิกคนที่ 3]
#### 3.3.1 การบีบอัดไฟล์วิดีโอ (Video Compression)
1. ระบบต้องคำนวณและแสดงขนาดไฟล์เดิมก่อนการบีบอัด
2. ระบบต้องมีตัวเลือกโหมดการบีบอัด เช่น:
   - **Preset Level:** High Quality (ลดลง ~20%), Balanced (ลดลง ~50%), Small Size (ลดลง ~70%)
   - **Custom Target Bitrate:** กำหนด Bitrate วิดีโอเป้าหมาย
3. ระบบต้องทำการปรับลดขนาดวิดีโอโดยใช้ Codec H.264/AAC ผ่าน FFmpeg

#### 3.3.2 การประเมินและรายงานผลขนาดไฟล์
1. ระบบต้องประเมินขนาดไฟล์ผลลัพธ์โดยประมาณก่อนการประมวลผล
2. เมื่อบีบอัดเสร็จสิ้น ระบบต้องแสดงเปรียบเทียบขนาดไฟล์เดิมและขนาดไฟล์ใหม่พร้อมคำนวณเปอร์เซ็นต์การลดลงของไฟล์
3. การประมวลผลบีบอัดต้องควบคุมโดย Class `CompressTask`

---

### 3.4 ระบบถอดเสียงและสร้างซับไตเติลอัตโนมัติ (Speech-to-Text & Subtitle Engine) [สมาชิกคนที่ 4]
#### 3.4.1 การประมวลผลถอดความด้วย AI
1. ระบบต้องรับไฟล์วิดีโอหรือไฟล์เสียง และแยกสตรีมเสียงส่งไปยังโมเดล AI `faster-whisper`
2. ระบบต้องรองรับการถอดเสียงภาษาไทย (TH) และภาษาอังกฤษ (EN)
3. ระบบต้องมีตัวเลือกขนาดโมเดล AI (เช่น `tiny` หรือ `base`) เพื่อความเหมาะสมกับสเปกเครื่องผู้ใช้

#### 3.4.2 การสร้างและซิงก์ Timecode ซับไตเติล
1. ระบบต้องคำนวณตำแหน่งเวลาเริ่มต้นและสิ้นสุด (Start Time - End Time) ของแต่ละประโยคให้ตรงกับเสียงพูด
2. ระบบต้องสร้างไฟล์ซับไตเติลและบันทึกออกเป็นไฟล์นามสกุลมาตรฐาน `.srt` (SubRip Subtitle) และ `.vtt`
3. ระบบต้องอนุญาตให้ผู้ใช้แสดงตัวอย่างข้อความถอดความ (Preview) ก่อนเซฟไฟล์ได้
4. การประมวลผลทั้งหมดต้องควบคุมโดย Class `SubtitleTask`

---

### 3.5 ระบบส่วนต่อประสานผู้ใช้และการจัดการคิวงาน (GUI & Task Queue Manager)
#### 3.5.1 หน้าจอผู้ใช้งาน (User Interface)
1. หน้าจอหลักแบบ Single-Window พัฒนาด้วย `PySide6` แบ่งเมนูตาม 4 ฟีเจอร์หลักชัดเจน
2. แสดงผลในรูปแบบ Modern Theme รองรับสไตล์ทั้งบน Windows 11 และ macOS
3. มีระบบเลือกไฟล์/โฟลเดอร์ผ่าน Native File Dialog ของแต่ละ OS

#### 3.5.2 การจัดการงานเบื้องหลัง (Background Task & Progress Bar)
1. มีระบบ Queue List สำหรับรับงานที่ผู้ใช้กดสั่งประมวลผล
2. มีแถบ Progress Bar และสถานะ Percentage แสดงความก้าวหน้าการทำงานแบบ Real-time
3. มีปุ่มยกเลิกงาน (Cancel Task) ขณะประมวลผล
4. มีระบบ Pop-up Alert แจ้งเตือนเมื่อการประมวลผลเสร็จสิ้นหรือเกิดข้อผิดพลาด

---

## 4. ความต้องการที่ไม่ใช่ฟังก์ชันการทำงาน (Non-Functional Requirements)

### 4.1 ด้านประสิทธิภาพการทำงาน (Performance)
1. **การตอบสนองของ UI:** ปุ่มกดและส่วนต่อประสานผู้ใช้ต้องตอบสนองภายในไม่เกิน 1 วินาที โดย UI ต้องไม่ค้างขณะประมวลผลงานเบื้องหลัง
2. **ความเร็วการถอดความ AI:** โมเดล `faster-whisper` (ขนาด base) ต้องสามารถถอดความวิดีโอความยาว 1 นาทีได้เสร็จสิ้นภายในเวลาไม่เกิน 30 วินาที (บนเครื่องมาตรฐาน)
3. **การใช้ทรัพยากร:** โปรแกรมขณะสแตนด์บายต้องกินหน่วยความจำ RAM ไม่เกิน 200 MB

### 4.2 ด้านความน่าเชื่อถือและการจัดการข้อผิดพลาด (Reliability & Error Handling)
1. **Error Handling:** หาก URL YouTube ไม่ถูกต้อง หรือไฟล์อินพุตเสียหาย ระบบต้องแสดงข้อความ Error ที่เข้าใจง่าย ไม่เกิดการ Crash ปิดตัวเองทันที
2. **Resource Cleanup:** ระบบต้องลบไฟล์ชั่วคราว (Temp files) ออกจากดิสก์เมื่อประมวลผลเสร็จสิ้นทุกครั้ง

### 4.3 ด้านส่วนต่อประสานผู้ใช้และการรองรับภาษา (Usability & Localization)
1. **ภาษาที่รองรับ:** ข้อความบนหน้าจอ GUI ภาษาหลักเป็นภาษาไทยเพื่อการใช้งานที่สะดวก
2. **ความง่ายในการใช้งาน:** ผู้ใช้สามารถเริ่มต้นใช้งานฟังก์ชันหลักได้ภายใน 3 คลิก

### 4.4 ด้านการแพ็กเกจ การรองรับมัลติแพลตฟอร์ม และระบบอัตโนมัติ (Packaging, Multi-Platform & CI/CD)
1. **Multi-Platform Executables:**
   - สำหรับ **Windows 11**: ต้องคอมไพล์ออกมาเป็นไฟล์ **`ClipHUB-Windows.exe`**
   - สำหรับ **macOS**: ต้องคอมไพล์ออกมาเป็นไฟล์ **`ClipHUB-macOS.dmg`** (หรือ `.app` bundle)
2. **Automated Multi-Platform Build Pipeline (GitHub Actions):**
   - ระบบต้องมีสคริปต์ CI/CD อยู่ที่ `.github/workflows/build.yml` สำหรับสั่งสร้างไฟล์ติดตั้งบน Windows และ macOS โดยอัตโนมัติเมื่อมีการ Push โค้ดเข้าสู่ `main` branch
   - ระบบ GitHub Actions ต้องอัปโหลดไฟล์ผลลัพธ์เป็น Build Artifacts ได้แก่ `ClipHUB-Windows.exe` และ `ClipHUB-macOS.dmg`
3. **Zero Dependency:** โปรแกรมเมื่อนำไปเปิดรันบน Windows 11 หรือ macOS เครื่องอื่น ต้องสามารถทำงานได้ทันทีโดยไม่ต้องติดตั้ง Python Environment หรือโปรแกรม FFmpeg แยกต่างหาก (มัดรวม dependencies และ FFmpeg binaries ไว้ในชุด Package)

---

## 5. ข้อจำกัดและเงื่อนไขของระบบ (System Constraints & Tech Stack)

### 5.1 ชุดเทคโนโลยีที่ใช้ในการพัฒนา (Tech Stack)
- **Programming Language:** Python 3.10+
- **GUI Framework:** PySide6 (Qt for Python - Cross Platform)
- **Media Engine:** FFmpeg Static Binaries (`ffmpeg.exe` บน Windows / `ffmpeg` บน macOS)
- **Python Libraries:**
  - `yt-dlp` (สำหรับ Feature 1: Downloader)
  - `ffmpeg-python` (สำหรับ Feature 2 & 3: Converter/Separator/Compressor)
  - `faster-whisper` (สำหรับ Feature 4: AI Subtitle Engine)
- **Packaging Tools:** PyInstaller, create-dmg (สำหรับสร้าง `.dmg` บน macOS)
- **Version Control & CI/CD:** Git / GitHub Actions

### 5.2 สคริปต์การทำ CI/CD บน GitHub Actions (`.github/workflows/build.yml`)

```yaml
name: Build ClipHUB Desktop Application (Windows & macOS)

on:
  push:
    branches: [ "main" ]
  workflow_dispatch:

jobs:
  build:
    name: Build for ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            artifact_name: ClipHUB-Windows.exe
            build_cmd: pyinstaller --onefile --windowed --name ClipHUB main.py
          - os: macos-latest
            artifact_name: ClipHUB-macOS.dmg
            build_cmd: pyinstaller --onefile --windowed --name ClipHUB main.py

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python 3.10
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build Application with PyInstaller
        run: ${{ matrix.build_cmd }}

      - name: Upload Executable Artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact_name }}
          path: dist/*
```

### 5.3 ข้อจำกัดทางเทคนิค (Technical Constraints)
1. **การเชื่อมต่ออินเทอร์เน็ต:** ฟีเจอร์ดาวน์โหลด YouTube จำเป็นต้องมีการเชื่อมต่ออินเทอร์เน็ต ขณะที่ฟีเจอร์ Converter, Compressor และ Subtitle สามารถทำงานแบบ Offline ได้เต็มรูปแบบ
2. **ระบบปฏิบัติการเป้าหมาย:** ตัวโปรแกรมพัฒนาและทดสอบเพื่อรองรับระบบปฏิบัติการ Windows 11 (64-bit) และ macOS 12 Monterey ขึ้นไป (ทั้งชิป Intel และ Apple Silicon)
3. **ลิขสิทธิ์ซอฟต์แวร์:** ใช้เฉพาะ Open-source Libraries ที่มีสัญญาอนุญาตแบบ MIT / Apache / LGPL
