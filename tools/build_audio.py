#!/usr/bin/env python3
"""Build every audio file the game needs from content.json (macOS only).

  sounds/<animal>.m4a   real animal recordings from Wikimedia Commons,
                        trimmed to the loudest part and volume-matched
  voice/*.m4a           Norwegian narration recorded with the macOS "Nora" voice
  CREDITS.md            authors and licences of the recordings (required by the licences)

Usage:  python3 tools/build_audio.py          # only builds what is missing
        python3 tools/build_audio.py --force  # rebuild everything
        python3 tools/build_audio.py --voice-only  # only the narration
Needs only the tools that ship with macOS: curl, afconvert and say.
"""
import array, html, json, os, re, subprocess, sys, tempfile, time, urllib.parse, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "tools", "cache")
FORCE = "--force" in sys.argv
VOICE_ONLY = "--voice-only" in sys.argv  # just record narration, skip downloads
UA = "toddler-app-prototype/1.0 (personal, non-commercial)"
VOICE, RATE = "Nora", "160"
SR = 44100

def run(*cmd):
    subprocess.run(cmd, check=True, capture_output=True)

def curl_json(url):
    for attempt in range(8):
        out = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, url], capture_output=True, text=True).stdout
        try:
            return json.loads(out)
        except ValueError:
            time.sleep(10 * (attempt + 1))  # Commons rate-limits bursts
    raise RuntimeError("Commons API not answering: " + url)

META = os.path.join(CACHE, "meta.json")

def load_commons_info(titles):
    """Look up download URL, author and licence for all files, in batches of 40, cached on disk."""
    os.makedirs(CACHE, exist_ok=True)
    known = json.load(open(META)) if os.path.exists(META) else {}
    missing = [t for t in titles if t not in known]
    for i in range(0, len(missing), 40):
        batch = missing[i:i + 40]
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "titles": "|".join("File:" + t for t in batch),
            "prop": "imageinfo", "iiprop": "url|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist",
        })
        res = curl_json("https://commons.wikimedia.org/w/api.php?" + q)["query"]
        # The API normalises titles (e.g. underscores), so map the answers back to what we asked for.
        norm = {n["to"]: n["from"] for n in res.get("normalized", [])}
        for page in res["pages"].values():
            asked = norm.get(page["title"], page["title"])[len("File:"):]
            if "imageinfo" not in page:
                raise RuntimeError("Not found on Commons: " + asked)
            ii = page["imageinfo"][0]
            meta = ii.get("extmetadata", {})
            artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", "unknown")))
            known[asked] = {"url": ii["url"], "page": ii["descriptionurl"],
                            "license": meta.get("LicenseShortName", {}).get("value", "?"),
                            "artist": " ".join(artist.split())}
        json.dump(known, open(META, "w"), indent=1, ensure_ascii=False)
    return known

def download(title, info):
    """Fetch the original file once into tools/cache (afconvert reads Ogg, MP3, WAV and FLAC)."""
    os.makedirs(CACHE, exist_ok=True)
    url = info["url"].split("?", 1)[0]
    local = os.path.join(CACHE, re.sub(r"[^\w.-]+", "_", title))
    for attempt in range(8):
        if os.path.exists(local):
            return local
        r = subprocess.run(["curl", "-sS", "-L", "-m", "120", "-A", UA, "-D", "-", "-o", local + ".part", url],
                           capture_output=True, text=True)
        status = re.findall(r"^HTTP/\S+ (\d+)", r.stdout, re.M)
        if r.returncode == 0 and status and status[-1] == "200":
            os.rename(local + ".part", local)
            time.sleep(15)  # be gentle: Commons rate-limits bursts
            continue
        # Rate-limited (HTTP 429): wait as long as the server asks, then try again.
        wait_s = re.search(r"^retry-after:\s*(\d+)", r.stdout, re.I | re.M)
        wait_s = int(wait_s.group(1)) + 5 if wait_s else 60 * (attempt + 1)
        print(f"  rate-limited, waiting {wait_s}s", flush=True)
        time.sleep(wait_s)
    raise RuntimeError("Could not download " + url)

def decode(path):
    """Decode any audio file to mono 16-bit samples at 44.1 kHz."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    run("afconvert", path, wav, "-f", "WAVE", "-d", f"LEI16@{SR}", "-c", "1")
    with wave.open(wav) as w:
        data = array.array("h", w.readframes(w.getnframes()))
    os.remove(wav)
    return data

def loudest_part(s, max_sec):
    """Cut to the most energetic stretch (at most max_sec long) and drop quiet edges."""
    hop = SR // 100  # 10 ms frames
    energy = [sum(x * x for x in s[i:i + hop]) / hop for i in range(0, len(s) - hop, hop)] or [0]
    win = min(len(energy), int(max_sec * 100))
    total = sum(energy[:win]); best, start = total, 0
    for i in range(1, len(energy) - win + 1):
        total += energy[i + win - 1] - energy[i - 1]
        if total > best:
            best, start = total, i
    frames = energy[start:start + win]
    floor = max(frames) * 0.02
    first = next(i for i, e in enumerate(frames) if e > floor)
    last = len(frames) - 1 - next(i for i, e in enumerate(reversed(frames)) if e > floor)
    a = max(0, (start + first - 3) * hop)
    b = min(len(s), (start + last + 8) * hop)
    return s[a:b]

def polish(s):
    """Short fade in/out and normalise the peak so every animal is equally loud."""
    out = array.array("h", s)
    fin, fout = int(SR * 0.02), min(int(SR * 0.2), len(out) // 3)
    for i in range(min(fin, len(out))):
        out[i] = int(out[i] * i / fin)
    for i in range(fout):
        out[len(out) - 1 - i] = int(out[len(out) - 1 - i] * i / fout)
    peak = max(1, max(abs(x) for x in out))
    gain = 0.89 * 32767 / peak
    return array.array("h", (max(-32768, min(32767, int(x * gain))) for x in out))

def encode(samples, dest):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(samples.tobytes())
    run("afconvert", wav, dest, "-f", "m4af", "-d", "aac", "-b", "96000")
    os.remove(wav)

def build_sound(animal, dest, infos):
    credits, parts = [], array.array("h")
    gap = array.array("h", bytes(int(SR * 0.15) * 2))
    for title in animal["sound"]["files"]:
        info = infos[title]
        credits.append((title, info))
        clip = decode(download(title, info))
        if parts:
            parts.extend(gap)
        parts.extend(loudest_part(clip, animal["sound"]["max"]))
    if not os.path.exists(dest) or FORCE:
        encode(polish(loudest_part(parts, animal["sound"]["max"])), dest)
    return credits

def build_voice(text, dest):
    if os.path.exists(dest) and not FORCE:
        return
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
        aiff = tmp.name
    run("say", "-v", VOICE, "-r", RATE, "-o", aiff, text)
    run("afconvert", aiff, dest, "-f", "m4af", "-d", "aac", "-b", "64000")
    os.remove(aiff)

def main():
    content = json.load(open(os.path.join(ROOT, "content.json"), encoding="utf-8"))
    os.makedirs(os.path.join(ROOT, "sounds"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "voice"), exist_ok=True)

    lines = {f"praise_{i}": t for i, t in enumerate(content["praise"])}
    lines.update({f"end_{i}": t for i, t in enumerate(content["end"])})
    credits = []
    infos = {} if VOICE_ONLY else load_commons_info([t for sc in content["scenes"] for a in sc["animals"] for t in a["sound"]["files"]])
    for scene in content["scenes"]:
        lines[f"intro_{scene['id']}"] = scene["intro"]
        for a in scene["animals"]:
            lines[f"ask_{a['id']}"] = f"Hvor er {a['the']}?"
            lines[f"is_{a['id']}"] = f"Det er {a['the']}!"
            lines[f"line_{a['id']}"] = a["line"]
            if VOICE_ONLY:
                continue
            print("sound", a["id"], flush=True)
            for title, info in build_sound(a, os.path.join(ROOT, "sounds", a["id"] + ".m4a"), infos):
                credits.append((a, title, info))

    for key, text in lines.items():
        build_voice(text, os.path.join(ROOT, "voice", key + ".m4a"))
    print(f"voice lines: {len(lines)}")
    if VOICE_ONLY:
        return

    with open(os.path.join(ROOT, "CREDITS.md"), "w", encoding="utf-8") as f:
        f.write("# Lydkreditering / Sound credits\n\n"
                "Animal recordings come from Wikimedia Commons. They are trimmed and volume-normalised; "
                "the edited clips in `sounds/` are shared under the same licence as each original.\n"
                "Narration in `voice/` is generated with the macOS text-to-speech voice \"Nora\".\n\n"
                "| Animal | Recording | Author | Licence |\n|---|---|---|---|\n")
        for a, title, info in credits:
            f.write(f"| {a['e']} {a['the']} | [{title}]({info['page']}) | {info['artist']} | {info['license']} |\n")
    print("done")

if __name__ == "__main__":
    main()
