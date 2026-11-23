"""Chiqim nomidan kategoriyani avtomatik aniqlash (o'zbek lotin/kirill, rus, ingliz)."""
import re

CATS = ["food", "transport", "home", "health", "shopping", "fun", "edu", "other"]

# Tartib muhim: birinchi mos kelgan kategoriya olinadi
_KEYWORDS = [
    ("health", """dori apteka shifokor vrach klinika tish tishlar analiz kasalxona kasal shifoxona massaj vitamin
        лекарство аптека врач больница зуб анализ клиника массаж витамин дори дўхтир шифокор касалхона
        medicine pharmacy doctor dentist hospital clinic pills"""),
    ("edu", """kitob kurs o'qish maktab universitet kontrakt repetitor daftar ruchka qalam darslik
        школа курс книга учеба обучение тетрадь репетитор университет контракт китоб дафтар
        book course school tuition university lesson notebook"""),
    ("transport", """taksi taxi yandex benzin metan propan yoqilg'i yoqilgi avtobus metro bus parkovka mashina avto moyka
        yo'lkira yolkira marshrutka zapravka poezd samolyot aviabilet
        такси бензин транспорт проезд метро автобус парковка заправка мойка поезд самолет
        таксі бензин автобус
        fuel parking train flight uber"""),
    ("home", """kommunal kvartira ijara arenda uy svet elektr tok issiqlik internet wifi wi-fi aloqa remont mebel kvartplata
        gaz-pul santexnik tozalash
        аренда коммунал квартплата свет электричество интернет ремонт мебель отопление связь
        ижара коммунал свет интернет таъмир
        rent utilities electricity internet repair furniture"""),
    ("fun", """kino konsert o'yin oyin game bilet damolish park sayohat mehmonxona hotel tatil obuna netflix spotify youtube
        playstation bilyard karaoke teatr sirk attraksion
        кино концерт игра развлечение отдых путешествие подписка театр отель билет
        кино концерт ўйин
        movie cinema trip subscription theatre party club"""),
    ("shopping", """kiyim ko'ylak koylak shim poyabzal krossovka oyoqkiyim sovg'a sovga tuhfa kosmetika parfyum salon soch
        kurtka palto soat sumka telefon noutbuk
        одежда обувь подарок косметика парфюм парикмахерская куртка сумка часы телефон ноутбук
        кийим совға
        clothes shoes gift shopping cosmetics perfume haircut jacket bag watch phone laptop"""),
    ("food", """non go'sht gosht mol tovuq guruch yog' yog sut qatiq suv choy kofe osh lag'mon lagmon somsa shirinlik meva
        sabzi kartoshka piyoz bozor magazin market oziq ovqat tushlik kechki nonushta burger pizza kfc evos lavash
        shawarma hotdog kafe restoran cafe korzinka makro havas carrefour oshxona tort pishiriq muzqaymoq ichimlik
        сок конфеты
        хлеб мясо молоко вода чай кофе еда продукты обед ужин завтрак ресторан кафе магазин рынок сладости фрукты
        нон гўшт сув чой овқат озиқ бозор
        bread meat milk water tea coffee food lunch dinner breakfast grocery groceries restaurant snack fruit drink"""),
]

_TABLE = [(cat, [w for w in words.split() if w]) for cat, words in _KEYWORDS]
_APOS = str.maketrans({"ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'", "´": "'"})
_TOKEN = re.compile(r"[\w'\-]+", re.UNICODE)


def categorize(name: str) -> str:
    if not name:
        return "other"
    tokens = _TOKEN.findall(name.lower().translate(_APOS))
    if not tokens:
        return "other"
    for cat, words in _TABLE:
        for w in words:
            for tok in tokens:
                if tok == w or (len(w) >= 3 and tok.startswith(w)):
                    return cat
    return "other"
