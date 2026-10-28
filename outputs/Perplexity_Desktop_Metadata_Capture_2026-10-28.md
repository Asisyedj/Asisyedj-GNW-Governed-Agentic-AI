# Perplexity desktop: مختصر connection-metadata capture

**تاریخ:** 2026-10-28 (Pakistan Standard Time)  
**Window:** 04:48:49–04:49:49 PKT (2026-10-27 23:48:49–23:49:49 UTC)  
**طریقہ:** Windows `Get-NetTCPConnection` اور process ID matching؛ Perplexity نام والے process roots اور ان کے child processes تک محدود۔

## مشاہدہ

اس window میں process-linked یہ remote TCP endpoints دیکھے گئے؛ تمام remote ports `443` تھے، یعنی TLS/HTTPS transport استعمال ہو رہا تھا۔ Capture میں application-layer hostname، SNI، URL path، HTTP method، request/response body، headers یا credentials شامل نہیں تھے۔

| PID | Process | Remote IP:port | نظر آنے والی حالت | مشاہدہ شدہ window (UTC) | samples |
|---:|---|---|---|---|---:|
| 4824 | `perplexity.exe` | `104.18.27.48:443` | Established | 23:48:51.921–23:49:48.066 | 45 |
| 12212 | `Perplexity.exe` | `3.233.158.112:443` | FinWait1 | 23:49:34.222–23:49:38.158 | 2 |
| 12212 | `Perplexity.exe` | `3.233.158.24:443` | Established | 23:49:44.715–23:49:48.066 | 2 |
| 12212 | `Perplexity.exe` | `3.233.158.26:443` | Established | 23:49:13.245–23:49:25.900 | 7 |
| 15824 | `Perplexity.exe` | `104.18.27.48:443` | Established | 23:48:51.921–23:49:48.066 | 15 |
| 15824 | `Perplexity.exe` | `142.251.106.105:443` | Established | 23:48:51.921–23:49:48.066 | 45 |
| 15824 | `Perplexity.exe` | `142.251.106.99:443` | Established | 23:48:51.921–23:49:48.066 | 30 |
| 15824 | `Perplexity.exe` | `192.178.211.105:443` | Established | 23:48:51.921–23:49:48.066 | 15 |

## کیا نتیجہ اخذ کیا جا سکتا ہے

اس مختصر مشاہدے میں Perplexity process tree نے اوپر دیے گئے IPs سے TCP/TLS connections رکھے یا بنائے۔ یہ ہر endpoint کے لیے process/PID کی نسبت اور 443 port کا براہِ راست مقامی metadata evidence ہے۔

صرف IP اور port سے hostname یا provider-owned API کا تعین نہیں کیا جا سکتا۔ ایک IP پر کئی سروسز ہو سکتی ہیں، اور app میں background sync، telemetry، static assets یا دیگر calls بھی چل سکتی ہیں۔ Connections کی موجودگی سے یہ ثابت نہیں ہوتا کہ انہی میں سے کوئی خاص connection آپ کے test prompt کو لے کر گیا، نہ یہ معلوم ہوتا ہے کہ کون سا URL/path یا API method استعمال ہوا۔

## حدود

یہ ایک one-time 60 سیکنڈ sample تھا، مسلسل monitoring نہیں۔ اس میں DNS cache، TLS ClientHello/SNI، packet payload، proxy interception، HTTPS decryption، application logs، session state یا credentials نہیں پڑھے گئے۔ لہٰذا prompt-to-connection correlation اور exact hostname فی الحال **NOT ESTABLISHED** ہیں۔ کوئی attack، stress test، fuzzing یا provider endpoint request نہیں بھیجی گئی۔
