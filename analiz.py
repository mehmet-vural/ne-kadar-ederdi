"""Yazı için analiz ve grafikler: "Mevduat mı, altın mı, döviz mi?"

Girdi: veri/aylik_seri.csv (veri_hazirla.py üretir), veri/imf_tavan_faiz.csv (karşılaştırma için)
Çıktı: gorseller/*.png ve ekrana yazdırılan rakamlar
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

KOK = Path(__file__).parent
GORSEL = KOK / "gorseller"
GORSEL.mkdir(exist_ok=True)
STOPAJ = 0.15
TUTAR = 1000
BAS, SON = "2005-01", "2026-09"

AD = {"altin": "Gram altın", "bist": "BIST 100", "usd": "Dolar", "mevduat": "TL mevduat", "eur": "Euro", "tl": "Yastık altı"}
RENK = {"altin": "#C08A12", "bist": "#D4572A", "usd": "#1B7F4B", "mevduat": "#1F5AA6", "eur": "#7B3FB5", "tl": "#8A93A3"}
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 160, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "axes.titleweight": "bold", "axes.titlesize": 13, "font.size": 10.5,
})


def kaydet(fig, ad, kaynak="IMF, TCMB, ECB, Dünya Bankası, Borsa İstanbul"):
    fig.text(0.99, 0.005, f"Kaynak: {kaynak} · Analiz: Mehmet Vural", ha="right", va="bottom", fontsize=8, color="#777")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(GORSEL / f"{ad}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def tl(x):
    return f"{x:,.0f}".replace(",", ".") + " TL"


# --- Seri: her varlık için "1 TL'nin değeri" endeksi -------------------------------
d = pd.read_csv(KOK / "veri" / "aylik_seri.csv", index_col=0)
d.index = pd.PeriodIndex(d.index, freq="M")
deger = pd.DataFrame({
    "altin": d.altin_gram, "bist": d.bist, "usd": d.usd, "eur": d.eur,
    "mevduat": (1 + d.faiz / 1200 * (1 - STOPAJ)).cumprod().shift(1, fill_value=1.0),
    "tl": 1.0,
})
tufe = d.tufe
reel = deger.div(tufe, axis=0)  # alım gücü endeksi


def getiri(bas, son, gercek=True):
    g = reel if gercek else deger
    return g.loc[son] / g.loc[bas] - 1


# --- 1. Ana sonuç: Ocak 2005'te 1.000 TL ---------------------------------------
enf = tufe[SON] / tufe[BAS]
r = getiri(BAS, SON).sort_values()
n = getiri(BAS, SON, gercek=False)
print(f"Fiyatlar {BAS}→{SON}: {enf:.1f} kat; gereken {tl(TUTAR * enf)}")
for k in r.index[::-1]:
    print(f"  {AD[k]:12s} cari {tl(TUTAR * (1 + n[k])):>12s}  alım gücü {TUTAR * (1 + r[k]):>8.0f} TL ({r[k]:+.0%})")

fig, ax = plt.subplots(figsize=(10, 5))
y = np.arange(len(r))
ax.barh(y, TUTAR * (1 + r.values), color=[RENK[k] for k in r.index])
ax.axvline(TUTAR, color="#14213d", lw=1.5, ls="--")
ax.text(TUTAR + 80, -0.75, "kesikli çizgi: başladığınız yer (1.000 TL)", color="#14213d", fontsize=9, va="center")
ax.set_ylim(-1.1, len(r) - 0.5)
for i, k in enumerate(r.index):
    v = TUTAR * (1 + r[k])
    ax.text(v + 120, i, f"{v:,.0f} TL".replace(",", ".") + f"   (bugün {tl(TUTAR * (1 + n[k]))})", va="center", fontsize=9.5)
ax.set_yticks(y, [AD[k] for k in r.index])
ax.set_xlim(0, TUTAR * (1 + r.max()) * 1.45)
ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
ax.set_xlabel("Alım gücü: 2005 fiyatlarıyla kaç TL'lik mal alabilir?")
ax.set_title("Ocak 2005'te 1.000 TL yatırsaydınız, Eylül 2026'da alım gücünüz")
ax.grid(axis="y", visible=False)
kaydet(fig, "1_sonuc")

# --- 2. Alım gücünün yolculuğu ---------------------------------------------------
yol = TUTAR * reel.loc[BAS:SON] / reel.loc[BAS]
fig, ax = plt.subplots(figsize=(10, 5.2))
x = yol.index.to_timestamp()
for k in ["altin", "bist", "usd", "mevduat", "eur", "tl"]:
    ax.plot(x, yol[k], color=RENK[k], lw=2.2 if k in ("altin", "mevduat") else 1.6, ls="--" if k == "tl" else "-", label=AD[k])
ax.axhline(TUTAR, color="#14213d", lw=1, ls=":")
ax.set_yscale("log")
ax.set_yticks([50, 100, 250, 500, 1000, 2500, 5000, 10000, 20000])
ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
ax.set_ylabel("2005 fiyatlarıyla TL (logaritmik)")
ax.set_title("1.000 TL'nin alım gücü yıllar içinde nasıl değişti?")
ax.legend(ncol=3, frameon=False, loc="upper left")
kaydet(fig, "2_yolculuk")

# --- 3. Yıl yıl kazananlar (takvim yılı reel getiri) -------------------------------
yillar = list(range(2003, 2026))
yillik = pd.DataFrame({y: reel.loc[f"{y}-12"] / reel.loc[f"{y - 1}-12"] - 1 if y > 2003 else
                       reel.loc["2003-12"] / reel.loc["2003-01"] - 1 for y in yillar}).T
yillik.index.name = "yil"
sira = ["altin", "bist", "usd", "eur", "mevduat"]
birinci = yillik[sira].idxmax(axis=1)
print("\nYıllık birinciler:", birinci.map(AD).value_counts().to_dict())
print("Mevduatın enflasyonu yendiği yıllar:", [y for y in yillar if yillik.loc[y, "mevduat"] > 0])
print("Son ve ilk sırada olma:", yillik[sira].idxmin(axis=1).map(AD).value_counts().to_dict())

fig, ax = plt.subplots(figsize=(12, 4.6))
for j, y in enumerate(yillar):
    s = yillik.loc[y, sira].sort_values(ascending=False)
    for i, (k, v) in enumerate(s.items()):
        ax.add_patch(plt.Rectangle((j, -i), 0.94, 0.9, color=RENK[k], alpha=0.95 if v > 0 else 0.35, lw=0))
        ax.text(j + 0.47, -i + 0.45, f"{v * 100:+.0f}", ha="center", va="center", fontsize=7.6,
                color="white" if v > 0 else "#14213d", fontweight="bold")
ax.set_xlim(0, len(yillar)); ax.set_ylim(-len(sira) + 0.9, 1)
ax.set_xticks(np.arange(len(yillar)) + 0.47, [str(y) if y > 2003 else "2003*" for y in yillar], fontsize=8.5, rotation=90)
ax.set_yticks([0.45 - i for i in range(len(sira))], ["1.", "2.", "3.", "4.", "5."])
ax.grid(False); [ax.spines[s].set_visible(False) for s in ("left", "bottom")]
ax.tick_params(length=0)
for k in sira:
    ax.bar(0, 0, color=RENK[k], label=AD[k])
ax.legend(ncol=5, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0))
ax.set_title("Her yıl kim kazandı? Enflasyondan arındırılmış yıllık getiri (%)", pad=30)
fig.text(0.01, 0.005, "Soluk kutular: o yıl alım gücü kaybettiren yatırım. *2003: Ocak–Aralık.", fontsize=8, color="#777")
kaydet(fig, "3_yillar")

# --- 4. En kötü dönem: zirveden en büyük reel düşüş --------------------------------
print("\nZirveden en büyük reel düşüş:")
dusus = {}
for k in sira:
    s = reel[k].loc["2003-01":SON]
    zirve = s.cummax(); dd = s / zirve - 1
    dip = dd.idxmin(); tepe = s.loc[:dip].idxmax()
    sonra = s.loc[dip:]; geri = sonra[sonra >= s[tepe]]
    toparlanma = geri.index[0] if len(geri) else None
    dusus[k] = (dd.min(), tepe, dip, toparlanma)
    print(f"  {AD[k]:12s} {dd.min():+.0%}  {tepe} → {dip}  toparlanma: {toparlanma}")

fig, ax = plt.subplots(figsize=(10, 4.6))
ks = sorted(sira, key=lambda k: dusus[k][0])
ax.barh(range(len(ks)), [dusus[k][0] * 100 for k in ks], color=[RENK[k] for k in ks])
for i, k in enumerate(ks):
    v, t, dp, tp = dusus[k]
    ay = lambda p: ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"][p.month - 1] + f" {p.year}"
    not_ = f"{ay(t)} → {ay(dp)}  ·  " + (f"eski seviyeye dönüş: {ay(tp)}" if tp is not None else "henüz eski seviyesine dönmedi")
    ax.text(v * 100 - 1, i, f"%{abs(v) * 100:.0f}   ", ha="right", va="center", fontsize=10, fontweight="bold")
    ax.text(1, i, not_, va="center", fontsize=9)
ax.set_yticks(range(len(ks)), [AD[k] for k in ks])
ax.set_xlim(min(dusus[k][0] for k in ks) * 100 - 14, 70)
ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"%{v:.0f}" if v <= 0 else ""))
ax.set_title("En kötü dönem: Alım gücü zirveden en fazla ne kadar düştü?")
ax.grid(axis="y", visible=False)
kaydet(fig, "4_dusus")

# --- 5. Ne kadar beklersen: enflasyonu yenme ihtimali --------------------------------
sureler = [1, 2, 3, 5, 10]
olasilik = pd.DataFrame(index=sureler, columns=sira, dtype=float)
medyan = olasilik.copy()
s = reel.loc["2003-01":SON]
for yil in sureler:
    g = s.shift(-12 * yil) / s - 1
    g = g.dropna()
    olasilik.loc[yil] = (g[sira] > 0).mean()
    medyan.loc[yil] = g[sira].median()
print("\nEnflasyonu yenme oranı (başlangıç ayları):\n", (olasilik * 100).round(0).to_string())
print("Medyan reel getiri:\n", (medyan * 100).round(0).to_string())

fig, ax = plt.subplots(figsize=(10, 4.8))
w = 0.16
for i, k in enumerate(sira):
    ax.bar(np.arange(len(sureler)) + (i - 2) * w, olasilik[k] * 100, w * 0.95, color=RENK[k], label=AD[k])
ax.axhline(50, color="#14213d", lw=1, ls=":", label="%50 (yazı tura)")
ax.set_xticks(range(len(sureler)), [f"{y} yıl" for y in sureler])
ax.yaxis.set_major_formatter(mtick.PercentFormatter())
ax.set_ylim(0, 105)
ax.set_xlabel("Paranızı ne kadar süre tuttunuz?")
ax.set_ylabel("Enflasyonu yendiğiniz dönemlerin oranı")
ax.set_title("Ne kadar uzun beklerseniz: Enflasyonu yenme ihtimali (2003–2026)")
ax.legend(ncol=6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=9.5)
ax.grid(axis="x", visible=False)
kaydet(fig, "5_sure")

# --- 6. Veri tuzağı: tavan faiz mi, ortalama faiz mi? ---------------------------------
imf = pd.read_csv(KOK / "veri" / "imf_tavan_faiz.csv")
imf = pd.Series(imf.OBS_VALUE.values, index=pd.PeriodIndex(imf.TIME_PERIOD.str.replace("-M", "-"), freq="M")).sort_index()
ort = d.faiz
fark = (imf - ort).dropna()
print(f"\nTavan - ortalama faiz farkı: ortalama {fark.mean():.1f} puan, en fazla {fark.max():.1f} ({fark.idxmax()})")
print("Ocak 2023:", imf["2023-01"], ort["2023-01"])
mev_tavan = (1 + imf.reindex(d.index).ffill() / 1200 * (1 - STOPAJ)).cumprod().shift(1, fill_value=1.0) / tufe
t_r = mev_tavan[SON] / mev_tavan[BAS] - 1
print(f"Tavan faizle mevduat {BAS}→{SON} alım gücü: {t_r:+.0%}  (ortalama faizle {r['mevduat']:+.0%})")

fig, ax = plt.subplots(figsize=(10, 4.6))
x = ort.index.to_timestamp()
ax.plot(imf.index.to_timestamp(), imf, color="#C8102E", lw=1.8, label="Uluslararası veri tabanındaki \"mevduat faizi\" (aslında tavan faiz)")
ax.plot(x, ort, color="#1F5AA6", lw=2.2, label="Bankaların fiilen ödediği ortalama faiz (TCMB)")
ax.fill_between(x, ort, imf.reindex(ort.index).values, color="#C8102E", alpha=0.08)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.set_title("Hangi mevduat faizi? Tavan ile ortalama arasındaki fark")
ax.legend(frameon=False, loc="upper center")
ax.set_ylabel("Yıllık faiz")
kaydet(fig, "6_faiz_tuzagi", kaynak="IMF, TCMB")

# --- Ek rakamlar -----------------------------------------------------------------
print("\nBaşlangıç yılına göre (Ocak→Eylül 2026) mevduat ve dolar alım gücü:")
for y in [2003, 2005, 2010, 2015, 2018, 2020, 2021, 2022, 2023, 2024]:
    g = getiri(f"{y}-01", SON)
    print(f"  {y}: " + "  ".join(f"{AD[k]} {g[k]:+.0%}" for k in ["altin", "bist", "usd", "mevduat", "eur", "tl"]))
print("\nSon 12 ay (2025-09→2026-09):", {AD[k]: f"{v:+.0%}" for k, v in getiri("2025-09", SON).items()})
print("Ocak 2005 → Eylül 2026 gram altın:", round(d.altin_gram[BAS], 1), "→", round(d.altin_gram[SON]), "TL;",
      "dolar:", round(d.usd[BAS], 2), "→", round(d.usd[SON], 2))
print("Yıllık enflasyon ortalaması (bileşik):", f"{enf ** (12 / (len(yol) - 1)) - 1:.1%}")
