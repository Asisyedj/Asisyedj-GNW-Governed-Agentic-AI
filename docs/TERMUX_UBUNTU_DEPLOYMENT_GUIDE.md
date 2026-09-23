# GNW Governed Agent v4 — Termux Ubuntu مکمل انسٹالیشن اور رن گائیڈ
## Termux Ubuntu Complete Deployment & Any-API Setup Guide

یہ گائیڈ آپ کے اینڈرائڈ فون پر Termux کے اندر Ubuntu میں GNW ایجنٹ کو 100% آسانی سے چلانے کے لیے تیار کی گئی ہے۔

---

## مرحلہ 1: اپنے فون پر Termux انسٹال کریں (Step 1: Install Termux)
1. اپنے فون میں F-Droid یا GitHub سے **Termux** ایپ ڈاؤن لوڈ کر کے انسٹال کریں۔ (گوگل پلے اسٹور والا Termux پرانا ہے، اس لیے F-Droid والا استعمال کریں)۔
2. Termux کھولیں اور موبائل اسٹوریج کی اجازت دیں:
   ```bash
   termux-setup-storage
   ```
   (فون کی اسکرین پر "Allow" پر کلک کریں)۔

---

## مرحلہ 2: Termux میں Ubuntu انسٹال کریں (Step 2: Install Ubuntu)
Termux کی بلیک اسکرین میں یہ کمانڈز چلائیں:

```bash
pkg update && pkg upgrade -y
pkg install proot-distro -y
proot-distro install ubuntu
```

اب Ubuntu کے اندر داخل ہو جائیں (لاگ ان کریں):
```bash
proot-distro login ubuntu
```
(اب آپ کے سامنے `root@localhost:~#` لکھا آئے گا، یعنی آپ اوبنٹو میں آ چکے ہیں)۔

---

## مرحلہ 3: پروجیکٹ زپ فائل اوبنٹو میں لائیں (Step 3: Copy Project ZIP)
اپنے فون کے Download فولڈر سے زپ فائل کو اوبنٹو میں کاپی کریں اور ان زپ کریں:

```bash
apt update && apt install unzip -y
cp /sdcard/Download/GNW-Governed-Agent-v4-Production.zip ~/
cd ~
unzip GNW-Governed-Agent-v4-Production.zip -d gnw-agent
cd gnw-agent
```

---

## مرحلہ 4: ایک کلک میں خودکار سیٹ اپ (Step 4: One-Click Auto-Setup)
ہم نے آپ کے لیے خودکار انسٹالیشن اسکرپٹ بنا دیا ہے۔ بس یہ چلائیں:

```bash
chmod +x scripts/setup-termux-ubuntu.sh scripts/start-termux.sh
./scripts/setup-termux-ubuntu.sh
```
یہ اسکرپٹ خود بخود:
- Node.js 20 اور ضروری ٹولز انسٹال کر دے گا۔
- تمام پیکیجز انسٹال کرے گا۔
- ویب پیج اور سرور کو کمپائل کر دے گا۔

---

## مرحلہ 5: کوئی بھی API کی (Any API Key) لگانا (Step 5: Configure Any LLM API)
آپ اپنی پسند کا کوئی بھی اے پی آئی (API) لگا سکتے ہیں۔ فائل کو ایڈٹ کرنے کے لیے لکھیں:
```bash
nano .env
```

### 1. OpenAI (ChatGPT):
```ini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=[REDACTED]
LLM_MODEL=gpt-4o-mini
```

### 2. Google Gemini (مفت یا سستا):
```ini
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=[REDACTED]
LLM_MODEL=gemini-1.5-flash
```

### 3. Groq (انتہائی تیز ترین اور مفت لمٹ کے ساتھ):
```ini
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=[REDACTED]
LLM_MODEL=llama-3.3-70b-versatile
```

### 4. OpenRouter (ایک کی سے دنیا کے تمام ماڈلز جیسے Claude، DeepSeek):
```ini
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=[REDACTED]
LLM_MODEL=deepseek/deepseek-chat
```

### 5. بغیر کسی API Key کے آف لائن موڈ (Offline Mode - Zero Cost):
اگر آپ `LLM_API_KEY=` خالی چھوڑ دیں گے تو GNW ایجنٹ بغیر کسی انٹرنیٹ API کے اپنے اندرونی سیکیورٹی اور گورننس انجن پر 100% چلے گا۔

فائل محفوظ کرنے کے لیے کی بورڈ پر دبائیں:  
`Ctrl + O` پھر `Enter` (Save کرنے کے لیے)  
پھر `Ctrl + X` (باہر نکلنے کے لیے)۔

---

## مرحلہ 6: ایجنٹ کو اسٹارٹ کریں اور موبائل پر چلائیں (Step 6: Start & Open in Browser)
Ubuntu میں یہ کمانڈ چلائیں:
```bash
npm start
```
یا
```bash
./scripts/start-termux.sh
```

اب اپنے موبائل فون کا کوئی بھی براؤزر (Chrome یا Brave وغیرہ) کھولیں اور یہ پتہ لکھیں:
```
http://localhost:8787
```

مبارک ہو! آپ کا مکمل GNW گورنر ایجنٹ آپ کے اپنے موبائل فون کے اندر لوکل سرور پر لائیو چل پڑے گا!
