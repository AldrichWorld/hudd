<div dir="rtl">

[English](../../README.md) · [Español](README.es.md) · [Français](README.fr.md) · [Português](README.pt.md) · [Deutsch](README.de.md) · [Русский](README.ru.md) · [Українська](README.uk.md) · **العربية** · [فارسی](README.fa.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

# Hudd

**اجتماعات فيديو مجانية تعمل في المتصفح.** بلا تثبيت، بلا حسابات، بلا حد زمني، وبلا قاعدة بيانات.
شغّل نسختك الخاصة بأمر واحد.

## المزايا

- اجتماعات صوت وفيديو في أي متصفح حديث، على الحواسيب والهواتف
- مشاركة الشاشة مضبوطة ليبقى النص واضحًا
- دردشة داخل الاجتماع مع الإشارة بـ@
- عرض الشبكة وعرض المتحدث، والتثبيت والشاشة الكاملة
- كلمات مرور للاجتماعات
- أدوات المضيف: كتم الجميع، كتم شخص واحد، طلب تشغيل الميكروفون من شخص، إنهاء الاجتماع للجميع
- 13 لغة للواجهة: English, Español, Français, Português, Deutsch, Русский, Українська, العربية, فارسی, 日本語, 한국어, 简体中文, 繁體中文
- يمكن تثبيته كتطبيق (PWA) على الحواسيب والهواتف
- لا يُخزَّن أي شيء: لا قاعدة بيانات ولا حسابات، ورسائل الدردشة لا تُحفظ أبدًا

## البدء السريع

تحتاج إلى [Docker](https://docs.docker.com/get-docker/) مع Docker Compose.

```bash
git clone https://github.com/AldrichWorld/hudd.git
cd hudd
./deploy.sh
```

يطرح السكربت سؤالًا واحدًا فقط: اسم النطاق.

- **على خادم له نطاق:** وجّه سجل DNS من النوع A للنطاق إلى الخادم، وافتح المنافذ TCP 80 و443 و7881 وUDP 7882، ثم اكتب النطاق عند السؤال. يحصل Hudd على شهادة HTTPS مجانية ويعمل على `https://نطاقك`.
- **على حاسوبك أو شبكتك المحلية:** اضغط Enter فقط. يعمل Hudd على `http://localhost:8080`، ويمكن للأجهزة الأخرى في شبكتك استخدام `https://<عنوان IP لهذا الحاسوب>:8443` (شهادة موقّعة ذاتيًا).

أوامر أخرى: `./deploy.sh status` و`./deploy.sh logs` و`./deploy.sh restart` (بعد تعديل `.env`) و`./deploy.sh update` و`./deploy.sh down`.

## الإعدادات

كل الإعدادات في الملف `.env` (يُنشأ عند التشغيل الأول من `.env.example`). أكثرها تغييرًا:

| الإعداد | وظيفته |
|---|---|
| `DOMAIN`, `ACME_EMAIL` | الوضع العام مع HTTPS تلقائي. اترك `DOMAIN` فارغًا للوضع المحلي |
| `CREATE_PASSCODE` | لا يبدأ الاجتماعات إلا من يعرف هذا الرمز. الانضمام عبر رابط لا يحتاج إليه أبدًا |
| `REVERSE_PROXY=host` | خادم Nginx أو Caddy لديك يستخدم المنفذين 80/443 بالفعل (انظر أدناه) |
| `PUBLIC_HOST` | عنوان IP لهذا الجهاز لنقل الصوت والفيديو. يُكتشف تلقائيًا |
| `ROOM_EMPTY_TIMEOUT` | مدة انتظار الاجتماع الجديد لأول شخص (بالثواني، الافتراضي 1800) |
| `ROOMS_PER_HOUR_PER_IP`, `OPEN_ROOMS_PER_IP` | حدود منع إساءة الاستخدام لكل عنوان IP زائر (0 = بلا حد) |
| `APP_NAME`, `SOURCE_URL` | الاسم الظاهر في الصفحات ورابط الشيفرة المصدرية في التذييل |

شغّل `./deploy.sh restart` بعد تعديل `.env`.

### خلف خادم الويب الخاص بك

إذا كان Nginx أو Caddy على الجهاز يستخدم المنفذين 80 و443 بالفعل، فاضبط `REVERSE_PROXY=host` في `.env`. عندها يستمع Hudd على `127.0.0.1:18080` فقط، ويحوّل خادم الويب لديك النطاق إليه، بما في ذلك WebSocket:

```nginx
location / {
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
}
```

مع Caddy يكفي سطر واحد: `نطاقك { reverse_proxy 127.0.0.1:18080 }`. ما زال الصوت والفيديو يحتاجان إلى فتح TCP 7881 وUDP 7882.

## كيف يعمل

يشغّل `docker-compose.yml` ثلاث حاويات:

- **LiveKit** (خادم الوسائط): ينقل الصوت والفيديو ومشاركة الشاشة.
- **web** (Python وFastAPI): الصفحات وواجهة برمجية صغيرة لإنشاء الاجتماعات والانضمام إليها.
- **Caddy** HTTPS، وعنوان واحد للصفحات ولـLiveKit.

لا توجد قاعدة بيانات. يوجد الاجتماع ما دامت غرفته في LiveKit موجودة؛ وتحفظ بيانات الغرفة الموضوع واسم المضيف وتجزئة مفتاحية لكلمة المرور. صلاحيات المضيف تأتي من مفتاح موقَّع، لذلك لا يقطع إعادة تشغيل خدمة الويب أي شيء. رسائل الدردشة تنتقل مباشرة بين المشاركين ولا تُحفظ أبدًا.

```
web/app/         main.py (pages + API) · rooms.py (meetings, no database) · lk.py (LiveKit) · i18n.py (server messages)
web/static/      index.html, room.html, js/, css/
web/static/js/i18n.js   all interface text in 13 languages
tests/           end-to-end tests with a real LiveKit server and a headless browser
```

## التطوير والاختبارات

```bash
pip install -r web/requirements.txt httpx playwright && python -m playwright install chromium
# livekit-server on your PATH: https://docs.livekit.io/home/self-hosting/local/
tests/run_tests.sh
```

## الترجمات

كل نصوص الواجهة موجودة في [`web/static/js/i18n.js`](../../web/static/js/i18n.js)، كتلة لكل لغة. لتصحيح ترجمة أو إضافة لغة، عدّل هذا الملف وافتح طلب دمج (pull request)؛ ويتحقق `tests/test_i18n.py` من أن كل اللغات فيها المفاتيح والمتغيرات نفسها.

## الترخيص

[MIT](../../LICENSE). المكوّنات الخارجية وتراخيصها مذكورة في [THIRD-PARTY-NOTICES](../../web/static/THIRD-PARTY-NOTICES.txt).

Hudd هو النواة مفتوحة المصدر لـ[hudd.live](https://hudd.live).

</div>
