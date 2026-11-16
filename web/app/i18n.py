"""Server messages in 13 languages (API errors, default meeting title).

The language comes from the X-Lang header (the page's current language), then Accept-Language, then English.
"""
from contextvars import ContextVar

LANGS = ("en", "es", "fr", "pt", "de", "ru", "uk", "ar", "fa", "ja", "ko", "zh-CN", "zh-TW")
DEFAULT = "en"
_current: ContextVar[str] = ContextVar("hudd_lang", default=DEFAULT)


def norm(lang: str | None) -> str | None:
    s = (lang or "").strip().lower()
    if not s:
        return None
    for c in ("en", "es", "fr", "pt", "de", "ru", "uk", "ar", "fa", "ja", "ko"):
        if s == c or s.startswith(c + "-"):
            return c
    if s in ("zh-tw", "zh-hk", "zh-mo", "zh-hant") or s.startswith("zh-hant"):
        return "zh-TW"
    if s == "zh" or s.startswith("zh-"):
        return "zh-CN"
    return None


def from_headers(x_lang: str | None, accept: str | None) -> str:
    n = norm(x_lang)
    if n:
        return n
    for part in (accept or "").split(","):
        n = norm(part.split(";")[0])
        if n:
            return n
    return DEFAULT


def current() -> str:
    return _current.get()


class LangMiddleware:
    """Puts the request's language into a context variable so handlers can call tr(...)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        h = {k.decode().lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        token = _current.set(from_headers(h.get("x-lang"), h.get("accept-language")))
        try:
            await self.app(scope, receive, send)
        finally:
            _current.reset(token)


M: dict[str, dict[str, str]] = {
 "nick_required": {
  "en": "Please enter your name",
  "es": "Introduce tu nombre",
  "fr": "Veuillez saisir votre nom",
  "pt": "Digite seu nome",
  "de": "Bitte gib deinen Namen ein",
  "ru": "Введите имя",
  "uk": "Введіть ім’я",
  "ar": "يُرجى إدخال اسمك",
  "fa": "لطفاً نامتان را وارد کنید",
  "ja": "名前を入力してください",
  "ko": "이름을 입력하세요",
  "zh-CN": "请填写昵称",
  "zh-TW": "請填寫暱稱"
 },
 "owner_only": {
  "en": "Only the meeting host can do this",
  "es": "Solo el anfitrión de la reunión puede hacer esto",
  "fr": "Seul l’hôte de la réunion peut faire cela",
  "pt": "Só o anfitrião da reunião pode fazer isso",
  "de": "Das kann nur der Gastgeber des Meetings",
  "ru": "Это может сделать только организатор встречи",
  "uk": "Це може зробити лише організатор зустрічі",
  "ar": "لا يمكن القيام بذلك إلا لمضيف الاجتماع",
  "fa": "فقط میزبان جلسه می‌تواند این کار را انجام دهد",
  "ja": "この操作は会議のホストのみ行えます",
  "ko": "회의 호스트만 할 수 있습니다",
  "zh-CN": "只有会议创建者可以执行此操作",
  "zh-TW": "只有會議建立者可以執行此操作"
 },
 "bad_passcode": {
  "en": "Incorrect passcode",
  "es": "Clave de acceso incorrecta",
  "fr": "Code d’accès incorrect",
  "pt": "Código de acesso incorreto",
  "de": "Falscher Zugangscode",
  "ru": "Неверный код доступа",
  "uk": "Неправильний код доступу",
  "ar": "رمز الدخول غير صحيح",
  "fa": "کد ورود نادرست است",
  "ja": "パスコードが正しくありません",
  "ko": "접속 코드가 올바르지 않습니다",
  "zh-CN": "创建会议口令不正确",
  "zh-TW": "建立會議密碼不正確"
 },
 "livekit_down": {
  "en": "Cannot reach the meeting server. Please try again later",
  "es": "No se puede conectar con el servidor de reuniones. Inténtalo más tarde",
  "fr": "Impossible de joindre le serveur de réunion. Réessayez plus tard",
  "pt": "Não foi possível conectar ao servidor de reuniões. Tente novamente mais tarde",
  "de": "Der Meeting-Server ist nicht erreichbar. Bitte versuche es später erneut",
  "ru": "Не удаётся связаться с сервером встреч. Попробуйте позже",
  "uk": "Не вдається зв’язатися із сервером зустрічей. Спробуйте пізніше",
  "ar": "تعذّر الوصول إلى خادم الاجتماعات. حاول لاحقًا",
  "fa": "دسترسی به سرور جلسه ممکن نیست. لطفاً بعداً دوباره امتحان کنید",
  "ja": "会議サーバーに接続できません。しばらくしてからもう一度お試しください",
  "ko": "회의 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요",
  "zh-CN": "无法连接会议服务器，请稍后再试",
  "zh-TW": "無法連線會議伺服器，請稍後再試"
 },
 "default_title": {
  "en": "{nick}'s meeting",
  "es": "Reunión de {nick}",
  "fr": "Réunion de {nick}",
  "pt": "Reunião de {nick}",
  "de": "Meeting von {nick}",
  "ru": "Встреча {nick}",
  "uk": "Зустріч {nick}",
  "ar": "اجتماع {nick}",
  "fa": "جلسهٔ {nick}",
  "ja": "{nick} さんの会議",
  "ko": "{nick} 님의 회의",
  "zh-CN": "{nick} 的会议",
  "zh-TW": "{nick} 的會議"
 },
 "room_pass_required": {
  "en": "This meeting requires a password",
  "es": "Esta reunión requiere contraseña",
  "fr": "Cette réunion exige un mot de passe",
  "pt": "Esta reunião exige senha",
  "de": "Für dieses Meeting ist ein Passwort nötig",
  "ru": "Для этой встречи нужен пароль",
  "uk": "Для цієї зустрічі потрібен пароль",
  "ar": "يتطلب هذا الاجتماع كلمة مرور",
  "fa": "این جلسه رمز لازم دارد",
  "ja": "この会議にはパスワードが必要です",
  "ko": "이 회의는 비밀번호가 필요합니다",
  "zh-CN": "这个会议需要输入房间密码",
  "zh-TW": "這個會議需要輸入房間密碼"
 },
 "room_pass_wrong": {
  "en": "Incorrect meeting password",
  "es": "Contraseña de la reunión incorrecta",
  "fr": "Mot de passe de la réunion incorrect",
  "pt": "Senha da reunião incorreta",
  "de": "Falsches Meeting-Passwort",
  "ru": "Неверный пароль встречи",
  "uk": "Неправильний пароль зустрічі",
  "ar": "كلمة مرور الاجتماع غير صحيحة",
  "fa": "رمز جلسه نادرست است",
  "ja": "会議パスワードが正しくありません",
  "ko": "회의 비밀번호가 올바르지 않습니다",
  "zh-CN": "房间密码不正确",
  "zh-TW": "房間密碼不正確"
 },
 "room_pass_locked": {
  "en": "Too many wrong passwords. Please try again in 10 minutes",
  "es": "Demasiados intentos fallidos. Vuelve a intentarlo dentro de 10 minutos",
  "fr": "Trop de mots de passe erronés. Réessayez dans 10 minutes",
  "pt": "Muitas senhas erradas. Tente novamente em 10 minutos",
  "de": "Zu viele falsche Passwörter. Bitte versuche es in 10 Minuten erneut",
  "ru": "Слишком много неверных паролей. Попробуйте через 10 минут",
  "uk": "Забагато неправильних паролів. Спробуйте через 10 хвилин",
  "ar": "محاولات خاطئة كثيرة. حاول بعد 10 دقائق",
  "fa": "رمز نادرست بیش از حد. ۱۰ دقیقهٔ دیگر دوباره امتحان کنید",
  "ja": "パスワードの誤りが多すぎます。10 分後にもう一度お試しください",
  "ko": "비밀번호를 너무 많이 틀렸습니다. 10분 후 다시 시도하세요",
  "zh-CN": "密码输错次数过多，请 10 分钟后再试",
  "zh-TW": "密碼輸錯次數過多，請 10 分鐘後再試"
 },
 "room_gone": {
  "en": "This meeting has ended or does not exist. Please check the meeting ID",
  "es": "Esta reunión ha terminado o no existe. Comprueba el ID de la reunión",
  "fr": "Cette réunion est terminée ou n’existe pas. Vérifiez l’ID de réunion",
  "pt": "Esta reunião terminou ou não existe. Verifique o ID da reunião",
  "de": "Dieses Meeting ist beendet oder existiert nicht. Bitte prüfe die Meeting-ID",
  "ru": "Эта встреча закончилась или не существует. Проверьте ID встречи",
  "uk": "Ця зустріч завершилася або не існує. Перевірте ID зустрічі",
  "ar": "انتهى هذا الاجتماع أو أنه غير موجود. تحقّق من معرّف الاجتماع",
  "fa": "این جلسه تمام شده یا وجود ندارد. شناسهٔ جلسه را بررسی کنید",
  "ja": "この会議は終了したか、存在しません。会議 ID を確認してください",
  "ko": "이 회의는 종료되었거나 존재하지 않습니다. 회의 ID를 확인하세요",
  "zh-CN": "会议已结束或不存在，请检查会议号",
  "zh-TW": "會議已結束或不存在，請檢查會議號碼"
 },
 "rate_limit": {
  "en": "Too many meetings were started from your network in the last hour (limit {n}). Please try again later",
  "es": "Se han iniciado demasiadas reuniones desde tu red en la última hora (límite {n}). Inténtalo más tarde",
  "fr": "Trop de réunions ont été lancées depuis votre réseau au cours de la dernière heure (limite {n}). Réessayez plus tard",
  "pt": "Muitas reuniões foram iniciadas a partir da sua rede na última hora (limite {n}). Tente novamente mais tarde",
  "de": "In der letzten Stunde wurden zu viele Meetings aus deinem Netzwerk gestartet (Limit {n}). Bitte versuche es später erneut",
  "ru": "За последний час из вашей сети начато слишком много встреч (лимит {n}). Попробуйте позже",
  "uk": "За останню годину з вашої мережі почато забагато зустрічей (ліміт {n}). Спробуйте пізніше",
  "ar": "بدأت اجتماعات كثيرة جدًا من شبكتك خلال الساعة الماضية (الحد {n}). حاول مرة أخرى لاحقًا",
  "fa": "در یک ساعت گذشته جلسه‌های زیادی از شبکهٔ شما شروع شده است (حداکثر {n}). بعداً دوباره امتحان کنید",
  "ja": "過去 1 時間にお使いのネットワークから開始された会議が多すぎます（上限 {n} 件）。しばらくしてからもう一度お試しください",
  "ko": "지난 1시간 동안 사용 중인 네트워크에서 시작된 회의가 너무 많습니다(한도 {n}개). 나중에 다시 시도하세요",
  "zh-CN": "过去一小时内从你的网络发起的会议太多（上限 {n} 场），请稍后再试",
  "zh-TW": "過去一小時內從你的網路發起的會議太多（上限 {n} 場），請稍後再試"
 },
 "open_limit": {
  "en": "Your network already has {n} meetings open. Please end one first",
  "es": "Tu red ya tiene {n} reuniones abiertas. Termina una primero",
  "fr": "Votre réseau a déjà {n} réunions ouvertes. Terminez-en une d’abord",
  "pt": "Sua rede já tem {n} reuniões abertas. Encerre uma primeiro",
  "de": "In deinem Netzwerk sind bereits {n} Meetings offen. Beende zuerst eines",
  "ru": "В вашей сети уже открыто {n} встреч. Сначала завершите одну из них",
  "uk": "У вашій мережі вже відкрито {n} зустрічей. Спершу завершіть одну з них",
  "ar": "لدى شبكتك بالفعل {n} اجتماعات مفتوحة. أنهِ أحدها أولًا",
  "fa": "شبکهٔ شما هم‌اکنون {n} جلسهٔ باز دارد. ابتدا یکی را پایان دهید",
  "ja": "お使いのネットワークからはすでに {n} 件の会議が開かれています。先にどれかを終了してください",
  "ko": "사용 중인 네트워크에 이미 {n}개의 회의가 열려 있습니다. 먼저 하나를 종료하세요",
  "zh-CN": "你的网络已有 {n} 场会议正在进行，请先结束其中一场",
  "zh-TW": "你的網路已有 {n} 場會議正在進行，請先結束其中一場"
 }
}


def tr(key: str, lang: str | None = None, **kw) -> str:
    texts = M.get(key, {})
    s = texts.get(lang or current()) or texts.get(DEFAULT) or key
    return s.format(**kw) if kw else s
