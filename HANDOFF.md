# HANDOFF: Vision-5 (till nästa agent)

Skriven 2026-10-17 av föregående agent. Läs hela filen innan du gör något. Den beskriver vad projektet är, vad som är gjort, hur säkra vi är på varje resultat, vad som är på gång och **varför**. Filen innehåller medvetet inga rumsmått, koordinater, foton eller personnamn: repot är publikt.

---

## 0. Läs det här först: så arbetar du med Elias

- **Språk:** svenska. Ärlig, konkret feedback. Små tydliga delmål, ett steg i taget ("vi tar en sak i taget").
- **Visionen byggs hel.** Elias vill inte ha en nedskuren version. Idéer som parkeras ska skrivas ned, inte ignoreras.
- **Elias är student och kör testerna själv på en Raspberry Pi.** Du ser inte hårdvaran. Allt du vet kommer från det Elias klistrar in (terminalutskrifter, bilder). Be om utskrift, gissa inte.
- **Ingen kodändring utan att Elias bett om den.** Föreslå först. Elias har uttryckligen sagt: "nej gör inte nya ändringar" när jag ändrade oombedd. När Elias säger "ja gör så" till ett konkret förslag är det klartecken för just det.
- **Säg alltid vad du ändrat och varför**, och kommentera det i filhuvudet (de numrerade ändringslistorna i `barcode_scanner.py` är mönstret).
- **Vanliga misstag att undvika** (alla har hänt):
  - Att dra slutsatser innan man mätt. Regel: **testa först, spekulera sedan.**
  - Att presentera beräknade siffror som mätta. Markera alltid: *uppmätt / beräknat / hypotes*.
  - Att ge råd som skapar ett nytt fel (jag föreslog att höja kameran med saker under, och det lutade uppställningen och förstörde flera körningar). Elias hittade felet själv.
  - Att påstå att något "bevisats" på tunt underlag.
- **Elias tar emot kodgranskning av andras kod** (ofta skriven av en annan AI-agent). Elias har gett tillåtelse att ändra kod om du tycker den är dålig, så länge du säger vad du ändrat och förklarar felet.
- **Måttband i tum.** Elias mäter i tum. Räkna om (tum × 2,54 = cm) i alla instruktioner.

### Säkerhetsregler (hårda)
- **API-nycklar klistras aldrig in i chatten.** Nyckeln ligger i miljövariabeln `GEMINI_API_KEY` / `.env` på Pi:n.
- **`.env` committas aldrig.** Säkerhetskopian `ai_glasses_backup.tar.gz` innehåller `.env` och får inte delas.
- **Repot är publikt.** Lägg inte in rumskartan (`kartor/*.geojson`), foton, bilder från rummet eller loggar. De är ignorerade/hålls utanför.
- **Säkerhet (hinder, bilar, trappor) sköts alltid lokalt och snabbt**, aldrig av molnet eller en agent. Gemini får vara långsam och kan ha fel, därför får den inte avgöra "bil, 0,6 meter".
- Systemet får **aldrig säga "fri väg"** (det går inte att veta).

### Git-arbetssätt (Elias vill ha allt på `main`)
- Utveckla på grenen `claude/affectionate-pasteur-gero98`, pusha, skapa PR mot `main` och mergea. Elias har bett om detta: "varje gång vi ändrar så ska det finnas där på main".
- Efter att en PR är mergad: starta om grenen från `main` (samma namn):
  `git fetch origin main && git checkout -B claude/affectionate-pasteur-gero98 origin/main`
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
- Luxonis OAK-D Lite (DepthAI 2.33), går idag på **USB HIGH (USB2)**, troligen Y-adaptern eller kabeln. Kontrollera med `lsusb -t` (5000M = USB3, 480M = USB2).
- Piper TTS (`sv_SE-alma-medium`) via `pw-play`; Logitech G435-headset med USB-dongel.
- Gemini 2.5 Flash (`google-genai`).
- Strömförsörjning: Baseus 65 W-powerbank (se avsnitt 5).

**Filer i repot (`main`)**

| Fil | Ansvar |
|---|---|
| `detect_spatial.py` | Huvudloop: YOLO + djup på kameran, akutlarm, Gemini-knapp |
| `audio_manager.py` | Prioritetskö för ljud (TTL per nivå, akutlarm avbryter, minst 0,7 s uppspelning först) |
| `tts_engine.py` | Piper som en process (`--json-input`), WAV-cache i `cache/tts/`, låst till kärna 2–3. `--prewarm` genererar 241 fraser |
| `phrases.py` | Fraser och avståndsformat (stil G: "Bil, 0,6 meter.") |
| `gemini_service.py` | Anrop till Gemini, timeout 10 s via `HttpOptions` (millisekunder) |
| `telemetry_logger.py`, `analyze_telemetry.py` | Spänning (`EXT5V_V`), `throttled`, temperatur, ljudkö; analys av latens m.m. |
| `measure_phrases.py` | Mätverktyg för fraslängd |
| `barcode_scanner.py` | **Rumstestet:** streckkod → karta → position. Se avsnitt 3–4 |
| `test_cam.py` | Gammal kameratest |

**Inte i repot (finns bara på Pi:n):** `kartor/produkter.geojson`, `kartor/mobler.geojson`, `.env`, `logs/`, `cache/`, Piper-modellen.

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
Startade som ett utkast från en annan AI-agent. Granskad och rättad. Filhuvudet har numrerade ändringar 1–17. I korthet:
- Rättade krascher (`time.timedelta`, `msg.get` på en MessageGroup) och en begränsning av skanningstakten som bara gällde efter en träff (30 avkodningar/s = strömproblem).
- **Extended disparity** så att djup finns ner till ~0,20 m (annars ~0,35 m). **Reservruta** för djup runt kodens yta.
- `--diag`: sparar en bild varannan sekund i `logs/snapshots/` (max 60) med ljus- och skärpevärde, och grön ram runt funna koder.
- `--4k`: 3840×2160 @ 5 fps (1080p @ 15 fps är standard). Varnar om USB inte är USB3.
- **Ändring 13–17 (2026-10-15, PR #6 och #7):** alla avläsningar loggas (även okända och felläsningar); `--facit EAN` märker varje läsning rätt/fel och skriver `FELLÄSNING`; pixlar per modul (`px_per_modul`) mäts från kodens hörn; läget (`4k`/`1080p`) står i loggfilens namn; försöksräknare (träffprocent efter 10 s uppvärmning) i sammanfattningen vid Ctrl+C.

**Loggformat** (`logs/scan_<datum>_<tid>_<4k|1080p>.jsonl`, en rad per avläsning, `fsync`): `t`, `mode`, `raw`, `ean`, `format`, `w_px`, `px_per_modul`, `rot_deg`, `hornen`, `bild`, `in_map`, `depth_how`, `distance_m`, och om `--facit`: `facit`, `correct`; för varor i kartan även `namn`, `candidates` (positioner), `ambiguous`. Bara avkodade koder loggas. Bildrutor utan kod ger ingen rad.

Skannern är **fristående**. Kör den aldrig samtidigt som `detect_spatial.py`, och den varnar inte för hinder eller människor.

---

## 4. Mätresultat och hur säkra de är

Tomatpuré (kod 33 mm), köket i dagsljus, powerbank, kameran rakt på bordet. Avstånd enligt kamerans djup.

| | 4K | 1080p |
|---|---|---|
| Stabilt | 0,38 m och 0,53 m (varje bild) | 0,21–0,22 m (62 läsningar) |
| Gräns | **0,62 m: ibland** (6 läsningar på ~1 min, ~10 %) | **~0,25 m: ibland rätt, ibland felläsning** |
| Inte alls | 0,81 m | ~0,25 m med dålig vinkel (10 tum) |

Linserna (14 oktober, kvällsljus ~55–75/255): 1080p 0,20 m, 4K stabilt ~0,35 m och ibland 0,45–0,50 m (mindre kod).

**Säkerhetsklass för varje påstående**

| Påstående | Status |
|---|---|
| Läsavstånden ovan | **Uppmätta** (loggar bekräftar) |
| 4K ≈ 2,4× längre läsavstånd än 1080p för samma kod | **Uppmätt**, litet underlag |
| Pixlar per modul vid gränsen (4K ~1,6–1,8, 1080p ~1,95–2,1) | **Beräknade** ur teorin (69° bildvinkel, 0,35 mm), **inte** mätta. Antar samma bildvinkel i båda lägena |
| "4K gav inga felläsningar" | Gäller bara de 6 av 11 4K-körningar där utskriften granskades. Felläsningar loggades inte då |
| "1080p felläser för att bilden skalas ner" | **Hypotes** |
| Måttband mot djup skiljer ~2 cm | **Ryms i måttbandets avrundning** (tum/halvtum, ±1,3 cm). Inget säkert offset |
| Säkerhetsregel "säg gå närmare under 2,5 px/modul" | **Inte testad.** Hade enligt de beräknade siffrorna blockerat 4K-läsningar som fungerade. Tröskeln måste mätas per läge |

### Viktiga fynd
1. **Stabila felläsningar.** På ~0,25 m i 1080p lästes tomatpurén som `6038721300844` ~20 gånger i rad. Rätt kod var `7340083497834`. Den gröna ramen satt på rätt kod, så felet ligger i avkodningen, inte i att fel sak hittades. Felkoderna hade **giltig kontrollsiffra** (som fångar ett enstaka fel, inte flera samtidigt). Bilden står stilla, så felet blir detsamma varje gång. **"Kräv 2–3 likadana läsningar" räcker därför inte.** Det som skyddade var att koden inte fanns i kartan.
2. **Vinkeln spelar lika stor roll som avståndet** nära gränsen. Kameran höjdes med saker under och lutade uppställningen: 0 läsningar i flera körningar.
3. **Motljus:** med fönstret i bild exponerar kameran efter fönstret. Ljusvärdet i `--diag` är ett **medelvärde över hela bilden** och säger inget om själva koden (det visade 85 när koden var för mörk).
4. **Autofokus** behöver ~10 s, luras av starka lampor och kan fastna. Ett kritiskt läge var nära håll (~0,2 m). Skärpevärdet i `--diag` är mest pålitligt som mätare.
5. **Att sikta** är ett verkligt problem (utan sökare hamnade koden i bild 1 av 14 gånger). En blind användare har samma problem.
6. **Nära gränsen är läsningen mycket känslig** för avstånd, vinkel och var i bilden koden sitter. Räkna med god marginal: ~0,5 m för den här koden i 4K, inte 0,62 m.
7. **Strömmen på powerbank höll** under dagsljustestet: `throttled=0x0`, ~4,83 V i vila och 4,90–4,95 V under körning.

### Begränsningar upptäckta i `barcode_scanner.py` (testat med syntetiska koder)
- `px_per_modul` är rätt för rak och 90° roterad kod. Vid andra vinklar mäter zxing längs en rak skanrad, så värdet blir för högt med 1/cos(vinkeln) (+3,5 % vid 15°).
- **zxing ger en rak rektangel för streckkoder även när koden lutar åt sidan.** Lutning (perspektiv) går alltså **inte** att läsa ur hörnpunkterna. Ett första försök (`persp`) gav alltid 1,0 och togs bort. Lutning måste mätas ur **djupet** (vänster mot höger sida), vilket inte är gjort.
- Antagandet att zxings position omfattar de 95 modulerna är bara kontrollerat på syntetiska bilder.
- `--facit` räknar **allt** som inte är facit som felläsning, även en riktig annan streckkod som råkar vara i bild (t.ex. ett cornflakespaket i bakgrunden).
- Positionsberäkningen ignorerar **sidoavvikelse**: den antar att användaren står rakt framför varan. Sitter koden i bildens kant blir felet upp till ~20 cm på 0,35 m. Troligen större än djupfelet.
- Stereodjupet är stabilt (samma värde på millimetern) men hoppar i steg som växer med avståndet i kvadrat. **Repeterbarhet är inte riktighet.**

---

## 5. Strömmen

- Powerbanken ger 15 W. Pi 5 vill ha 25 W (och ger bara 600 mA till USB utan 5 A-strömförsörjning). Rumstestet fungerar ändå, men håll koll på `throttled` efter varje körning (`vcgencmd get_throttled`; `0x0` = ingen underspänning sedan start).
- Elias köper efter lönen den 25:e: batterier/UPS HAT och en riktig strömförsörjning (officiella 27 W). **Kontrollera vid valet** att USB-effekten räcker för kameran.
- Mätning är ogiltig om `throttled` ändras mellan körningar (Pi:n sänker då processorhastigheten, och det ser ut som att avståndet är problemet).

---

## 6. Vad som väntar just nu: dagsljustestet med `--facit`

**Läge vid skrivandet:** Elias fick en komplett testplan (steg 0–9) men har **inte** återkommit med resultat. Jag vet inte om testet är kört, eller om Pi:n är uppdaterad. Fråga först. Pi:n ska stå på `main` (`git log -1` ska visa merge-commiten för PR #7, `ffd01a9`).

**Varför testet:** vi har bara beräknade pixlar per modul och inga felläsningar loggade för 5 av 11 körningar. Vi behöver mätt data för att kunna bestämma en säker tröskel för "gå närmare" (och för att veta om det går att skilja rätt från fel alls).

**Testplanen (kort)** (full version gavs till Elias i chatten):
0. `cd ~/ai_glasses && git pull && sync && source venv/bin/activate`, kontrollera commit.
1. `vcgencmd get_throttled; vcgencmd pmic_read_adc EXT5V_V` som utgångsvärde.
2. Köket i dagsljus, fönstret bakom kameran, **bara tomatpurén i bild**, kameran rakt, koden mitt i bilden.
3. Kontrollkörning 4K på 15 tum: `python3 barcode_scanner.py --diag --4k --facit 7340083497834; vcgencmd get_throttled; vcgencmd pmic_read_adc EXT5V_V`. Kontrollera att `px/modul` ligger runt **2,6**.
4. 4K-serie: 19, 20, 21, 22, 23, 24, 25 tum, 60 s per steg efter 10 s fokus. Sluta vid två noll i rad.
5. 1080p-serie (utan `--4k`): 7, 8, 9, 10, 11 tum.
6. Jämför måttband (tum × 2,54) mot utskrivet djup.
7. Sammanställning av alla loggar (ett kort Python-skript som skriver ut läsningar, median/min px per modul för rätta och fel).
8. `sync`. 9. Skicka allt hit.

**Förväntade värden (beräknade, 0,35 mm per modul, 69° bildvinkel):** 4K på 0,38 m ≈ 2,6 px/modul; 4K på 0,53 m ≈ 1,85; 1080p på 0,22 m ≈ 2,2. Avviker de mer än ~15 % är antingen bildvinkeln fel eller zxings hörnpunkter inte där vi tror. Det är i så fall ett resultat i sig, eftersom kamerans verkliga pixelskala då kan räknas ut ur datan.

---

## 7. Det jag tänkte göra härnäst, och varför

I ordning:

1. **Analysera Elias testdata** (när den kommer). *Varför:* gör beräknade siffror till mätta.
   - Jämför `px_per_modul` mot de förväntade värdena ovan. Räkna ut verklig pixelskala per läge.
   - Bygg en tabell per läge och avstånd: försök, träffprocent, rätt/fel, px/modul för rätta och fel.
   - **Bestäm tröskeln per läge**, om fördelningarna för rätt och fel går att skilja. Om de överlappar: säg det ärligt och föreslå alternativ (t.ex. dubbelkoll mot butikens produktlista, läsning ur lite olika bilder, Gemini som dubbelkoll vid osäkerhet).
   - **Validera tröskeln på andra körningar** än de den togs fram på. Annars är den inte testad.
   - Uppdatera arbetsloggen (PDF) och rätta de punkter som markerats som beräknade.
2. **Kontrollera djupet mot måttband** (0,3 / 0,5 / 1,0 / 1,5 m). *Varför:* stereofelet växer med avståndet i kvadrat. Den observerade 2 cm-skillnaden går inte att tolka eftersom måttbandet avrundades. Obs: djupet skrivs bara ut när en kod läses, så avstånd bortom läsgränsen kräver en större testkod.
3. **Positionstestet.** Lägg om tejpkorsen (de gamla låg 0,6–1,0 m från varan, för långt för att läsa koden) på ~0,35 m och kör 4K. *Varför:* mäter hela kedjan karta → kod → position. Räkna med att sidoavvikelse är största felkällan.
4. **Röstvägledning för siktet** (Elias vill fundera extra på den, och tycker den är en bra funktion). Se nedan. *Varför:* löser sikteproblemet, som är designkrav för blinda användare.
5. **Knappskanning** (USB-knapp via `evdev`, systemd): kameran sitter på pannband och följer huvudet. Skanna några sekunder vid tryck. *Varför:* mindre ström, inga oönskade avläsningar, passar att användaren "tittar" på varan.
6. **Gemini som reserv** när ingen kod syns eller den är osäker (produktigenkänning, "koden sitter på baksidan, vänd paketet"). *Varför:* skalar till hundratals produkter utan att träna egna modeller.
7. **Hyllkantsetiketter**, **integration** med `detect_spatial.py` (en kamera, säkerhetslarmen först, position på nivå 3 i ljudkön), eventuell **AI-agent** med verktyg (`ta_bild`, `läs_streckkod`, `slå_upp_i_kartan`, `säg`; aldrig säkerhet), sist en **genomgång** för att göra allt så robust som möjligt.

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
vcgencmd get_throttled; vcgencmd pmic_read_adc EXT5V_V          # ström
lsusb -t                                                        # USB3 (5000M) eller USB2 (480M)
python3 tts_engine.py --prewarm                                 # förgenerera tal (inte samtidigt som detect_spatial.py)
```

Elias hämtar bilder genom att högerklicka i VS Code och välja **Download**. Skriv `clear` före en körning så att bara den nya utskriften kopieras. Översiktsbilder (de 16 senaste bilderna i en mosaik) har gjorts med ett kort OpenCV-skript. Skriv om det vid behov, och ta bilden **innan** bilderna rensas med `rm logs/snapshots/snap_*.jpg`.

**Test av skannern utan kamera:** föregående agent testade med en låtsas-kamera (en `Device`-klass som levererar syntetiska bilder) och syntetiska EAN-13-koder med känd modulstorlek (kodningstabellerna L/G/R och paritet är standard). Den koden ligger inte i repot. Skriv om den om du ändrar `barcode_scanner.py`, och kontrollera `px_per_modul` mot kända modulstorlekar. Obs: testkodernas streck måste vara tillräckligt höga för roterade koder, annars går de inte att avkoda.

---

## 10. Öppna frågor till Elias
- Är dagsljustestet med `--facit` kört? Vilka resultat?
- Har Pi:n hämtat `main` (PR #6 och #7)?
- Vilken butik/vilka butiker finns det tillgång till för att spana in etiketter?
- Röstvägledningen: ton, ord eller båda? Vilken konvention för riktning?
- Datum för inköp av strömförsörjning (efter den 25:e) och vilken UPS HAT/PSU?

*Det fullständiga samtalsunderlaget (om det finns kvar i sessionens miljö) ligger under `~/.claude/projects/` för sessionen. Räkna inte med att det finns: miljön är tillfällig. Arbetsloggarna (PDF) som gjordes för Elias ligger inte i repot eftersom de innehåller rummets mått. Elias har egna kopior.*
