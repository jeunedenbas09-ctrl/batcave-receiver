"""Mise à jour Batcave dans le cloud (GitHub Actions) : produit donnees.json et briefing.mp3 pour la TV.
Ne contient aucun secret. Le classement vient de classement_manuel.json (la FFF bloque les serveurs).
Le texte du briefing reprend la logique d'alfred.py (heure, météo, agenda de la semaine, prochaine prière)."""
import asyncio, datetime as dt, json, re, urllib.parse, urllib.request
from pathlib import Path

PARIS = dt.timezone(dt.timedelta(hours=1))
NOW = dt.datetime.now(PARIS)
JOURS = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]
MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
NOM = "Amine"
ICI = Path(__file__).resolve().parent
WMO = {0: "ciel dégagé", 1: "ciel plutôt dégagé", 2: "ciel partiellement nuageux", 3: "ciel couvert",
       45: "brouillard", 48: "brouillard givrant", 51: "bruine légère", 53: "bruine", 55: "bruine forte",
       61: "pluie faible", 63: "pluie", 65: "pluie forte", 71: "neige faible", 73: "neige", 75: "neige forte",
       80: "averses faibles", 81: "averses", 82: "averses fortes", 95: "orage", 96: "orage avec grêle", 99: "orage violent"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8", "replace")

def meteo():
    g = json.loads(get("https://geocoding-api.open-meteo.com/v1/search?name=Choisy-le-Roi&count=1&language=fr"))["results"][0]
    d = json.loads(get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto", "forecast_days": 1,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset"})))
    c, j = d["current"], d["daily"]
    return {"ville": "Choisy-le-Roi", "source": "Open-Meteo", "releve": c["time"], "temp": round(c["temperature_2m"]),
            "ressenti": round(c["apparent_temperature"]), "ciel": WMO.get(c["weather_code"], "temps variable"),
            "vent": round(c["wind_speed_10m"]), "min": round(j["temperature_2m_min"][0]), "max": round(j["temperature_2m_max"][0]),
            "pluie": j["precipitation_probability_max"][0], "ciel_jour": WMO.get(j["weather_code"][0], "temps variable"),
            "lever": j["sunrise"][0][-5:], "coucher": j["sunset"][0][-5:]}

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

def prochaine(now, liste):
    """Prochaine prière d'après l'adhan (Shuruq exclu). Après Isha : la Fajr de demain."""
    mn = now.hour * 60 + now.minute
    prives = [p for p in liste if p["nom"] != "Shuruq"]
    for p in prives:
        h, m = map(int, p["adhan"].split(":"))
        if h * 60 + m > mn:
            return {"nom": p["nom"], "adhan": p["adhan"], "demain": False}
    p = prives[0]
    return {"nom": p["nom"], "adhan": p["adhan"], "demain": True}

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

def affiche(h):
    """« 09:00 » -> « 09 h 00 » ; vide -> « journée » ; « matin », « après-midi » restent tels quels."""
    h = (h or "").strip()
    if not h:
        return "journée"
    if re.fullmatch(r"\d{1,2}:\d{2}", h):
        return h.replace(":", " h ")
    return h

def cle_tri(h):
    """Clé de tri : journée d'abord, matin, puis l'heure, après-midi vers 13 h."""
    h = (h or "").strip()
    if h in ("", "journée"):
        return "00:00"
    if h == "matin":
        return "00:01"
    if h.startswith("après"):
        return "13:00"
    m = re.fullmatch(r"(\d{1,2})\s*(?::|h)\s*(\d{2})", h)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else "23:59"

def emploi_du_jour(now):
    """Semaine type fixe (emploi_du_temps.json) : les entrées du jour."""
    f = ICI / "emploi_du_temps.json"
    if not f.exists():
        return []
    semaine = json.loads(f.read_text(encoding="utf-8")).get("semaine", {})
    out = [{"heure": affiche(e.get("heure", "")), "titre": e["titre"]} for e in semaine.get(JOURS[now.weekday()], [])]
    return sorted(out, key=lambda x: cle_tri(x["heure"]))

def heure_parlee(hhmm):
    h, m = map(int, hhmm.split(":"))
    return f"{h} heures" + (f" {m:02d}" if m else "")

def texte_briefing(now, m, prio, ag, suivante=None):
    # pas d'heure ni de prochaine prière dans la voix : la voix est fixe, l'écran de la TV les affiche en direct au lancement
    p = [f"Bonjour, Monsieur {NOM}. Nous sommes le {JOURS[now.weekday()]} {now.day} {MOIS[now.month - 1]}."]
    if m:
        p.append(f"À {m['ville']}, {m['ciel']}, {m['temp']} degrés, ressenti {m['ressenti']}. "
                 f"Aujourd'hui : {m['ciel_jour']}, entre {m['min']} et {m['max']} degrés, {m['pluie']} pour cent de risque de pluie.")
    else:
        p.append("Je n'ai pas pu joindre le service météo ce matin ; je préfère ne rien vous annoncer plutôt que d'inventer.")
    if ag:
        p.append("À votre agenda : " + " ; ".join(f"{e['heure']}, {e['titre']}" for e in ag[:4]) + ".")
    else:
        p.append("Votre agenda est libre aujourd'hui.")
    if prio:
        ordres = ["Premièrement", "Deuxièmement", "Troisièmement", "Ensuite", "Enfin"]
        p.append(("Vos priorités du jour. " if len(prio) > 1 else "Votre priorité du jour. ") + " ".join(f"{ordres[i]} : {x.rstrip('.')}." for i, x in enumerate(prio[:5])))
    p.append("La Batcave est prête. Force et honneur, Monsieur.")
    return " ".join(p)

async def voix(texte, fichier):
    import edge_tts
    await edge_tts.Communicate(texte, voice="fr-FR-HenriNeural", rate="-10%", pitch="-14Hz").save(fichier)

if __name__ == "__main__":
    prio = [l for l in (ICI / "priorites.json").read_text(encoding="utf-8").splitlines() if l.strip()]
    prio = json.loads("\n".join(prio))
    m = meteo(); pr = prieres(); mt = match()
    ag = emploi_du_jour(NOW)
    suiv = prochaine(NOW, pr["prieres"])
    texte = texte_briefing(NOW, m, prio, ag, suiv)
    donnees = {"date": f"{JOURS[NOW.weekday()]} {NOW.day} {MOIS[NOW.month-1]} {NOW.year}",
               "genere": NOW.strftime("%Y-%m-%d %H:%M"), "meteo": m, "prieres": pr, "priorites": prio,
               "classement": classement(), "match": mt, "corps": None, "agenda": ag,
               "semaine": json.loads((ICI / "emploi_du_temps.json").read_text(encoding="utf-8")).get("semaine", {}),
               "texte": texte, "audio": "briefing.mp3"}
    json.dump(donnees, open("donnees.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    asyncio.run(voix(texte, "briefing.mp3"))
    print("donnees.json et briefing.mp3 prêts")
