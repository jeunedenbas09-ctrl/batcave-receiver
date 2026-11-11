"""Sauvegarde le refresh token Withings renouvelé dans le secret GitHub WITHINGS_REFRESH_TOKEN.
Lancé après maj.py par le workflow. Utilise GH_SECRETS_TOKEN (jeton GitHub avec la permission Secrets en écriture).
Ne journalise jamais la valeur. Efface le fichier temporaire après usage."""
import base64, json, os, urllib.request
from pathlib import Path
from nacl import encoding, public

ICI = Path(__file__).resolve().parent
FICHIER = ICI / "nouveau_refresh.txt"

def requete(methode, url, token, donnees=None):
    corps = json.dumps(donnees).encode() if donnees is not None else None
    r = urllib.request.Request(url, data=corps, method=methode, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=20) as rep:
        return rep.status, (json.loads(rep.read() or b"{}"))

if __name__ == "__main__":
    if not FICHIER.exists():
        print("Pas de nouveau refresh token à sauvegarder."); raise SystemExit(0)
    token = os.environ.get("GH_SECRETS_TOKEN", "")
    depot = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not depot:
        raise SystemExit("GH_SECRETS_TOKEN absent : le nouveau refresh token n'est pas sauvegardé.")
    valeur = FICHIER.read_text(encoding="utf-8").strip()
    FICHIER.unlink()
    api = f"https://api.github.com/repos/{depot}/actions/secrets"
    _, cle = requete("GET", api + "/public-key", token)
    box = public.SealedBox(public.PublicKey(cle["key"].encode(), encoding.Base64Encoder()))
    chiffre = base64.b64encode(box.encrypt(valeur.encode())).decode()
    statut, _ = requete("PUT", api + "/WITHINGS_REFRESH_TOKEN", token, {"encrypted_value": chiffre, "key_id": cle["key_id"]})
    print("Secret WITHINGS_REFRESH_TOKEN mis à jour (statut", statut, ")")
