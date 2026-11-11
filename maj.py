"""Mise à jour Batcave dans le cloud (GitHub Actions) : produit donnees.json et briefing.mp3 pour la TV.
Ne contient aucun secret. Le classement vient de classement_manuel.json (la FFF bloque les serveurs)."""
import asyncio, datetime as dt, json, re, urllib.parse, urllib.request
from pathlib import Path

PARIS = dt.timezone(dt.timedelta(hours=1))
NOW = dt.datetime.now(PARIS)
JOURS = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]
MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
ICI = Path(__file__).resolve().parent

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8", "replace")

def meteo():
    g = json.loads(get("https://geocoding-api.open-meteo.com/v1/search?name=Choisy-le-Roi&count=1&language=fr"))["results"][0]
    d = json.loads(get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto", "forecast_days": 1,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"})))
    c, j = d["current"], d["daily"]
    return {"ville": "Choisy-le-Roi", "source": "Open-Meteo", "releve": c["time"], "temp": round(c["temperature_2m"]),
            "ressenti": round(c["apparent_temperature"]), "ciel": "", "vent": round(c["wind_speed_10m"]),
            "min": round(j["temperature_2m_min"][0]), "max": round(j["temperature_2m_max"][0]),
            "pluie": j["precipitation_probability_max"][0], "ciel_jour": "", "lever": j["sunrise"][0][-5:], "coucher": j["sunset"][0][-5:]}

def tableau(html, cle):
    i = html.find('"' + cle + '":[')
    d, debut = 0, html.index("[", i)
    for p in range(debut, len(html)):
        d += (html[p] == "[") - (html[p] == "]")
        if d == 0:
            return json.loads(html[debut:p + 1])

def prieres():
    html = get("https://mawaqit.net/fr/mosquee-de-choisy-le-roi-choisy-le-roi")
    cal = tableau(html, "calendar")[NOW.month - 1][str(NOW.day)]
    iq = tableau(html, "iqamaCalendar")[NOW.month - 1][str(NOW.day)]
    adhan = dict(zip(["Fajr", "Shuruq", "Dhuhr", "Asr", "Maghrib", "Isha"], cal))
    out = []
    for nom, dec in zip(["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"], iq):
        a = adhan[nom]; h, m = map(int, a.split(":")); t = (h*60 + m + int(dec.replace("+", ""))) % 1440
        out.append({"nom": nom, "adhan": a, "iqama": f"{t//60:02d}:{t%60:02d}"})
    out.insert(1, {"nom": "Shuruq", "adhan": adhan["Shuruq"], "iqama": None})
    return {"prieres": out, "jumua": ["12:45", "13:45"]}

def classement():
    m = json.loads((ICI / "classement_manuel.json").read_text(encoding="utf-8"))
    lignes = []
    for ligne in m["classement"]:
        rang, reste = ligne.split(" ", 1)
        equipe, pts = reste.rsplit(" - ", 1)
        lignes.append({"rang": int(rang), "equipe": equipe, "pts": int(pts.split()[0]), "j": 0, "g": 0, "n": 0, "p": 0, "diff": 0})
    return {"titre": "Classement · Choisy-le-Roi AS Senior 2", "equipe_suivie": m["equipe_suivie"], "lignes": lignes}

def match():
    m = json.loads((ICI / "match_foot.json").read_text(encoding="utf-8"))
    return m

async def voix(texte, fichier):
    import edge_tts
    await edge_tts.Communicate(texte, voice="fr-FR-HenriNeural", rate="+0%", pitch="-6Hz").save(fichier)

if __name__ == "__main__":
    prio = [l for l in (ICI / "priorites.json").read_text(encoding="utf-8").splitlines() if l.strip()]
    prio = json.loads("\n".join(prio))
    m = meteo(); pr = prieres(); mt = match()
    texte = (f"Bonjour, Monsieur Amine. Nous sommes le {JOURS[NOW.weekday()]} {NOW.day} {MOIS[NOW.month-1]}. "
             f"À Choisy-le-Roi, {m['temp']} degrés, ressenti {m['ressenti']}. "
             "Vos priorités du jour : " + " ; ".join(prio) + ". La Batcave est prête. Force et honneur, Monsieur.")
    donnees = {"date": f"{JOURS[NOW.weekday()]} {NOW.day} {MOIS[NOW.month-1]} {NOW.year}",
               "genere": NOW.strftime("%Y-%m-%d %H:%M"), "meteo": m, "prieres": pr, "priorites": prio,
               "classement": classement(), "match": mt, "corps": None, "agenda": [], "texte": texte, "audio": "briefing.mp3"}
    json.dump(donnees, open("donnees.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    asyncio.run(voix(texte, "briefing.mp3"))
    print("donnees.json et briefing.mp3 prêts")