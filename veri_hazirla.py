"""Hesaplayıcının kullandığı aylık seriyi (veri.json) hazırlar.

Kaynaklar (veri/ klasörüne indirilir):
- TÜFE: IMF CPI veri seti, Türkiye, genel endeks (2025=100)
- Mevduat faizi: TCMB EVDS, 3 aya kadar vadeli TL mevduata uygulanan ağırlıklı ortalama faiz
  (akım, TP.TRY.MT02), aylık ortalama. Not: IMF/Dünya Bankası "deposit rate" serisi
  azami (tavan) faizdir, ortalamayı yaklaşık 5–15 puan yüksek gösterir; bu yüzden kullanılmadı.
- Dolar ve euro: Avrupa Merkez Bankası referans kurları (Frankfurter API), aylık ortalama
- Altın: Dünya Bankası Pink Sheet, aylık ortalama ons fiyatı ($)
- BIST 100: Yahoo Finance, ay sonu kapanış (fiyat endeksi, temettü hariç)

Çalıştırma: python veri_hazirla.py          (veri/ içindeki dosyalarla)
            python veri_hazirla.py --indir  (önce dosyaları yeniden indirir)
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

KOK = Path(__file__).parent
VERI = KOK / "veri"
GRAM_ONS = 31.1035
BASLANGIC = "2003-01"

KAYNAKLAR = {
    "imf_cpi_ix.csv": ("https://api.imf.org/external/sdmx/2.1/data/IMF.STA,CPI/TUR.CPI._T.IX.M"
                       "?startPeriod=2003-01", "application/vnd.sdmx.data+csv;version=1.0.0"),
    "fx.json": ("https://api.frankfurter.dev/v1/2002-12-01..?base=TRY&symbols=USD,EUR", None),
    "yahoo_xu100.json": ("https://query1.finance.yahoo.com/v8/finance/chart/XU100.IS"
                         "?range=max&interval=1mo", None),
}


CMO_SAYFA = "https://www.worldbank.org/en/research/commodity-markets"
EVDS_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/fe"
EVDS_SORGU = {"type": "json", "series": "TP.TRY.MT01-TP.TRY.MT02-TP.TRY.MT06", "aggregationTypes": "avg-avg-avg",
              "formulas": "0-0-0", "startDate": "01-01-2002", "endDate": datetime.now().strftime("%d-%m-%Y"),
              "frequency": "5", "decimalSeperator": ".", "decimal": "2", "dateFormat": "0", "lang": "tr",
              "yon": "0", "sira": "0", "ozelFormuller": [], "groupSeperator": True, "isRaporSayfasi": False}


def indir():
    VERI.mkdir(exist_ok=True)
    # TCMB EVDS: sitenin tablo oluştururken kullandığı açık uç (frequency 5 = aylık)
    istek = urllib.request.Request(EVDS_URL, data=json.dumps(EVDS_SORGU).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(istek, timeout=180) as yanit:
        (VERI / "tcmb_mevduat.json").write_bytes(yanit.read())
    print("indirildi: tcmb_mevduat.json")
    # Dünya Bankası Pink Sheet: dosya adresi her yıl değiştiği için güncel bağlantıyı sayfadan bul
    sayfa = urllib.request.urlopen(urllib.request.Request(CMO_SAYFA, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read().decode("utf-8", "ignore")
    cmo_url = re.search(r'https://thedocs\.worldbank\.org[^"]*CMO-Historical-Data-Monthly\.xlsx', sayfa).group(0)
    KAYNAKLAR["cmo_aylik.xlsx"] = (cmo_url, None)
    for ad, (url, accept) in KAYNAKLAR.items():
        istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        if accept:
            istek.add_header("Accept", accept)
        with urllib.request.urlopen(istek, timeout=180) as yanit:
            (VERI / ad).write_bytes(yanit.read())
        print("indirildi:", ad)


def ay(seri_tarih):
    return pd.PeriodIndex(seri_tarih, freq="M")


def tufe():
    d = pd.read_csv(VERI / "imf_cpi_ix.csv", low_memory=False)
    d = d[(d.COICOP_1999 == "_T") & (d.TYPE_OF_TRANSFORMATION == "IX") & (d.INDEX_TYPE == "CPI")]
    return pd.Series(d.OBS_VALUE.values, index=ay(d.TIME_PERIOD.str.replace("-M", "-"))).sort_index()


def mevduat_faizi(seri="TP_TRY_MT02"):
    kalemler = json.loads((VERI / "tcmb_mevduat.json").read_text(encoding="utf-8"))["items"]
    d = pd.DataFrame(kalemler)
    return pd.Series(pd.to_numeric(d[seri]).values, index=ay(d.Tarih)).sort_index()


def kurlar():
    oranlar = json.loads((VERI / "fx.json").read_text())["rates"]
    d = pd.DataFrame(oranlar).T
    d.index = pd.to_datetime(d.index)
    d = 1 / d  # 1 TRY = x USD  ->  1 USD = y TRY
    return d.groupby(d.index.to_period("M")).mean()


def altin_ons_dolar():
    d = pd.read_excel(VERI / "cmo_aylik.xlsx", sheet_name="Monthly Prices", header=4)
    d = d.rename(columns={d.columns[0]: "ay"})
    d = d[d.ay.astype(str).str.match(r"^\d{4}M\d{2}$")]
    return pd.Series(pd.to_numeric(d.Gold).values, index=ay(d.ay.str.replace("M", "-"))).sort_index()


def bist100():
    r = json.loads((VERI / "yahoo_xu100.json").read_text())["chart"]["result"][0]
    # Zaman damgası ayın ilk gününün 00:00'ı (İstanbul saati); kapanış o ayın son değeri
    tr = timezone(timedelta(hours=3))
    aylar = [datetime.fromtimestamp(t, tr).strftime("%Y-%m") for t in r["timestamp"]]
    s = pd.Series(r["indicators"]["quote"][0]["close"], index=ay(aylar), dtype=float)
    return s[~s.index.duplicated(keep="last")].sort_index()


def hazirla():
    t = tufe()
    son = t.index.max()  # TÜFE'nin son ayı hesaplayıcının da son ayı
    aylar = pd.period_range(BASLANGIC, son, freq="M")

    k = kurlar().reindex(aylar)
    faiz = mevduat_faizi().reindex(aylar).ffill()  # açıklanmamış son aylar için son oran
    ons = altin_ons_dolar().reindex(aylar)
    bist = bist100().reindex(aylar)

    # Mevduat: her ay o ayın yıllık faizinin 1/12'si kadar büyür (aylık bileşik, brüt; stopaj sayfada düşülür)
    buyume = 1 + faiz / 1200
    mevduat = buyume.cumprod().shift(1, fill_value=1.0)  # ayın başında yatırılan 1 TL

    tablo = pd.DataFrame({
        "tufe": t.reindex(aylar),
        "usd": k.USD,
        "eur": k.EUR,
        "altin_gram": ons * k.USD / GRAM_ONS,
        "bist": bist,
        "mevduat": mevduat,
        "faiz": faiz,
    }, index=aylar)

    eksik = tablo.isna().sum()
    if eksik.any():
        print("Eksik değerler:\n", eksik[eksik > 0])
        tablo = tablo.ffill()

    tablo.round(6).to_csv(VERI / "aylik_seri.csv", index_label="ay")
    cikti = {
        "guncelleme": datetime.now().strftime("%Y-%m-%d"),
        "aylar": [str(a) for a in aylar],
        **{s: [round(float(v), 6) for v in tablo[s]] for s in tablo.columns},
    }
    (KOK / "veri.json").write_text(json.dumps(cikti, separators=(",", ":")), encoding="utf-8")
    print(f"{aylar[0]} – {aylar[-1]}: {len(aylar)} ay yazıldı")
    print(tablo.iloc[[0, 12 * 10, -13, -1]].round(2).to_string())


if __name__ == "__main__":
    if "--indir" in sys.argv:
        indir()
    hazirla()
