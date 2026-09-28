# Hvor er dyret? (Where's the Animal?)

A tap-to-find game in Norwegian (Bokmål) for 2–3-year-olds. The narrator asks "Hvor er kua?", the child taps the cow, and it jumps, sparkles and moos with a real recording. Then the narrator says "Kua sier mø!" and asks about the next animal. There are six places, and each round ends with a calm "Slutt" screen and "Snipp, snapp, snute, så er eventyret ute."

| Place | Animals |
| --- | --- |
| Gården 🐄 | ku, hest, gris, sau, hane, and |
| Skogen 🦉 | ugle, rev, frosk, gjøk |
| Hjemme 🐈 | katt, hund, fugl |
| Jungelen 🦁 | løve, elefant, ape, papegøye |
| Havet 🐋 | hval, delfin, pingvin |
| Fjellet 🐐 | ørn, geit, ulv, bjørn |

## Run it

```sh
cd ~/Desktop/games_farida
python3 -m http.server 8000
```

Open http://localhost:8000. It has to be served over http because opening the file directly won't load the sounds.

On an iPad or phone on the same Wi-Fi, open `http://<Mac IP>:8000`, where `ipconfig getifaddr en0` shows the IP. Then add it to the home screen: in Safari use Share → Add to Home Screen, and in Chrome on Android use ⋮ → Add to Home screen. Once it's hosted on HTTPS (for example GitHub Pages or Netlify), every sound is cached and it works fully offline.

## How it plays

- **No wrong answers.** Tapping a different animal plays its sound and says "Det er grisen!", then asks the question again.
- **Hints.** After 8 seconds the right animal wiggles and glows. After 16 seconds the question is asked again.
- **Grown-up controls.** 🏠 has to be held for about a second. 🔊 repeats the question. The optional name field makes the narrator add the child's name, for example "Hurra! Farida!". The name uses the device's own Norwegian voice (iPhone, iPad and Mac have one built in), and it's skipped on devices without one.

## Changing content

Everything is in **`content.json`**: text, places, where each animal stands (`x` and `y` are percentages of the screen, `s` is the size), and which Wikimedia Commons recording each animal uses. After editing it, rebuild the audio. This needs a Mac, and only records what is missing:

```sh
python3 tools/build_audio.py          # add --force to redo everything
```

The script:
- downloads each recording from Wikimedia Commons,
- trims it to the loudest 2–4 seconds and evens out the volume, and saves it as `sounds/<animal>.m4a`,
- records every narration line with the macOS Norwegian voice "Nora" into `voice/`,
- writes **CREDITS.md** with each recording's author and license.

After changing files, bump `VERSION` in `sw.js` so installed copies update.

## Licenses

The animal recordings are public domain, CC0, CC BY or CC BY-SA. Keep **CREDITS.md** with the app, and show those credits somewhere in a published version, for example on an "About" page for parents.

## Next steps toward the app stores

- Record the narration with a real person's voice by replacing the files in `voice/` (same file names).
- Use drawn artwork instead of emoji, so it looks the same on Android and iOS.
- Wrap it with Capacitor to make iOS and Android apps (needs Node.js).
# farida-games
