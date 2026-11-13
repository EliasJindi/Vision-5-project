# HANDOFF: Vision-5 (till nästa agent)

Skriven 2026-10-17 av föregående agent och uppdaterad samma dag efter mätserien (avsnitt 3, 4, 6, 7 och 10). Avsnitt 7 reviderades därefter efter en genomgång med Elias (ny ordning, ingen deadlinepress). **Uppdaterad 2026-10-27** efter fokustesterna 18 och 20/10 och filtertestet 27/10 (avsnitt 0, 5, 6, 7, 9, 10 och nytt avsnitt 11 med arbetsloggarna som PDF i `docs/`). **Uppdaterad 2026-10-29** efter varutesterna (kaffefilter, Coca-Cola med EAN-8): avsnitt 3, 6, 7, 10 och 11. **Uppdaterad 2026-11-03** efter att röstvägledningen byggts (PR #16): avsnitt 1, 3, 7, 9, 10 och 11. **Uppdaterad 2026-11-05** efter de första proven med röst på Pi:n och felsökningen av kameran (Y-adaptern var trasig), PR #19–#28: avsnitt 0, 1, 3, 5, 6, 7, 9, 10 och 11. **Uppdaterad 2026-11-07** efter 6–7/11: USB 3 (kontaktens riktning), kamerans vinkel, "Sakta närmare."/"Håll stilla.", verktygen i `tools/` och fokus på handen (`--hand`), PR #31–#37: avsnitt 0, 1, 3, 6, 7, 9, 10 och 11. **Uppdaterad 2026-11-09** efter 7–9/11: regel 3b (detektorn), "Redo" efter 8 s, ordning i repot, handmodellen (MediaPipe i två steg) i skannern och att rösten inte tystnar efter "Redo", PR #40–#55: avsnitt 0, 1, 6, 7, 9, 10 och 11. **Uppdaterad 2026-11-13** med examensarbetets datum (avsnitt 7, punkt 5) och idén om dialog med användaren (avsnitt 7, idéer som inte är byggda). **Uppdaterad 2026-11-13 kväll** efter 10–13/11 (PR #58–#67): ändring 40–44, knapparna (`tools/knappar.py`), provlyssning (`tools/lyssna.py`), avståndet, handmodellen i dagsljus mot kvällsljus, dialogidén och nätverket: avsnitt 0, 1, 6, 7, 9 och 10. Läs hela filen innan du gör något. Den beskriver vad projektet är, vad som är gjort, hur säkra vi är på varje resultat, vad som är på gång och **varför**. Filen innehåller medvetet inga rumsmått, koordinater, foton eller personnamn: repot är publikt.

---

## 0. Läs det här först: så arbetar du med Elias

- **Språk:** svenska. Ärlig, konkret feedback. Små tydliga delmål, ett steg i taget ("vi tar en sak i taget").
- **Visionen byggs hel.** Elias vill inte ha en nedskuren version. Idéer som parkeras ska skrivas ned, inte ignoreras.
- **Elias är student och kör testerna själv på en Raspberry Pi.** Du ser inte hårdvaran. Allt du vet kommer från det Elias klistrar in (terminalutskrifter, bilder). Be om utskrift, gissa inte.
- **Ingen kodändring utan att Elias bett om den.** Föreslå först. Elias har uttryckligen sagt: "nej gör inte nya ändringar" när jag ändrade oombedd. När Elias säger "ja gör så" till ett konkret förslag är det klartecken för just det. **Igen 5/11:** "vad har du ändrat, du har inte sagt om du får ändra heller", efter att egna tillägg (korgens regler, "Redo för nästa vara") byggts och mergats utan fråga. Arbetssätt sedan dess: lägg fram ett konkret förslag (gärna en tabell med före/nu), bygg och merga först när Elias säger "kör". Skilj i svaret på vad Elias bad om och vad du själv valt.
- **Elias idéer är värda att mäta (7/11).** "Man visar alltid produkter med handen" blev `--hand`, som gav ungefär tre gånger så många läsningar. Ta idén på allvar, bygg ett mätverktyg först (`tools/narmast.py`), sedan funktionen.
- **Slutsatser ska bygga på upprepade körningar (Elias 9/11):** "är du säker på att det är pga konsekventa saker? och inte enbart utifrån ett resultat". Gör positiva och negativa körningar separat (`tools/handmodell.py --namn …`), en fråga per körning, och säg uttryckligen vad som bygger på en enda körning. Elias vill ta det "en sak i taget", som numrerade steg.
- **Vid en dålig körning: titta på bilderna innan du gissar.** `python3 tools/mosaik.py NAMN` (eller `NAMN mitten`). 6/11 visade mosaikerna kameran mot taket, varan i bildens kant och motljus, inte fel i koden. Elias vill ha `sleep 15 &&` före körningar så att han hinner ställa sig (9/11: `sleep 5` räcker för korta mätningar). Sedan 9/11 kör han ofta från laptopen över SSH: i ett nytt fönster saknas `(venv)`, kör `source venv/bin/activate`.
- **Användarperspektivet först (Elias, 5/11):** "ingen användare kommer ha det så idealt som vi har det". Tester på stöd i perfekt läge visar bara bästa fall. Röstens kommandon ska vara **korta och enkla handgrepp** för någon som inte ser, avstånd i **armlängd**, inte centimeter.
- **Säg alltid vad du ändrat och varför**, och kommentera det i filhuvudet (de numrerade ändringslistorna i `barcode_scanner.py` är mönstret).
- **Vanliga misstag att undvika** (alla har hänt):
  - Att leta i koden när hårdvaran krånglar. 5/11 kraschade kameran i timmar; gammal och ny kod kraschade likadant, och felet var Y-adaptern. **Kör den gamla koden och läs `dmesg` först.** Anta inte vilken strömkälla eller uppställning Elias har: fråga.
  - Att dra slutsatser innan man mätt. Regel: **testa först, spekulera sedan.**
  - Att presentera beräknade siffror som mätta. Markera alltid: *uppmätt / beräknat / hypotes*.
  - Att ge råd som skapar ett nytt fel (jag föreslog att höja kameran med saker under, och det lutade uppställningen och förstörde flera körningar). Elias hittade felet själv.
  - Att påstå att något "bevisats" på tunt underlag.
  - Att tolka brus som mönster: under mätserien 17/10 drogs tre egna tolkningar tillbaka (se avsnitt 4). Dra inga slutsatser av en enstaka körning, och skriv uttryckligen *uppmätt / tolkning / hypotes*.
  - Mutationstest som lämnar en gammal förkompilerad fil kvar (9/11): blev den ändrade filen lika stor och återställdes samma sekund läste Python den gamla `.pyc`, och ett värde blev fel. Kör `python3 -B` med `PYTHONDONTWRITEBYTECODE=1` och rensa `__pycache__` efteråt.
  - Att köra nedladdad kod för att jämföra (9/11 stoppades det). Läs den och skriv av formlerna i stället.
  - Att tro att en inklistrad utskrift är den nya körningen. Elias klistrar ibland in den gamla. **Kontrollera loggnamnet (tiden) på raden `Loggar till logs/scan_…`** och be om den nya vid behov.
- **Ifrågasätt gärna (Elias 13/11):** "det är bra att du diskuterar med mig och vågar ifrågasätta". Säg när du inte håller med och varför, men bygg det Elias bestämmer.
- **Provlyssna innan fraser byggs in (13/11).** Det som ser bra ut i text kan låta fel med Piper: kolon ("Senast: Tomatpure.") och ensamma bokstäver ("S, senaste varan.") lät konstigt. `python3 tools/lyssna.py "fras"` spelar upp utan kameran. Skriv hela, vanliga meningar.
- **Kontrollera facit mot förpackningen (11/11).** Claude tog en streckkod ur en gammal körning som facit för ättikan, och den var en annan vara; alla "felläsningar" var rätta. Be Elias läsa siffrorna under koden.
- **Elias tar emot kodgranskning av andras kod** (ofta skriven av en annan AI-agent). Elias har gett tillåtelse att ändra kod om du tycker den är dålig, så länge du säger vad du ändrat och förklarar felet.
- **Måttband i tum.** Elias mäter i tum. Räkna om (tum × 2,54 = cm) i alla instruktioner.
- **Skriv inte i HANDOFF.md på eget initiativ** (Elias, 17/10). Uppdatera när Elias ber om det.
- **Arbetsloggar som PDF** efter testdagar ska läggas i `docs/rapporter/` och listas i avsnitt 11, **nyaste överst** (Elias, 27 och 29/10). Aldrig foton från rummet, koordinater eller butiksnamn i dem: repot är publikt.
- **Checklistor med numrerade steg (☐ 0, 1, 2 …)** fungerar bra för Elias när tester ska köras.

### Säkerhetsregler (hårda)
- **API-nycklar klistras aldrig in i chatten.** Nyckeln ligger i miljövariabeln `GEMINI_API_KEY` / `.env` på Pi:n.
- **`.env` committas aldrig.** Säkerhetskopian `ai_glasses_backup.tar.gz` innehåller `.env` och får inte delas.
- **Repot är publikt.** Lägg inte in rumskartan (`kartor/*.geojson`), foton, bilder från rummet eller loggar. De är ignorerade/hålls utanför.
- **Säkerhet (hinder, bilar, trappor) sköts alltid lokalt och snabbt**, aldrig av molnet eller en agent. Gemini får vara långsam och kan ha fel, därför får den inte avgöra "bil, 0,6 meter".
- Systemet får **aldrig säga "fri väg"** (det går inte att veta).

### Git-arbetssätt (Elias vill ha allt på `main`)
- Utveckla på grenen sessionen anger (3–5/11: `claude/tender-carson-khrm7l`; tidigare `claude/affectionate-pasteur-gero98`), pusha, skapa PR mot `main` och mergea. Elias har bett om detta: "varje gång vi ändrar så ska det finnas där på main".
- Efter att en PR är mergad: starta om grenen från `main` (samma namn):
  `git fetch origin main && git checkout -B <grenen> origin/main` (om en reset nekas: `git merge --ff-only origin/main`)
- `mcp__github__merge_pull_request` kräver **hela 40-tecken-SHA** i `expectedHeadSha` (`git rev-parse HEAD`).
- Commit-fot och PR-fot följer sessionens attributionsinstruktion.
- Ingen PR-mall finns i repot.
- Elias använder GitHub Desktop och Pi:n hämtar med `git pull`. Git på Pi:n har gått sönder två gånger av strömavbrott ("object file is empty"). Rutin: **alltid `sync` efter `git pull`.** Reparation: flytta `.git` åt sidan, `git init`, hämta från GitHub, `git reset`, `sync`.

---

## 1. Projektet

**Vision-5** är ett examensarbete (görs under en praktik): ett **bärbart navigeringshjälpmedel för synskadade** ("AI-glasögon") med att **handla mat självständigt** som scenario.

**Arkitektur:** lokala **reflexer** (säkerhet, snabbt, offline) + en **hjärna** i molnet (Gemini) för beskrivningar och reservlösningar.

**Hårdvara**
- Raspberry Pi 5, projektet ligger i `~/ai_glasses` med virtuell miljö (`source venv/bin/activate`).
- Luxonis OAK-D Lite (**DepthAI 2.29.0.0 på Pi:n**, kontrollerat 5/11; tidigare stod 2.33 här, det var fel), direkt i Pi:n (Y-adaptern var trasig, 5/11). **USB 3 (SUPER) sedan 6/11, men bara med USB-C-kontakten vid kameran åt ett visst håll** (märkt). Kontrollera med `python3 tools/usb_hastighet.py`. Med USB 2 kom bara hälften av bilderna fram och 4K kraschade. **Kontakten är känslig**: vrids kameran (på huvudet) kraschar den; avlasta sladden.
- Piper TTS (`sv_SE-alma-medium`) via `pw-play`; Logitech G435-headset med USB-dongel.
- Gemini 2.5 Flash (`google-genai`).
- Strömförsörjning: Baseus 65 W-powerbank (se avsnitt 5).

**Filer i repot (`main`)**

| Fil | Ansvar |
|---|---|
| `detect_spatial.py` | Huvudloop: YOLO + djup på kameran, akutlarm, Gemini-knapp |
| `audio_manager.py` | Prioritetskö för ljud (TTL per nivå, akutlarm avbryter, minst 0,7 s uppspelning först). `speak(wav=…, ttl=…)` spelar en färdig fil med egen bäst-före (pipet, 5/11) |
| `tts_engine.py` | Piper som en process (`--json-input`), WAV-cache i `cache/tts/`, låst till kärna 2–3. `--prewarm` genererar akutfraserna, vägledningens fasta fraser och bekräftelserna för varorna i `kartor/produkter.geojson`. **Kör den igen efter varje `git pull` som ändrar fraser och när kartan ändras** |
| `phrases.py` | Fraser och avståndsformat (stil G: "Bil, 0,6 meter."), och röstvägledningens fraser |
| `gemini_service.py` | Anrop till Gemini, timeout 10 s via `HttpOptions` (millisekunder) |
| `telemetry_logger.py`, `analyze_telemetry.py` | Spänning (`EXT5V_V`), `throttled`, temperatur, ljudkö; analys av latens m.m. |
| `measure_phrases.py` | Mätverktyg för fraslängd |
| `barcode_scanner.py` | **Rumstestet:** streckkod → karta → position. Se avsnitt 3–4 |
| `scan_filters.py` | Höjd- och djupfilter och modulantal (EAN-13/UPC-A 95, EAN-8 67). Bara standardbiblioteket, delas av skannern och analysen |
| `analyze_scans.py` | Utvärderar filtren på `logs/scan_*.jsonl`. `--pixlar`: säkra/osäkra läsningar per px/modul. `--lins`: linsläge vid säkra läsningar per avstånd. Går utan kameran |
| `hand_region.py` | **Fokus på handen** (7/11): det närmaste föremålet inom en armlängd i djupbilden, `HandFocus` (när kameran ska få ny lins/ljus) och `lens_for_distance` (linstabellen ur `--lins`). Ren numpy |
| `hand_model.py` | **Handmodellen** (9/11, ändring 38): MediaPipes handflatemodell (128×128) och landmärkesmodell (224×224) på kamerans processor. `HandModel.check()` ger landmärkesvärdet för handflatan i den blå rutan, `HandGate` regeln "bekräftad inom 2 s". Laddar aldrig ner något själv |
| `tools/` | Hjälpverktyg som överlever omstart: `usb_hastighet.py`, `sikte.py` (en bild till `logs/sikte.jpg`), `mosaik.py` (16 `--diag`-bilder från senaste körningen), `narmast.py` (ruta runt handen), `streckkod.py` (ser detektorn koden? zoom), `handmodell.py` (hittar handmodellen handen? laddar ner modellerna till `models/`, `--namn` per körning), `knappar.py` (knappar från laptopen via länken: upprepa, senaste varan, korgen, hjälp), `lyssna.py` (provlyssna fraser utan kameran). Körs från `~/ai_glasses` |
| `voice_guidance/` | **Röstvägledning** (3–5/11): `engine.py` (beslutslogik), `voice.py` (inkl. pip), `basket.py` (korgen), `catalog.py` (namn och `info`), `link.py` (JSON-länk för t.ex. C#), `session.py`, `replay.py`. Se `docs/ROSTVAGLEDNING.md` |
| `tests/` | 340 enhetstester (13/11; alla körs om zxing-cpp och OpenCV finns, annars hoppas skannertesterna över): `python3 -m unittest discover -s tests -t .` |
| `docs/` | `ROSTVAGLEDNING.md`. Arbetsloggarna (PDF) ligger i `docs/rapporter/`, se avsnitt 11 |
| `ej_anvant/` | Gammalt som inte används (t.ex. `test_cam.py`, en gammal kameratest). Mappen är i `.gitignore`: bilder och utskrifter som läggs där når aldrig GitHub |

**Inte i repot (finns bara på Pi:n):** `kartor/produkter.geojson` (13/11: två streckkoder, tomatpuré och linser på två platser; ättikan och den vita flaskan säger "Okänd vara." och ska inte läggas in nu, Elias 11/11), `kartor/mobler.geojson`, `.env`, `logs/`, `cache/`, Piper-modellen, `models/` (handmodellerna, i `.gitignore`).

---

## 2. Vad som gjordes 2026-10-10 (grunden)

Mycket gick åt till att göra systemet stabilt och snabbt.

- **Kodens läge:** Pi-koden fanns bara på SD-kortet. GitHub stod på juni. Allt lades upp och granskades. "Fixade" saker som agenten påstått fanns inte i filerna (spök-kod) och skrevs på riktigt.
- **Latens:** Piper startas inte längre per fras (0,85 s modelladdning). Den körs hela tiden, vanliga fraser ligger som WAV i cache. Från larm till ljudstart: ~1 ms vid cacheträff (var 4,2 s).
- **Pratighet:** bara det **närmaste** akutobjektet larmar, upprepning efter 4 s eller när objektet kommit 0,3 m närmare. 28 → 3 larm per 10 s i simulering.
- **Kortare fraser:** "Bil, 0,6 meter." 2,05 s mot 2,93 s (−30 %).
- **Gemini:** timeouten fungerade inte (en tråd-timeout avbryter inte anropet). Flyttad till HTTP-klienten. Navigeringsprompten svarar `INGET` i stället för "fri väg". 503/429 loggas ärligt.
- **Telemetri:** vitaldata varje sekund, `fsync` var 2:a sekund (en logg på 0 byte efter en krasch var anledningen).
- **Strömmen, rotorsak:** powerbanken förhandlar **3000 mA = 15 W**, Pi 5 vill ha 25 W. Det orsakade krascher. Piper är därför begränsad till 2 kärnor, och förgenereringen av fraser körs separat från kameran.

---

## 3. Rumstestet för butiksnavigering (2026-10-11 till 15)

**Idén:** produkter som landmärken. Läser man en känd vara vet man var man står. Butiker kan senare ge sin egen karta (hyllor, etiketter). Beviset görs först i ett rum, utan butikens tillstånd.

**Kartan:** QGIS, koordinatsystem **EPSG:3006** (meter), GeoJSON. Origo i ett rumshörn. Varje produkt har `ean`, `ligger_pa` och `facing` (+x, −x, +y, −y: åt vilket håll varan vänder sig). **Position = produktens position + avståndet d i `facing`-riktningen.** Geometrin är sanningen, inte attributen.

**Testprodukter**
- **Tomatpuré**, EAN `7340083497834`. Platt förpackning, kodens bredd 33 mm (1,30–1,31 tum), alltså ~0,35 mm per modul. `facing` ändrades till `-x` (bekräftat: skannern räknade ut rätt position).
- **Linser**, EAN `0783935132243` (UPC-A som skannern gör om till EAN-13 med inledande 0). Finns **medvetet på två ställen** för att testa tvetydighet. Skannern säger då "Tvetydigt: varan finns på 2 platser".

**QGIS-fällor:** sök bara på "3006" (ett tankstreck i "EPSG:3006 – SWEREF99 TM" bröt sökningen). Avbocka "Detektera fälttyper" vid CSV-import så att inledande nollor i EAN behålls. Exportera GeoJSON med RFC7946=NO så att koordinaterna stannar i EPSG:3006.

### `barcode_scanner.py`
Startade som ett utkast från en annan AI-agent. Granskad och rättad. Filhuvudet har numrerade ändringar 1–35 (20–27: filter och sammanfattning, PR #11; 28: EAN-8, PR #14; 29–31: röstvägledning, länk och tester, PR #16; 32: kartans `info` läses efter namnet, PR #21; 33: korgen skrivs ut vid avslut, PR #23; 34: `--fokusruta`, PR #26; **35: `--hand`, PR #35 och #37**). I korthet:
- Rättade krascher (`time.timedelta`, `msg.get` på en MessageGroup) och en begränsning av skanningstakten som bara gällde efter en träff (30 avkodningar/s = strömproblem).
- **Extended disparity** så att djup finns ner till ~0,20 m (annars ~0,35 m). **Reservruta** för djup runt kodens yta.
- `--diag`: sparar en bild varannan sekund i `logs/snapshots/` (max 60) med ljus- och skärpevärde, och grön ram runt funna koder.
- `--4k`: 3840×2160 @ 5 fps (1080p @ 15 fps är standard). Varnar om USB inte är USB3.
- **Ändring 13–17 (2026-10-15, PR #6 och #7):** alla avläsningar loggas (även okända och felläsningar); `--facit EAN` märker varje läsning rätt/fel och skriver `FELLÄSNING`; pixlar per modul (`px_per_modul`) mäts från kodens hörn; läget (`4k`/`1080p`) står i loggfilens namn; försöksräknare (träffprocent efter 10 s uppvärmning) i sammanfattningen vid Ctrl+C.
- **Ändring 18–19 (2026-10-17, PR #9):** linsposition (`lins`, 0–255), exponeringstid (`exp_us`) och ISO loggas per läsning och visas i `--diag`-raden; sammanfattningen jämför linsposition för alla bildrutor med de som hade rätt kod; **`--fokus N`** låser linsen manuellt (autofokus av). **Inte körd mot riktig kamera.** Skalan 0–255 är kamerans egen, inte centimeter.

**Loggformat** (`logs/scan_<datum>_<tid>_<4k|1080p>.jsonl`, en rad per avläsning, `fsync`): `t`, `mode`, `raw`, `ean`, `format`, `w_px`, `px_per_modul`, `rot_deg`, `hornen`, `bild`, `lins`, `exp_us`, `iso`, `in_map`, `depth_how`, `distance_m`, och om `--facit`: `facit`, `correct`; för varor i kartan även `namn`, `candidates` (positioner), `ambiguous`. Bara avkodade koder loggas. Bildrutor utan kod ger ingen rad.

Skannern är **fristående**. Kör den aldrig samtidigt som `detect_spatial.py`, och den varnar inte för hinder eller människor.

---

## 4. Mätresultat och hur säkra de är

Tomatpuré (kod 33 mm, ~0,35 mm per modul), köket i dagsljus, powerbank. Avstånd enligt kamerans djup. **Mätserie 2026-10-17 med `--facit`** (en PDF med alla 19 körningar gjordes för Elias, men ligger inte i repot). Siffror per körning: andel bildrutor med rätt kod efter 10 s uppvärmning.

### 4K (3840×2160)
| Djup | px/modul (uppmätt) | Rätt kod | Felläsningar | Kommentar |
|---|---|---|---|---|
| 0,50 m | 2,0 | 70 % | 8 av 79 | Rakt stöd |
| 0,54 m | 1,87 | 68 % | 0 av 64 | |
| 0,54–0,55 m | 1,86 | **77 %** | 0 av 17 | Bok som stöd, plant |
| 0,55 m | 1,84 | **2 %** | 0 | Samma avstånd som raden ovan, paketet verkade vridet |
| 0,57 m | 1,80 | 1 % | 0 | |
| 0,59 m | 1,75 | 1 % | 0 | Läsningar bara efter att paketet rörts |
| 0,60 m | 1,7 | 0 % | 1 av 1 | |
| 0,63 m | 1,63 | 1 % | 0 | |

Första körningarna (12:47 och 12:52) hade koden långt ner i bilden respektive en instabil hög under paketet: 2 % och 1 % (3 av 4 läsningar fel).

### 1080p
| Djup | px/modul | Rätt kod | Felläsningar | Kommentar |
|---|---|---|---|---|
| 0,21 m | 2,4–2,5 | 20 % | 2 av 19 | Läsningar bara under ~10 s efter en knuff, sedan inget (fokus landar fel) |
| 0,23 m | 2,22 | 0 % | 0 | Skärpa ~600, en läsning under fokussökning |
| 0,25 m | 2,05 | 12 % | 6 av 16 | Svart bok hållen bakom |
| 0,25–0,26 m | 1,95–2,05 | **0 %** | **30 av 30** | Svart bok stående bakom, läsningar efter knuff, alla fel |
| 0,28 m | 1,82 | 0 % | 1 av 1 | |

Från 15/10 (före `--facit`, mindre underlag): 4K stabilt på 0,38 m och 0,53 m, ibland 0,62 m. 1080p 0,21–0,22 m stabilt (62 läsningar), ~0,25 m med blandade rätt och fel.

### Säkerhetsklass för varje påstående
| Påstående | Status |
|---|---|
| Läsavstånden i tabellerna | **Uppmätta**, men nära gränsen är de **inte repeterbara** (samma avstånd gav 2 %, 68 % och 77 %) |
| px/modul är mätt (inte beräknad) och stämmer med teorin (2,0 / 1,87 / 1,63 i 4K, 2,22 i 1080p) | **Uppmätt** |
| 4K-gräns ≈ 1,85 px/modul, 1080p-gräns ≈ 2,2 px/modul | **Uppmätt tendens**, få körningar per nivå. Att 1080p kräver fler pixlar kan bero på nedskalning: **hypotes** |
| px/modul skiljer **inte** rätt från fel läsning (2,03 mot 2,02) | **Uppmätt** (samma kod, samma avstånd) |
| Felläsningar är **reproducerbara** (samma felaktiga koder dag efter dag, i båda lägena) | **Uppmätt** |
| Röstning över några sekunder hade fångat felen i 4K (71 rätt mot 8 fel) men inte i 1080p (30 av 30 fel) | **Uppmätt**, men bara en körning per fall |
| Läsningar kommer i bursts efter att paketet rörts, och fokus landar ofta fel nära | **Tolkning**, stöd i ~8 körningar. Skärpevärdet i `--diag` mäts över hela bilden och går inte att jämföra mellan uppställningar |
| Vinkel/vridning av paketet är den största okända variabeln | **Tolkning**, passar alla körningar men är inte mätt |
| Kodens position i bilden förklarar skillnaderna | **Stöds inte** (mellan 10 och 16 % under mitten avgör läget inget, bara längst ner var det dåligt) |
| Måttband mot djup: ~2 cm offset | **Ej visat.** Skillnaden växlade +0,7 till +3,1 cm utan mönster och ryms i hur kameran ställdes mot måttbandet. Använd djupet som avstånd |

### Tre tolkningar som drogs tillbaka under dagen (upprepa dem inte)
1. "4K är pålitligt upp till 0,54 m": gäller bara med rak uppställning.
2. "Träffarna följer skärpan" (ur fem körningar): motbevisades av en körning med skärpa ~1 250 och 77 % träffar.
3. "Gränsen är 1,8–1,85 px/modul i båda lägena": 1080p kräver ~2,2.

### Viktiga fynd
1. **Stabila felläsningar.** Tomatpurén (`7340083497834`) läses fel som samma fåtal koder: `6038721300844`, `4340413497834`, `7320023497834`, `7340023497832`, m.fl. Felkoderna har giltig kontrollsiffra. Exempel: `7320023497834` har två siffror fel (4→2 och 8→2) vars effekter på kontrollsumman tar ut varandra (−2 och −18, summan −20). **"Kräv 2–3 likadana läsningar" räcker därför inte**, och i 1080p på 0,25 m var den felaktiga koden i majoritet. Det som skyddar är kontroll mot en produktlista, en pixelgräns per läge och röstning tillsammans.
2. **Uppställningen avgör nära gränsen.** Plant stöd, paketet rakt mot kameran, inget lutande eller vridet, ingen instabil hög. Vinklar har inte mätts (använd mobilens vattenpass).
3. **Motljus och ljusmedelvärdet:** `--diag` visar ett medelvärde över hela bilden som kan visa 85 när koden är för mörk.
4. **Autofokus** behöver ~10 s, kan landa på bakgrunden och går inte att lita på på nära håll (~0,2 m). Det är därför `--fokus` och linspositionsloggen lades in.
5. **Att sikta** är ett verkligt problem för en blind användare. Det är designkrav.
6. **Strömmen på powerbank höll** hela dagen: `throttled=0x0`, 4,83 V i vila och 4,90–4,96 V under körning.

### Begränsningar upptäckta i `barcode_scanner.py` (testat med syntetiska koder)
- `px_per_modul` är rätt för rak och 90° roterad kod. Vid andra vinklar mäter zxing längs en rak skanrad, så värdet blir för högt med 1/cos(vinkeln) (+3,5 % vid 15°).
- **zxing ger en rak rektangel för streckkoder även när koden lutar åt sidan.** Lutning (perspektiv) går inte att läsa ur hörnpunkterna och måste mätas ur **djupet** (vänster mot höger sida). Inte gjort.
- `--facit` räknar **allt** som inte är facit som felläsning, även en riktig annan streckkod som råkar vara i bild (ha bara testobjektet i bild).
- Positionsberäkningen ignorerar **sidoavvikelse**: den antar att användaren står rakt framför varan. Upp till ~20 cm fel på 0,35 m om koden sitter i bildens kant.
- Stereodjupet är stabilt men hoppar i steg som växer med avståndet i kvadrat (uppskattningsvis ~1 cm per steg vid 0,6 m). Repeterbarhet är inte riktighet.
- Bara avkodade koder loggas. Bildrutor utan kod ger ingen rad; träffprocent räknas i terminalens sammanfattning (inte i loggen).

---

## 5. Strömmen

- Powerbanken ger 15 W. Pi 5 vill ha 25 W (och ger bara 600 mA till USB utan 5 A-strömförsörjning). Rumstestet fungerar ändå, men håll koll på `throttled` efter varje körning (`vcgencmd get_throttled`; `0x0` = ingen underspänning sedan start).
- **5/11: Y-adaptern var trasig.** Med den kraschade kameran efter 10–30 s (`error -71`, "Maybe the USB cable is bad?" i `dmesg`), även med nätadapter och gammal kod. Utan den, på nätadaptern: ingen krasch, 5,07–5,12 V, `throttled=0x0`. Kameran drar nu ström genom Pi:n, som har `usb_max_current_enable=1` (full USB-ström). **På powerbanken utan Y-adapter är det inte prövat.** Detaljer: `docs/rapporter/Vision5_rostvagledning_pa_pi_2026-11-05.pdf`.
- **Elias har beställt Waveshare UPS HAT (E) för Pi 5 (5 V/6 A, 30 W, pogo-pins under Pi:n), leverans 18–23/11 (5/11).** Batterierna (4 × 21700) ingår **inte** och ska köpas separat: skyddade celler av samma modell från ett känt märke, kontrollera celltypen i Waveshares wiki. Med kortet behövs ingen Y-adapter. Vikt ca 400 g med celler (beräknat): ryggsäck eller bälte, inte headset. Drifttid ca 4–5 h (beräknat, 10–15 W). Ett annat UPS-kort med bara 5 V/2,5 A (12,5 W) valdes bort: för svagt, powerbanken på 15 W har redan gett strömproblem.
  - **Tills dess:** nätadaptern, kameran direkt i Pi:n, utan Y-adapter. Powerbanken utan Y-adapter är inte prövad.
  - **När kortet kommit:** sätt i cellerna, kör skannern med `--vagledning tal` i 2 minuter, mät spänningen (`while true; do vcgencmd pmic_read_adc EXT5V_V; vcgencmd get_throttled; sleep 1; done`) och läs `dmesg`. Kontrollera `vcgencmd get_config usb_max_current_enable` (ska vara 1: Pi:n ser inte vad kortet klarar). Pi:ns hölje och kylare kan behöva bytas: kortet sitter under Pi:n. Kortet kan rapportera batterinivån via I2C (idé: rösten säger "batteriet är lågt"), inte byggt.
  - **Det är inte bevisat att kortet löser kamerakraschen**, bara att kameran är stabil utan Y-adaptern på nätadaptern.
- Tidigare plan: batterier/UPS HAT och en riktig strömförsörjning (officiella 27 W) efter lönen den 25:e. **Inte köpt 27/10, av ekonomiska skäl.** Powerbanken räcker för skannertesterna (`throttled=0x0` hela tiden). **Kontrollera vid valet** att USB-effekten räcker för kameran.
- Mätning är ogiltig om `throttled` ändras mellan körningar (Pi:n sänker då processorhastigheten, och det ser ut som att avståndet är problemet).

---

## 6. Läget just nu och vad som väntar på Pi:n

**Pi:n är på `main` med PR #11 (27/10).** Fokustestet är gjort (18 och 20/10) och filtren är testade på Pi:n (27/10). Detaljer och alla körningar i PDF:erna i `docs/rapporter/` (avsnitt 11). Det viktigaste:

| Fynd | Status |
|---|---|
| **Fokus, inte pixlar, stoppade läsningen på ~0,20 m.** Autofokus 0 %, rätt låst lins 100 %, i flera uppställningar | Uppmätt |
| **Autofokus fokuserar på bildens mitt.** Kod nära mitten: landar på 82–86 och läser 100 % (köket 20/10, rummet 27/10). Kod längst ner: landar på 58–72 (bakgrunden), 0 % | Uppmätt, båda riktningarna |
| **Ett fast linsvärde fungerar inte.** Fönstret flyttas med avstånd och vinkel: 0,20 m 77–92 (en uppställning), 0,31 m 69–84, 0,41 m 70–77. 77 låg vid kanten och gav 1 % 20/10 | Uppmätt |
| Fel fokus ger inga felläsningar, bara inga läsningar. Felläsningarna kommer av för få pixlar | Uppmätt |
| **Felaktigt djup (3–13 m)** kommer bara inom ~1,2 s från första läsningen, och bara med låst lins (läsning direkt vid start). 15 av 1 459 läsningar. Från både "mitten" (9) och "kodens yta" (6) | Uppmätt |
| **Höjdfiltret** (höjd/bredd < 15 %) stoppar 60 av 62 gamla felläsningar (30 av 32 utan 17/10 14:09), men **vid pixelgränsen är även rätta läsningar 1 px höga**: det kastade 33 av 35 rätta på 0,22 m / 2,29 px/modul. Höjden mäter osäkerhet, inte rätt/fel | Uppmätt |
| **Bara ~hälften av kamerans bilder når Pi:n:** 1080p 7,5 av 14,5/s, 4K 2,7 av 4,8/s. Färg + djup ≈ 590 / 570 Mbit/s mot USB2:s 480 | Uppmätt; USB2 som orsak är beräknad |
| **Uppställningen betydde mer än varan (29/10).** Kaffefiltret gav 22 felläsningar (`5317443006847`, 4 av dem 52–92 px höga som passerade höjdfiltret) när lådan lutade mycket på en instabil uppställning. Rak och stabil: 0 fel av 80 vid 2,55–2,85 px/modul. Lutning och instabilitet går inte att skilja åt; ~3° lutning gav inga fel. Koden såg hel ut | Uppmätt; orsaken är en tolkning |
| **Räckvidd i 4K, bästa fall (29/10):** Coca-Cola 33 cl (EAN-8, modul ~0,36 mm) felfri ned till 1,45 px/modul (0,71 m); tomatpuré ~2,0 (~0,5 m); kaffefiltret (modul ~0,29 mm) mest tunna läsningar under ~2,8 px/modul | Uppmätt |
| **Felband vid kanten (29/10):** Coca-Cola ~1,35 px/modul: 7 av 39 fel (`44036706`, siffra 1 och 7), alla 1–2 px höga och fångade av höjdfiltret. Felen sitter inte alltid i vänstra halvan | Uppmätt |
| Höjdfiltret räcker inte ensamt mot systematiska felkoder (höga felläsningar sågs i den dåliga uppställningen): produktlista och en **konfliktregel** (två olika koder på samma ställe inom några sekunder = osäkert) behövs | Konfliktregeln är ett förslag |
| **EAN-8 läses** (ändring 28): px/modul räknas med 67 moduler | Uppmätt på Pi:n |
| djup × px/modul ≈ 0,51–0,55 m (1080p) och ≈ 1,0 m (4K) för tomatpurén | Uppmätt, används i djupfiltret |

**Tre tolkningar som drogs tillbaka (upprepa dem inte):** "ett fast linsvärde ~77 räcker för armlängd", "filtret kastar bara ~10 % av rätta, det märks knappt" (gäller inte vid gränsen), "en lägre höjdgräns stoppar fel utan rätta" (rätta kan också vara 1 px).

**Röstvägledningen på Pi:n (4–5/11), uppmätt:**

| Fynd | Status |
|---|---|
| Rösten fungerar hela vägen: tips, "lite närmare"/riktning, namn med `info` och "Tillagd.", "Redo för nästa vara.". Första synliga kod till namn 3–5 s (tre körningar). Inget fel namn | Uppmätt |
| Replay 81 loggar: 0 fel vara, både med och utan tunna läsningar i konfliktregeln (43 mot 44 bekräftelser) | Uppmätt |
| **Kameran läser bara 1–7 % av bildrutorna när varan hålls i handen** (autofokus letade 0–95). Det kan ta en minut innan något läses | Uppmätt; orsaken är inte mätt (fokus, rörelse, ljuset vid 16-tiden) |
| Pipet hördes aldrig: tunna läsningar är för få (4 på 4 min) | Uppmätt |
| 4K gav 3,4 px/modul på 0,29 m, 1080p 3,6 på 0,27 m. 4K borde ge ungefär det dubbla | Uppmätt, inte förklarat |
| `--fokusruta` | Inte prövad på kameran |

**Kameran, siktet och handen (6–7/11), uppmätt.** Detaljer: `docs/rapporter/Vision5_handen_och_fokus_2026-11-07.pdf`.

| Fynd | Status |
|---|---|
| **USB 3 kräver att USB-C-kontakten vid kameran sitter åt ett visst håll.** Då 5,0 av 5 bilder/s i 4K (förut 2,7 av 4,8). "Hälften av bilderna" var USB 2 | Uppmätt |
| **Kamerans vinkel styr allt.** Med band pekade kameran för lågt eller mot taket, olika varje gång. En vara i ansiktshöjd hamnar ändå nära nederkanten (kameran sitter på pannan, ca 20° skillnad, beräknat). Hållaren behöver fast vinkel ca 20° nedåt | Uppmätt (mosaiker); vinkeln beräknad |
| Motljus (fönster bakom varan) gör koden mörk. Med fönstret bakom testaren: 11 % | Uppmätt |
| `--fokusruta` (mitten) gör det sämre när varan inte ligger i mitten | Uppmätt, en körning |
| **Alla säkra läsningar (1 614 från 50 körningar) vid linsläge 66–92.** Misslyckade körningar: linsen på 26–64 | Uppmätt (`analyze_scans.py --lins`) |
| **`--hand` (linsen efter handens avstånd): 13 och 15 % av bildrutorna med kod, utan: 4 och 4 %.** Linsen 73–76 med, 60–64 utan. Två rundor var, samma plats och ljus, en vara | Uppmätt |
| Regeln "närmast = handen" tar fel när ingen hand hålls fram (pappersrulle, kroppen). Hela bilden läses ändå, så ingen kod missas, men lins och ljus kan hamna fel en stund | Uppmätt |
| En enda läsning i stället för två hade gett **4 fel namn** i 88 loggar (två: 0) | Uppmätt (replay) |

**Detektorn, rösten och handmodellen (7–9/11).** Detaljer: `docs/rapporter/Vision5_handmodellen_2026-11-09.pdf`.

| Fynd | Status |
|---|---|
| Regel 3b: koden sedd men inte läst ger riktning eller "Håll stilla.". Detektorn såg koden i 20 av 93 bilder med hand, 24 ms | Uppmätt, en körning |
| Med kameran rätt vinklad och blundande: tomatpurén från första tips till namn på 12 s. Kameran för högt: varan i nederkanten | Uppmätt |
| **Handflatemodellen ensam räknade bordet med varor som hand i 16–55 %** och gav falsklarm i bakgrunden i alla körningar (upp till 0,87) | Uppmätt, fyra körningar |
| **Med landmärkesmodellen (hela bilden, inom 2 s): saltburk 83 %, ättiksflaska 83 %, bordet utan händer 0 % och 0 %** (landmärkesvärden högst 0,04) | Uppmätt, två körningar per fall |
| Handrutan blev kornig när den krymptes 3–5 gånger direkt ur 4K; förminskning med medelvärden först höjde saltburken från 53 till 83 % | Uppmätt (olika körningar) |
| I skannern: handen bekräftad i 72 % av bildrutorna med blå ruta, 121 ms per bildruta på Pi:n (ca 64 ms på kameran) | Uppmätt, ett rösttest |
| Ättiksflaskan gav 33 s tystnad efter "Redo": bara en läst kod startade en ny sökning. Ändrat (ändring 39), inte prövat på Pi:n | Uppmätt; ändringen otestad |
| Ättiksflaskan (liten kod, böjd, blank): 98 s till namnet, 15 läsningar avvisade som tunn remsa | Uppmätt |

**Avståndet, ljuset och rösten (10–13/11).** Detaljer 10–11/11: `docs/rapporter/Vision5_kvallsljus_2026-11-10.pdf` och `Vision5_avstandet_2026-11-11.pdf`. 13/11 finns bara här.

| Fynd | Status |
|---|---|
| **Avståndet avgör för en svår kod:** ättikan på stöd, 30 cm 97 och 95 % av bildrutorna godkända (2,56 px/modul), 40 cm 0 och 0 % (1,88). Felläsningar bara vid gränsen, alla stoppade av höjdfiltret | Uppmätt, två körningar per avstånd |
| "En halv armlängd" blev 0,38–0,46 m i handen. Med "armbågen mot kroppen" 0,28–0,38 m, och alla varor lästes (ändring 41) | Uppmätt, många körningar, en person |
| **Handmodellen beror på ljuset:** samma plats i köket, dagsljus 88 %, kväll med en taklampa (17,4 lux, mobilapp) 13 %. Mosaiken: händerna för mörka; handflatemodellen "såg" händer på paketet (96 %), landmärkesmodellen sa rätt nej | Uppmätt, en körning var; stämmer med 0–26 % 10/11 kväll och 50–95 % i dagsljus 11–13/11 |
| Med en genomskinlig flaska framför handen bekräftas handen sällan även i dagsljus (21–30 %); med händerna synliga vid ändarna 50–95 % | Uppmätt, NARA2 mot NARA4–5 |
| **Regel 4b ("Sakta närmare." efter avståndet, ändring 42) kom 4 av 4 gånger när handen var bekräftad, och varan kom närmare varje gång.** Kom inte när handmodellen inte såg handen eller handen var under 0,37 m | Uppmätt, NARA1–5 13/11 |
| Ättikan i dagsljus närmare: 10–27 s (98 s 9/11) | Uppmätt, flera körningar |
| "Håll stilla." följt 3–5 s senare av "Håll varan nära…" (NARA2, 3 gånger) → ändring 43 A. I NARA5 inte kvar | Uppmätt; efter ändringen en körning |
| "Sakta närmare." på 0,26–0,27 m och 3,0 px/modul (NARA4) → ändring 43 B ("Håll stilla."). NARA5: fyra "Håll stilla." på 14 s, tunna läsningar fortsatte; varken "närmare" eller "håll stilla" har visat sig bättre när bara en remsa av koden läses | En körning var |
| Ättikan liggande i handen: många tunna läsningar vid 2,6–3,0 px/modul (på stöd godkändes 95 % vid 2,56) | Uppmätt; orsaken (flaskans rundning) en hypotes |
| Gränsen 0,37 m i regel 4b är troligen för generös för ättikan: på 0,35–0,37 m lästes den sällan, säkert först på 0,28–0,31 m | Tolkning, flera körningar |
| En sedd kod efter en lång sökning gav 110 s tystnad (13/11 kväll) → ändring 44 (8 s, simulerat) | Uppmätt en gång; rättelsen inte prövad på Pi:n |
| **Knapparna** (H, S, K) nådde rösten via länken. Kolon och ensamma bokstäver lät konstigt; hela meningar lät "mycket bättre" (PR #66) | Uppmätt 13/11 kväll |

**Pi:n kan tappa wifi** (hände 27/10, `vision-pi1.local` gick inte att nå). Se avsnitt 9. **venv:** efter en omstart saknas `(venv)` i prompten och skannern säger `No module named 'cv2'`: kör `source venv/bin/activate`.

**Test i uppställning att använda:** **koden nära mitten av bilden** (annars fokuserar autofokus på bakgrunden), köket i dagsljus, fönstret bakom kameran, **bara testobjektet i bild**, kameran plant, paketet rakt upp på ett stabilt stöd med rak framsida mot kameran, **tejpmarkerad bas för paketet och kamerans fötter** så att uppställningen kan upprepas. Mät vinkeln med mobilens vattenpass. Skriv ner varje ändring (en sak i taget). Mät avstånd med djupet, inte måttbandet.

---

## 7. Det jag tänkte göra härnäst, och varför

**Tidsram (2026-10-17):** exjobbet börjar först nästa termin, så det finns ingen deadline att stressa mot. En person kommer då att hjälpa Elias med koden. Prioritera därför att det som byggs nu är **förstått, repeterbart och dokumenterat** framför att hinna med många funktioner. Ordningen nedan reviderades efter en genomgång samma dag: punkt 2 är ny, positionstestet är flyttat fram och vinkel och djupkontroll är sammanslagna i punkt 5. Kodändringar föreslås först och görs när Elias säger ja.

**Status 13/11: rösten guidar efter avståndet, och användaren kan fråga (PR #58–#67).** Ändring 40 ("Håll nästa vara framför dig." 5 s efter "Redo"), 41 (första tipset "Håll varan nära, armbågen mot kroppen."), 42 (regel 4b: "Sakta närmare." när den bekräftade handen är längre bort än 0,37 m), 43 (A: första tipset 8 s efter en kod; B: "Håll stilla." i stället för "närmare" inom 0,30 m), 44 (rättelse: 110 s tystnad), `tools/knappar.py` och `tools/lyssna.py`. Fynden i avsnitt 6. **Nästa steg, i ordning:**
1. **I dagsljus:** knapparna med två varor (K, S), och en lång sökning (koden bortvänd ca 60 s, sedan fram): nästa tips ska komma inom 8 s (ändring 44). `python3 tools/lyssna.py --knappar` provlyssnar utan kameran.
2. **Blundande prov** med de nya fraserna, tre varor, en körning per vara (`--diag` sparar bara 2 minuter).
3. **Headsetet:** vinkeln fem gånger (`clear && sleep 5 && python3 tools/sikte.py`, blundande, varan nära) och kamerans mått i tum. Läraren har tid om några veckor (13/11); Elias har ett band med en utskriven hållare tills dess.
4. **Butiksbesöket:** lux med mobilen (köket kväll 17,4; dagsljus inte mätt) avgör om handmodellen fungerar där. Hyllplan, testzon och 10–15 varor (se butikschecklistan i chatten 11/11).
5. Batterikortet 18–23/11.
6. **Väntar på beslut:** gränsen 0,37 m (ca 0,33 för ättikan?); tröghet vid 0,30 m om rösten växlar mellan "Håll stilla." och "Sakta närmare." igen (hände en gång); handmodellen i svagt ljus om butiken är mörk; dialogens steg 2–3; snabbare handmodell (oförändrat sedan 9/11); ska en sedd kod utan bekräftad hand hålla tipsen tillbaka (oförändrat).
7. **Examensarbetet:** titel och grupp till 8 januari (punkt 5 nedan). En grupp krävs; Elias vill helst inte ta in fler i idén (13/11).

**Status 9/11: handmodellen är inbyggd (PR #40–#55).** Regel 3b (detektorn), "Redo" efter 8 s, handmodellen (MediaPipe i två steg) styr när "kod sedd" ger röst, och en sedd kod i en bekräftad hand startar en ny sökning efter "Redo". Arbetslogg: `docs/rapporter/Vision5_handmodellen_2026-11-09.pdf`. **Nästa steg, i ordning:**
1. Rösttest med 3–4 varor i rad (kartan har 5), så att ändring 39 prövas på Pi:n.
2. **Väntar på Elias beslut:** en sedd kod utan bekräftad hand ska hålla tipsen tillbaka (i dag räknas den som "ingen kod", och "Håll varan framför dig…" hördes när varan hölls fram); snabbare handmodell (förminska 4K en gång per bildruta); frasen i stället för "en halv armlängd".
3. Butikstest när tillstånd finns: utan `--diag` (inga bilder sparas), helst med batterikortet (18–23/11). Förfrågningar om butikstest och examensarbete är skickade till flera dagligvaruföretag; fråga Elias om svar.
4. Hållare med fast vinkel ca 20° nedåt. Kameran pekade för högt i flera körningar även 7–9/11.
5. **Examensarbetet:** kandidatexamen i Informatik (GIK28T, 15 hp), vecka 13–22 våren 2027, på plats. Frågeställning: "Hur kan djupseende, streckkodsläsning och röstvägledning kombineras för att en person utan syn självständigt ska kunna identifiera varor vid matinköp?" Före kursstart: handledare, metod (design science föreslagen), litteraturstudie, forskningsetik och test med frivilliga blinda och gravt synskadade (Elias: "jag tänker inte blunda och låtsas som att det räcker").
   **Datum (kickoff 13/11, Högskolan Dalarna, "Thesis Spring 2027").** De första inlämningarna kommer före kursstart:

   | Datum | Vad | Att tänka på |
   |---|---|---|
   | 8 jan 2027 | Lämna in grupp och preliminär titel | Ensam eller i grupp? Frågan ställd 13/11, inte besvarad |
   | 29 jan | Lämna in projektidé | Frågeställningen finns redan |
   | 5 feb | Presentation av projektidén ("Are your project ideas feasible?") | Visa systemet och siffrorna, t.ex. ättikan 98 s → 10 s (arbetsloggen 11/11) |
   | 26 feb | Handledare och examinator fördelas; studenten kontaktar handledaren | Fråga direkt om GDPR (hälsouppgifter) och forskningsetik |
   | 29 mars | Kursstart | |
   | 31 mars | Lämna in projektbeskrivning | Två dagar efter kursstart: skriv den i mars |
   | 25 april | Lämna in utkast till rapporten | Testerna med användare behöver vara gjorda före |
   | 27–29 april | Halvtidspresentation (grupp, handledare, examinator) | |
   | 19 maj | Lämna in slutrapport, checklista och blankett för författarnas bidrag; handledningen slutar, examinatorn tar över | |
   | 23 maj | Lämna in oppositionsrapport | |
   | 25–27 maj | Slutseminarium och opposition | Återkoppling på rapporten 3 dagar efter seminariet |
   | 31 maj / 3 juni | Betygskommittén / återkoppling om betyg | |
   | 11 juni | Lämna in rättad slutrapport | |
   | 24 juni | Rapporter i DiVA, resultat i Ladok | |

   **Planering bakåt (förslag 13/11, inte beslutat):** testerna med blinda och gravt synskadade behöver vara klara i början av april. Rekrytering, samtycke och frågan om hälsouppgifter i februari–mars. **Elias planerar att göra testerna tillsammans med Synskadades Riksförbund** (13/11). Det tekniska (stabilt system, headset, butikskarta, ett första butikstest) helst före jul.

**Idéer som inte är byggda (samlade 9/11).** Finns sedan tidigare: Gemini hittar rätt vara bland liknande (punkt 6 under 7/11), Gemini som reserv när ingen kod syns, t.ex. "vänd paketet" (punkt 8 nedan), rösten guidar efter handen även utan kod ("Lyft varan lite."), hyllkantsetiketter, en AI-agent med verktyg, hållare med fast vinkel (CAD). Nya:
- **Zoom:** när detektorn ser en kod som inte går att läsa skärs den ut, förstoras 2 gånger och läses igen. Räddade 2 av 14 bilder i en mätning (`tools/streckkod.py`); vilka koder som lästes är inte kontrollerat (felläsningar?). Inte inbyggt.
- **Bara läsa koder på varan i handen.** I en butik är hyllan full av koder, och skannern läser i dag hela bilden. Med handmodellen går det att kräva att koden ligger i den bekräftade handens ruta innan namnet sägs. Viktigt före butikstest.
- **Pilot i en mindre lokal butik** där Elias känner personalen: lättare att få ja, och något att visa de stora kedjorna. Fråga den som bestämmer, och fråga handledaren om tester före kursstart får räknas.
- **Dialog med användaren: en smartare röst som man kan svara (Elias 13/11).** Elias: "vi bygger det åt de som behöver det, inte oss själva". Användaren ska kunna svara och fråga, med laptopen som knappar tills vidare. Elias exempel: rösten säger "närmare" fast varan redan är nära, och användaren svarar "jag har den nära, ska jag vända den?". Elias vill börja tänka på det nu, före januari, så att det blir bra för användaren; kärnan ska ändå vara stabil först. Diskussionen 13/11, det Claude invände och föreslog:
  - **Vägledningen ska ligga kvar som lokala regler.** Motorn beslutar 2 gånger per sekund; en AI i molnet tar 1–3 s och kräver nät. Agenten ligger *ovanpå* reglerna: den pratar och kan byta strategi, men styr inte varje rörelse.
  - **Det kameran redan mäter behöver ingen dialog.** Exemplet ovan löser ändring 43 B med avståndet. Dialogen gör mest nytta för det kameran inte vet: "Vad håller jag i?", "Upprepa", "Vad har jag i korgen?", "Var hittar jag kaffet?", "Läs innehållet" (allergier).
  - **Knappar före röst.** Knappar fungerar i en bullrig butik och ingen annan hör frågan. Taligenkänning på Pi:n är tung; i molnet kräver den nät.
  - **Regler som gäller även här:** säkerhet aldrig via agenten, och ett varunamn sägs bara när streckkoden bekräftat det (en AI kan hitta på). Nät är ofta dåligt inne i butiker; varje fråga kostar; bilder till molnet kan visa andra kunder.
  - **Förslag i tre steg (inte beslutat i detalj):** 1. Knappar från laptopen utan AI: "Upprepa", "Vad var det senaste?", "Vad har jag i korgen?". 2. Användaren byter strategi med en knapp ("jag har den nära" → tipsen om att vrida och vända). 3. En agent för fria frågor via länken (`--lank`, som byggdes för just ett sådant program) och Gemini (`gemini_service.py`).
  - **Mät först:** fråga några personer (förbundet) vad de vill kunna fråga, och om de föredrar knappar eller röst. Rita interaktionen på papper (knappar, vad var och en gör, vad rösten svarar).
  - **Steg 1 byggt 13/11 (Elias: "kör steg 1"): `tools/knappar.py`.** Prövat på Pi:n 13/11 kväll: H, S och K nådde rösten. Svaren ändrades efter provlyssning till hela meningar ("Senaste varan var Tomatpure, 500 gram.", "Du har två varor i korgen, Tomatpure och Linser.", "Mellanslag, hör igen. Ess, senaste varan. Kå, korgen. Hå, hjälp."). Mellanslag upprepar senaste beskedet, S senaste varan, K korgen, H hjälpen, Q avslutar. Lyssnar på länken och svarar med `say`; skannern är oförändrad. Starta skannern med `--lank 5555` och knapparna i en andra terminal, innan varor läggs i korgen (annars saknas de i korgen). Fraserna genereras första gången de sägs (ca 0,5 s).
  - **AI-modellen i molnet, programmet på Pi:n** (Elias frågade 13/11 varför inte allt i molnet): AI:n (Gemini) körs i molnet i steg 3 och belastar inte Pi:n. Det som avråds från är en egen server i molnet: länken lyssnar bara på Pi:n själv av säkerhetsskäl, och fler delar kan gå sönder.
  - **Tankar om steg 3, den smartare AI:n (13/11, inte beslutat):** ett eget program (som knapparna) på länken som anropar Gemini med verktyg: korgen, senaste varan, kartan, `say`. Fråga med en tryck-och-prata-knapp; Gemini kan troligen ta emot ljudet direkt, så ingen separat taligenkänning behövs (kontrollera). Skicka bara den blå rutan runt handen, aldrig hela bilden (andra kunder), och bara när användaren frågar. Svar som inte bygger på en läst streckkod sägs som osäkra ("Det ser ut som… men koden är inte läst"); allergener och innehåll med en uppmaning att dubbelkolla. Utan nät: "Jag har ingen kontakt med nätet just nu.", knapparna och vägledningen fungerar ändå. Strategibyte ("jag har den nära") kräver ett nytt kommando i länken (protokoll 2). Mät först: fråga användare vad de vill fråga, och prova med inspelade frågor på laptopen (svarstid, rätt svar) innan Pi:n.
  - **Inget molnkonto behövs för att börja** (Claudes bedömning 13/11): steg 1–2 går att bygga och testa med låtsade händelser utan Pi:n, och programmet körs sedan bredvid skannern på Pi:n eller laptopen. En egen server i molnet ger kostnad, nycklar att skydda och bilder som lämnar huset.

**Status 7/11: fokus på handen fungerar (PR #31–#37).** `--hand` ställer linsen efter handens avstånd och gav ungefär tre gånger så många läsningar. Arbetslogg: `docs/rapporter/Vision5_handen_och_fokus_2026-11-07.pdf`. **Nästa steg, i ordning:**
1. Fler rundor med och utan `--hand`, fler varor (burk, blank påse, liten kod), blundande test. Kör alltid `python3 tools/usb_hastighet.py` först.
2. ~~**Handmodell** som bekräftar att det närmaste är en hand~~ Gjort 9/11 (ändring 38, se status 9/11). Att rösten guidar efter handen även utan kod ("Lyft varan lite.") är inte byggt.
3. Hållare med fast vinkel ca 20° nedåt (CAD-fil), vinklad USB 3-sladd. Batterikortet kommer 18–23/11 (avsnitt 5).
4. **Väntar på Elias beslut:** ny fras i stället för "en halv armlängd" (förslag: "Böj armen och håll varan framför dig."). **Avgjort 7/11:** `--hand` är standard (ändring 36, `--utan-hand` stänger av); tipsen efter "Håll stilla." behåller sin takt (efter 8 s har användaren ändå rört sig); två läsningar krävs (en gav 4 fel namn); "Finns redan i korgen." vid återvisning är rätt (Elias testade det med flit).
5. Butikstester när ICA ger tillstånd.
6. **Idé (Elias 7/11): Gemini hjälper till att hitta rätt vara bland liknande.** Står flera liknande varor bredvid varandra (t.ex. godispåsar) tar Gemini reda på hur den sökta förpackningen ser ut (färg, form, logga, text) och skickar beskrivningen till Pi:n. Då vet kameran vad den letar efter och rösten kan guida till rätt påse innan streckkoden syns. Inte byggd. Att avgöra: var beskrivningen kommer ifrån (Gemini utifrån namnet, eller en bild/färg per vara i kartan i förväg); om Pi:n letar själv (färg i bilden, snabbt och lokalt) eller om Gemini jämför påsarna i bilden (långsammare men säkrare). **Streckkoden bekräftar alltid till sist:** två påsar kan ha nästan samma färg. Gemini guidar bara mot varan, aldrig säkerheten.

**Status 5/11: röstvägledningen är körd och fungerar på Pi:n (PR #19–#28).** Vad som ändrats, vad som är uppmätt och vad som är osäkert: `docs/rapporter/Vision5_rostvagledning_pa_pi_2026-11-05.pdf`. **Nästa steg, i ordning:**
1. Kameran utan Y-adapter, nätadaptern, bra ljus. `git pull && sync`, `python3 tts_engine.py --prewarm`.
2. `lsusb -t` med kameran i en blå port: USB3 utan Y-adaptern?
3. A/B 60 s utan och med `--fokusruta` (samma ljus och avstånd), jämför andelen bildrutor med kod. Läsfrekvensen (1–7 %) är det största problemet nu.
4. Blundande test: fem försök från bortvänd kod, tid till "Tillagd.".
5. 1080p mot 4K på samma avstånd (px/modul ser fel ut).
6. **Förslag som väntar på Elias beslut:** avståndsvägledning med djupkameran ("Närmare"/"Längre bort" även utan kod), "Bra, håll stilla." när koden skymtar, OpenCV-detektorn för pip och riktning (B, mät först), CAD-fil till ett 3D-utskrivet headset. **Avböjt:** låst fokus som standard (användaren kan hålla varan på helt andra avstånd) och kvartsvarv i tipsen.
7. Butikstester när ICA ger tillstånd.

**Status 3/11: röstvägledningen är byggd (PR #16) men inte körd på Pi:n.** Paketet `voice_guidance/`, `--vagledning text|tal`, `--sikte huvud|hand`, `--lank PORT` och 99 enhetstester. Regler, protokoll och kända begränsningar: `docs/ROSTVAGLEDNING.md`. Arbetslogg: `docs/rapporter/Vision5_rostvagledning_2026-11-03.pdf`. **Nästa steg, i ordning:**
1. **`python3 -m voice_guidance.replay logs/scan_*.jsonl --karta kartor/produkter.geojson`** på Pi:n. Visar vad motorn hade sagt under alla gamla körningar och **hur ofta den hade sagt fel vara** (ska vara 0, annars justeras reglerna innan något testas med röst). Skicka utskriften till Claude.
2. `python3 tts_engine.py --prewarm` (utan kameran igång), sedan `--vagledning text` och sist `--vagledning tal`. Lyssna om beskeden stämmer med det som händer.
3. **Justera trösklarna** (`GuidanceConfig`), särskilt `conflict_radius` (0,10, gissad: grannvaror på en hylla kan räknas som konflikt) och riktningskonventionen.
4. **Test med ögonbindel**: den enda sanna testen av om vägledningen fungerar för någon som inte ser. Alla resultat hittills gäller bästa fall (kameran rätt riktad).
5. Fokuslås (B1), fokusområde på koden (B2), pip, burk och blank påse, USB3-test.

**Arkitekturbeslut 3/11 (Elias): "mellanvägen".** Python äger kameran, avkodningen och filtren (uppmätta med zxing-cpp, en annan avkodare ger andra gränser) och allt som rör säkerhet. Applikationslogiken (vad som sägs och när) kan senare flyttas till C# via länken (`--lank`, JSON-rader på localhost), eftersom den senior konsult som hjälper Elias i exjobbet kan C# bäst. Pythons `GuidanceEngine`, `tests/test_engine.py` och `replay.py` är då specifikationen. Ingen omskrivning görs nu. **Skriv inte om det uppmätta i C#.**

**Status 29/10:** varutester gjorda för tomatpuré, kaffefilter och Coca-Cola (EAN-8) i 4K, se avsnitt 6 och de två PDF:erna från 29/10. Del 2 rättar flera slutsatser från del 1. EAN-8 inlagt (PR #14). Röstvägledningen föreslogs här och byggdes 3/11 (se ovan). Resultaten gäller bästa fall (kameran rätt riktad).

**Status 27/10:** punkt 1 (fokustestet) är gjord. Del A av kodförslaget (`docs/rapporter/Vision5_forslag_kodandring_2026-10-20.pdf`) är genomförd i PR #11: höjd- och djupfilter som loggas och avvisar med `--filter`, `scan_filters.py`, `analyze_scans.py`. Ändrat efter granskning: vid orimligt eller saknat djup sägs varan utan position. Punkt 2–5 nedan är inte påbörjade. **Ny ordning härifrån:**
1. **Beslut: ska en tunn läsning ge "lite närmare" i stället för tystnad?** *Varför:* höjdfiltret stoppar allt nära pixelgränsen, även rätta läsningar. Som signal behålls säkerheten utan att räckvidden går förlorad, och det är första biten av röstvägledningen. Förslag, inte beslutat.
2. **Testa en vara med kort streckkod.** *Varför:* hela men korta koder (höjd/bredd ~0,1) avvisas av höjdfiltret. Inte testat.
3. **Fokuslås vid träff (B1 i kodförslaget).** Lås på medianen av några läsningar, släpp efter ~1,5 s utan träff, och låt aldrig låset ligga kvar (hinderdetekteringen behöver fokus långt bort). *Varför:* fönstret flyttas med avstånd och vinkel.
4. **Fokusområde på koden (B2).** Testa först på sparade bilder: OpenCV:s BarcodeDetector på suddiga koder, eller fokus på närmaste föremålet i djupbilden. *Varför:* autofokus fokuserar på bildens mitt.
5. **USB3-test** (blå port, utan Y-adapter) när strömförsörjningen finns. *Varför:* bara hälften av bilderna når Pi:n.
6. Positionstestet, röstvägledning, knappskanning och spaningsbesök i butik (kontakt tagen med en mindre ICA-butik, väntar på svar), som nedan.

**Ursprunglig lista (17/10)**, i ordning:

1. **Fokustestet** (avsnitt 6) och **`lsusb -t` utan Y-adaptern.** *Varför:* läsningar kom gång på gång bara medan autofokus sökte, och i 1080p nära (≤0,23 m) räckte pixlarna men inget lästes när fokus hade landat. Avgör om fokus är begränsningen, och vad knappskanningen ska göra (t.ex. sätta fokus för nära håll vid tryck). USB-kontrollen hör hit eftersom strömmande 4K i 5 fps (≈500 Mbit/s) inte ryms på USB2 (480 Mbit/s), **beräknat**. **Rättelse (20/10):** att skannern bara avkodar ~2 bilder/s i 4K bevisar ingenting om USB, det är skannerns egen gräns (`UHD_SCAN_INTERVAL_S` = 0,5 s). Mät i stället hur många bildrutor kameran levererar: sammanfattningen visar det från ändring 27.
2. **Repeterbar testrigg och offline-replay** (ny). Utskrivna streckkoder i kända storlekar på en plan, stadig skiva med tejpad fixtur, som ersätter paketet vid gränsmätningar. Spara även det beskurna kodområdet **förlustfritt (PNG)**, inte JPEG, så att olika avkodare, uppskalning och kamerans sharpness/denoise kan jämföras mot samma bilder utan Pi:n. *Varför:* samma avstånd gav 2 %, 68 % och 77 % beroende på uppställningen, så varje manuell körning mäter mest uppställningen. Replay skiljer optik från avkodare och testar nedskalningshypotesen (avsnitt 4) direkt. Bilderna hålls utanför git (repot är publikt). Kräver ändring i `barcode_scanner.py`: föreslå först.
3. **Positionstestet** (flyttat fram från punkt 5). Lägg om tejpkorsen (de gamla låg 0,6–1,0 m från varan, för långt för att läsa koden) på ~0,35 m och kör 4K. *Varför:* mäter hela kedjan karta → kod → position, och i 4K lästes koden på 0,38 m och 0,53 m i varje bildruta (15/10), så testet behöver inte vänta på gränsfallen. Räkna med att sidoavvikelse är största felkällan. Den går att räkna ut ur kodens pixelposition (föreslå först).
4. **Säkerhetslager för felläsningar.** *Varför:* felen är systematiska och reproducerbara, och px/modul kan inte flagga en enskild läsning. Kombinera (a) en pixelgräns **per läge** (4K ~1,85, 1080p ~2,2, ska valideras på nya körningar), (b) röstning över några sekunder (fungerade i 4K, inte i 1080p) och (c) kontroll mot butikens produktlista. Gemini kan dubbelkolla vid osäkerhet. Räkna inte med att tröskeln ensam räcker.
   - Felkoderna ligger 1–3 siffror från rätt kod. Närliggande koder hos samma tillverkare kan vara riktiga produkter, så en produktlista skyddar troligen mindre än man tror (**resonemang, inte mätt**). Särskilt viktigt för allergener.
   - Ett förslag Elias har sett men inte beslutat: logga skärpa i just kodens ruta. Det flaggar inte enskilda fel (rätt och fel kom i samma bildruta), men förklarar träffprocent mellan uppställningar.
5. **Mät vinkeln och kontrollera djupet mot måttband.** Mobilens vattenpass vid varje körning, och längre fram lutning ur djupet (vänster mot höger sida av koden). Djupet mot måttband på 0,3 / 0,5 / 1,0 / 1,5 m. *Varför:* vinkel/vridning är den enda variabel som passar alla körningar, och den är inte mätt. Stereofelet växer med avståndet i kvadrat, och skillnaden mot måttbandet växlade +0,7 till +3,1 cm utan mönster. Djupet skrivs bara ut när en kod läses, så avstånd bortom läsgränsen kräver en större testkod.
6. **Röstvägledning för siktet** (Elias vill fundera extra på den, och tycker den är en bra funktion). **Byggd 3/11, se status överst i avsnittet.** Designen nedan är den ursprungliga: den byggda versionen ligger i `docs/ROSTVAGLEDNING.md`. *Varför:* löser sikteproblemet, som är designkrav för blinda användare.
7. **Knappskanning** (USB-knapp via `evdev`, systemd): kameran sitter på pannband och följer huvudet. Skanna några sekunder vid tryck. *Varför:* mindre ström, inga oönskade avläsningar, passar att användaren "tittar" på varan.
8. **Gemini som reserv** när ingen kod syns eller den är osäker (produktigenkänning, "koden sitter på baksidan, vänd paketet"). *Varför:* skalar till hundratals produkter utan att träna egna modeller.
9. **Hyllkantsetiketter**, **integration** med `detect_spatial.py` (en kamera, säkerhetslarmen först, position på nivå 3 i ljudkön), eventuell **AI-agent** med verktyg (`ta_bild`, `läs_streckkod`, `slå_upp_i_kartan`, `säg`; aldrig säkerhet), sist en **genomgång** för att göra allt så robust som möjligt.

### Röstvägledning: designen vi landade i (inte implementerad)
Siktet kräver snabb återkoppling (5–10 gånger per sekund), så **det får inte gå via Gemini/Claude** (1–3 s, kräver nät, kostar). Allt som behövs finns lokalt:

| Användaren behöver veta | Hur det mäts lokalt | Säger |
|---|---|---|
| Var är koden? | Leta kodområde utan att avkoda (t.ex. OpenCV:s streckkodsdetektor) | "vänster", "upp" |
| Är den nära nog? | Pixlar per modul | "närmare" |
| Lutar den? | **Djupet** vänster mot höger | "vrid varan" |
| Allt rätt? | Kod läst och tillräckligt många px/modul | pip + varans namn |

- **Ton** medan man siktar (som parkeringssensor), **korta ord** för besked, genererade i förväg med Piper så att de ligger i cachen.
- Bestäm **en** konvention för riktning ("vrid huvudet" eller "flytta handen", inte båda).
- Under ~0,20 m finns inget djup: säg "lite längre bort".
- Regeln "vrid eller gå närmare": jämför kodens uppmätta bredd i pixlar med förväntad bredd från djupet. Mycket smalare än väntat = lutning. Ungefär som väntat = för långt bort.
- Gemini bara när ingen kod syns eller koden är osäker. **Gratisalternativ:** Geminis gratisnivå räcker troligen eftersom molnet bara behövs ibland (kontrollera villkoren: data i gratisnivån kan användas av Google, viktigt om bilder visar andra personer). Inget gratis alternativ är lika bra för bilder. Lokala bildmodeller (Moondream, SmolVLM) är för långsamma på en Pi 5 (tiotals sekunder per bild).

### Idéer som parkerats (kasta inte bort dem)
- **Relaterat arbete: OrCam MyEye** (Elias hittade den 5/11). Liten kamera på glasögonbågen som läser text, känner igen ansikten och sedlar och identifierar produkter via streckkod, utan telefon. Uppgifterna är från Claudes minne och ska kontrolleras mot tillverkaren. Det som verkar skilja Vision-5 åt: **position i butiken** (varor som landmärken) och **vägledning för att få koden läst**. Ta med som relaterat arbete i uppsatsen, jämför hellre än att konkurrera. Påstå inte att MyEye inte fungerar i butik.
- **Begränsad autofokus i stället för låst:** `setAutoFocusLensRange` och `setAutoFocusRegion`, ihop med `setAutoExposureRegion` (löser motljuset). **Inte testat på OAK-D Lite.** Kameran delas med hinderdetekteringen: ändra tillfälligt vid knapptryck och återställ, annars kan YOLO tappa hinder. Fokus-/exponeringsområdet bör sättas på den funna koden, inte bara på bildens mitt.
- **4K-stillbild vid knapptryck** i stället för strömmande 4K: strömmande 4K ryms inte på USB2 (5 fps ≈ 500 Mbit/s mot 480). Måste testas (ström, värme, YOLO samtidigt).
- **Mät ljuset mitt i bilden** i `--diag` i stället för över hela bilden.
- **Hyllkantsetiketter:** läsbara på längre håll än streckkoder (text ~5 mm, pris ~20 mm), sitter fast och är bättre landmärken än produkter. Layout och storlek varierar mellan butiker, så **bygg på gränser i pixlar, inte meter**. Elektroniska etiketter har lägre kontrast och reflexer. Låt Gemini läsa dem först.
- **Butikens etikettsystem** (t.ex. Pricer): butikens system vet redan vad varje etikett visar, och ofta en LED som kan blinka (syns på flera meter). Kräver avtal och officiellt API, **aldrig avlyssning**. Inom exjobbet: simulera med en låtsasdatabas och en låtsas-LED.
- **Stor streckkod och låtsasetikett i testet** (mät kodens bredd, visar att läsavståndet växer med kodstorleken).
- **Spana in butiker:** typ av etikett, storlek, ljus, gångar. Fråga om tillstånd för tester och foto. Fota aldrig kunder. Elias har sagt att han ska göra detta.

---

## 8. Äldre backlog (från 10 oktober)
- Fladder mellan "bil" och "lastbil" i detektionen.
- Mäta hur lång tid `pw-play` tar att starta (krav NFR-01).
- Test utan nät (offline).
- Kalibrera om ROI i djupmätningen i `detect_spatial.py`.
- Kontakta en person om kamerafästet.
- Kolla om GitHub Desktop har opushade commits.
- `lsusb -t` utan Y-adaptern (får vi USB3?).
- Ladda ner `logs/` från Pi:n som underlag till rapporten.

---

## 9. Bra att ha: kommandon

```bash
# På Pi:n
cd ~/ai_glasses && git pull && sync && source venv/bin/activate
python3 barcode_scanner.py --diag --4k --facit 7340083497834   # utan --4k för 1080p
python3 barcode_scanner.py --diag --facit 7340083497834 --fokus 85    # låst lins (N 0-255, ta fram värdet med lins-raderna)
python3 barcode_scanner.py --diag --facit 7340083497834 --filter      # filtren avvisar (utan --filter loggas de bara)
python3 analyze_scans.py                                        # höjdregler och orimligt djup i alla loggar (går utan kameran)
python3 analyze_scans.py logs/scan_20261027_*.jsonl --utan 140916   # vissa loggar, utan en körning
python3 -m unittest discover -s tests -t .                      # enhetstesterna (~100, ~2 s)
python3 -m voice_guidance.replay logs/scan_*.jsonl --karta kartor/produkter.geojson   # vad hade vägledningen sagt? Felkod 1 om någon bekräftelse var fel
python3 barcode_scanner.py --diag --4k --facit <EAN> --vagledning text   # röstvägledning, bara utskrift
python3 barcode_scanner.py --diag --4k --facit <EAN> --vagledning tal --sikte huvud   # med röst (kör tts_engine.py --prewarm först)
python3 tools/usb_hastighet.py                                  # USB 3 (SUPER)? Annars vänd USB-C-kontakten vid kameran
clear && sleep 15 && python3 barcode_scanner.py --4k --vagledning tal --sikte hand --filter --diag   # handläget är standard (--utan-hand stänger av)
python3 tools/mosaik.py NAMN                                    # vad såg kameran? (NAMN mitten, NAMN 12:11:50 12:12:30)
python3 tools/mosaik.py NAMN --senaste 4                        # en mosaik per körning (bilderna sparas per körning sedan 7/11)
python3 tools/narmast.py --4k                                   # hittar den handen? 8 bilder till logs/narmast.jpg
python3 tools/sikte.py                                          # en bild till logs/sikte.jpg: varan ska vara mitt i bild
python3 analyze_scans.py --pixlar                               # säkra/osäkra läsningar per px/modul
python3 analyze_scans.py --lins                                 # linsläge vid säkra läsningar per avstånd (linstabellen)
dmesg | tail -30                                                # USB-fel vid kamerakrasch (error -71 = koppling/sladd)
echo 'cd ~/ai_glasses && source venv/bin/activate' >> ~/.bashrc   # venv aktiveras automatiskt i nya terminaler
python3 barcode_scanner.py --lank 5555                          # JSON-länk på 127.0.0.1:5555 för andra program (se docs/ROSTVAGLEDNING.md)
vcgencmd get_throttled; vcgencmd pmic_read_adc EXT5V_V          # ström
lsusb -t                                                        # USB3 (5000M) eller USB2 (480M)
python3 tts_engine.py --prewarm                                 # förgenerera tal (inte samtidigt som detect_spatial.py)
clear && sleep 5 && python3 tools/handmodell.py --sekunder 40 --namn vara1   # hittar handmodellen handen? logs/handmodell_vara1.jpg
python3 barcode_scanner.py --4k --vagledning tal --sikte hand --filter --utan-handmodell   # utan handmodellen (som före 9/11)
python3 -m json.tool kartor/produkter.geojson > /dev/null && echo "kartan ok"   # är kartan rätt skriven?
python3 barcode_scanner.py --4k --vagledning tal --sikte hand --filter --lank 5555   # med länken, för knapparna
python3 tools/knappar.py                                        # i en andra terminal: mellanslag upprepa, S senaste, K korgen, H hjälp
python3 tools/lyssna.py "Senaste varan var Tomatpure, 500 gram."   # provlyssna en fras utan kameran (--knappar, --fraser)
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -t .   # testerna utan förkompilerade filer (efter mutationstest)
```

Sammanställning av alla körningar görs med `analyze_scans.py`, som läser `logs/scan_*.jsonl` (fälten står i avsnitt 3; från PR #11 även `h_px`, `hojd_andel`, `forvantat_djup_m` och `filter`). Träffprocent (försök) och bildrutor/s från kameran finns bara i terminalens sammanfattning.

**När Pi:n inte går att nå** (`Could not resolve hostname vision-pi1.local`): kontrollera att lampan lyser grönt (Pi 5 har en lampa: grön = igång, röd = avstängd), att datorn är på samma wifi, och leta efter Pi:n med `arp -a` i PowerShell efter en pingrunda över nätet (`foreach ($i in 1..254) { $null = ping -n 1 -w 200 "192.168.50.$i" }`). Raspberry Pi har fysiska adresser som börjar med 88-a2-9e (Elias Pi 5, 13/11), 2c-cf-67, d8-3a-dd, dc-a6-32, e4-5f-01, 28-cd-c1 eller b8-27-eb. **13/11:** Pi:n var på nätet men namnet gick inte att nå från Windows; den hittades på sin adress, och SSH-filen på laptopen pekar nu `vision-pi1.local` på adressen (raderna `HostName`). Byt siffrorna där om adressen ändras. 27/10 hade Pi:n tappat wifi. Förebygg med `sudo nmcli connection modify "<wifi-namnet>" connection.autoconnect yes`.

Elias hämtar bilder genom att högerklicka i VS Code och välja **Download**. Skriv `clear` före en körning så att bara den nya utskriften kopieras. Översiktsbilder görs med `python3 tools/mosaik.py NAMN` (senaste körningen) eller `--senaste N` / `--korning scan_…`. Sedan 7/11 sparar `--diag` bilderna i `logs/snapshots/<körning>/`, så ingenting behöver rensas före en körning. Ta bort gamla mappar då och då (`rm -r logs/snapshots/scan_202610*`): en 4K-körning kan ta 60–120 MB (uppskattat).

**Test av skannern utan kamera:** föregående agent testade med en låtsas-kamera (en `Device`-klass som levererar syntetiska bilder) och syntetiska EAN-13-koder med känd modulstorlek (kodningstabellerna L/G/R och paritet är standard). Den koden ligger inte i repot. Skriv om den om du ändrar `barcode_scanner.py`, och kontrollera `px_per_modul` mot kända modulstorlekar. Obs: testkodernas streck måste vara tillräckligt höga för roterade koder, annars går de inte att avkoda.

---

## 10. Öppna frågor till Elias
- Riktningskonventionen: Elias kör `--sikte hand` i proven (kameran stilla, varan i handen). Ska `hand` bli standard?
- Är tipsen lätta att följa blundande? Är 10 s mellan dem lagom i längden? Saknas något kommando?
- ~~Hjälper `--fokusruta`?~~ Nej när varan inte ligger i mitten (6/11); `--hand` ersätter den.
- ~~Ska `--hand` bli standard? Ska tipsen vänta 8 s efter "Håll stilla."?~~ Avgjort 7/11 (ja, nej). ~~Vilken fras ersätter "en halv armlängd"?~~ "Håll varan nära, armbågen mot kroppen." (11/11, ändring 41).
- ~~Handmodell (MediaPipe) som nästa steg?~~ Byggd 9/11.
- Ska en sedd kod utan bekräftad hand hålla tipsen tillbaka? Ska handmodellen göras snabbare (121 ms per bildruta)?
- Vilka svar har kommit på förfrågningarna om butikstest och examensarbete? **13/11:** en butik har sagt ja till tester (butiksbesök vilken dag som helst; namnet står inte här).
- Vilken vara var "ättika, 150 s" i arbetsloggen 10/11? Den hade koden `5701092110183`, inte ättikans `7331642037042`. Loggen 10/11 rättas när det är känt.
- Gränsen i regel 4b (0,37 m) och i ändring 43 B (0,30 m): justera efter fler varor och körningar?
- Dialogen: vad vill användarna fråga, knappar eller röst? Steg 2–3 när?
- ~~Replay på de gamla loggarna~~ Gjort 4–5/11: 0 fel vara.
- Grannvaror på en hylla: räknas två produkter nära varandra som konflikt (`conflict_radius`)? Testas i butiken.
- ~~Ska en tunn läsning ge "lite närmare" i stället för tystnad~~ Beslutat och byggt 3/11.
- Finns en vara med kort streckkod (13 siffror, korta streck) att testa höjdfiltret på? EAN-8 läses sedan ändring 28.
- Har ICA-butiken svarat på mejlet?
- Vad ska uppställningen heta när den blir standard (tejpmärken, stöd, bakgrund), så att resultaten går att upprepa?
- Vilken butik/vilka butiker finns det tillgång till för att spana in etiketter?
- Röstvägledningen: ton, ord eller båda? Vilken konvention för riktning?
- UPS-HAT 5 V/6 A beställd (5/11), leverans 18–23/11. Ny Y-adapter behövs inte med den. Celler köpta?
- Ska skärpa i kodens ruta loggas (se avsnitt 7, ursprunglig punkt 3)? Elias har inte tagit ställning.

*Det fullständiga samtalsunderlaget (om det finns kvar i sessionens miljö) ligger under `~/.claude/projects/` för sessionen. Räkna inte med att det finns: miljön är tillfällig. Rådata (`logs/scan_*.jsonl`) ligger bara på Pi:n.*

---

## 11. Arbetsloggar (PDF i `docs/rapporter/`)

Nyaste överst.

| Fil | Innehåll |
|---|---|
| `docs/rapporter/Vision5_knappar_och_ljus_2026-11-13.pdf` | 13/11: "Sakta närmare." efter avståndet (regel 4b) kom 4 av 4 gånger när handen var bekräftad, ändring 43 (8 s efter en kod; "Håll stilla." inom 0,30 m), handmodellen på samma plats dagsljus 88 % mot kväll 13 % (17,4 lux), 110 s tystnad och ändring 44, knapparna från laptopen och provlyssningen (hela meningar), dialogidén, vad som är osäkert, nästa steg |
| `docs/rapporter/Vision5_avstandet_2026-11-11.pdf` | 11/11: avståndsmätning med ättikan på stöd (30 cm: 97 och 95 % av bildrutorna godkända; 40 cm: 0 och 0 %; felläsningar bara vid gränsen, alla stoppade av höjdfiltret), rösttester i dagsljus med varorna på ca 30 cm (alla tre varorna lästes, ättikan 16 och 10 s), handmodellen 70–76 % i dagsljus, ändring 41 ("Håll varan nära, armbågen mot kroppen."), fel facit och nätverket, vad som är osäkert, nästa steg |
| `docs/rapporter/Vision5_kvallsljus_2026-11-10.pdf` | 10/11: fem rösttester i lampljus (0 läsningar av tre skäl: mörker, kameran för högt, motljus; sedan lästes tomatpurén mot en upplyst vägg), handmodellen 0–26 % i lampljus mot 72 % i dagsljus, 45 s tystnad efter "Redo" och ändring 40 ("Håll nästa vara framför dig." efter 5 s, fungerade på Pi:n), ättikan 150 s vid läsgränsen, Gemini och lätta hyllor först, nästa steg |
| `docs/rapporter/Vision5_handmodellen_2026-11-09.pdf` | 7–9/11: detektorn och regel 3b, rösttester blundande (12 s), "Redo" efter 8 s, handmodellen (handflata ensam 16–55 % fel på bordet; med landmärkesmodellen 83 % och 83 % med vara, 0 % utan), förminskningsfelet, handmodellen i skannern, 33 s tystnad och ändring 39, vad som är osäkert, nästa steg |
| `docs/rapporter/Vision5_handen_och_fokus_2026-11-07.pdf` | 6–7/11: USB 3 och kontakten, kamerans vinkel (mosaikerna), "Sakta närmare."/"Håll stilla.", en läsning gav 4 fel namn, linstabellen, `--hand` 13–15 % mot 4 %, vad som är osäkert, nästa steg |
| `docs/rapporter/Vision5_rostvagledning_pa_pi_2026-11-05.pdf` | Röstvägledningen på Pi:n 4–5/11: vad som hände i varje prov, felsökningen av kamerakrascherna (Y-adaptern), ändringarna PR #19–#28, vad som är osäkert, nästa steg |
| `docs/rapporter/Vision5_rostvagledning_2026-11-03.pdf` | Arbetslogg 3/11: vad som byggdes och varför, arkitekturen, hur det är testat (99 tester, mutationskontroll), vad som inte är testat, nästa steg |
| `docs/rapporter/Vision5_varutest_del2_2026-10-29.pdf` | Varutest del 2 (4K): Coca-Cola med EAN-8 läser till 0,71 m, kaffefiltret rakt och stabilt ger inga fel. **Rättar flera slutsatser i del 1** |
| `docs/rapporter/Vision5_varutest_kaffefilter_2026-10-29.pdf` | Varutest del 1 (4K): kaffefilter med 22 felläsningar i en lutande, instabil uppställning, förslag på konfliktregel. Läs med rättelserna i del 2 |
| `docs/rapporter/Vision5_filter_pa_pi_2026-10-27.pdf` | Filtren på Pi:n: höjden mäter osäkerhet, inte rätt/fel; djupet fel bara första sekunden; hälften av bilderna når Pi:n |
| `docs/rapporter/Vision5_forslag_kodandring_2026-10-20.pdf` | Kodförslaget (del A filter, del B fokusstyrning) med testplan. Del A genomförd i PR #11, med ändringen att varan sägs utan position vid orimligt djup |
| `docs/rapporter/Vision5_autofokus_hojdfilter_2026-10-20.pdf` | Autofokus och kodens placering (mitten 100 %, längst ner 0 %), lins 77 vid kanten, höjdfiltret på alla loggar |
| `docs/rapporter/Vision5_fokustest_2026-10-18.pdf` | Fokustestet: 19 körningar, linsfönster per avstånd, fast lins mot autofokus, första felaktiga djupet, första tunna felläsningen. USB-raden rättad 20/10 |

**Referens, inte en arbetslogg:** `docs/ROSTVAGLEDNING.md`. Röstvägledningens regler, trösklar, länkprotokollet (JSON-rader, kommandot `say`) och kända begränsningar. Läs den före `voice_guidance/`

**Inte i repot:** dagsljustestet 15/10 och mätserien 17/10 (gjorda av föregående agent). De innehåller foton från köket. Elias har egna kopior, och siffrorna från 17/10 står i avsnitt 4.
