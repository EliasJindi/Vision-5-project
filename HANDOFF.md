# HANDOFF: Vision-5 (till nästa agent)

Skriven 2026-10-17 av föregående agent och uppdaterad samma dag efter mätserien (avsnitt 3, 4, 6, 7 och 10). Avsnitt 7 reviderades därefter efter en genomgång med Elias (ny ordning, ingen deadlinepress). **Uppdaterad 2026-10-27** efter fokustesterna 18 och 20/10 och filtertestet 27/10 (avsnitt 0, 5, 6, 7, 9, 10 och nytt avsnitt 11 med arbetsloggarna som PDF i `docs/`). **Uppdaterad 2026-10-29** efter varutesterna (kaffefilter, Coca-Cola med EAN-8): avsnitt 3, 6, 7, 10 och 11. Läs hela filen innan du gör något. Den beskriver vad projektet är, vad som är gjort, hur säkra vi är på varje resultat, vad som är på gång och **varför**. Filen innehåller medvetet inga rumsmått, koordinater, foton eller personnamn: repot är publikt.

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
  - Att tolka brus som mönster: under mätserien 17/10 drogs tre egna tolkningar tillbaka (se avsnitt 4). Dra inga slutsatser av en enstaka körning, och skriv uttryckligen *uppmätt / tolkning / hypotes*.
  - Att tro att en inklistrad utskrift är den nya körningen. Elias klistrar ibland in den gamla. **Kontrollera loggnamnet (tiden) på raden `Loggar till logs/scan_…`** och be om den nya vid behov.
- **Elias tar emot kodgranskning av andras kod** (ofta skriven av en annan AI-agent). Elias har gett tillåtelse att ändra kod om du tycker den är dålig, så länge du säger vad du ändrat och förklarar felet.
- **Måttband i tum.** Elias mäter i tum. Räkna om (tum × 2,54 = cm) i alla instruktioner.
- **Skriv inte i HANDOFF.md på eget initiativ** (Elias, 17/10). Uppdatera när Elias ber om det.
- **Arbetsloggar som PDF** efter testdagar ska läggas i `docs/` och listas i avsnitt 11, **nyaste överst** (Elias, 27 och 29/10). Aldrig foton från rummet, koordinater eller butiksnamn i dem: repot är publikt.
- **Checklistor med numrerade steg (☐ 0, 1, 2 …)** fungerar bra för Elias när tester ska köras.

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
Startade som ett utkast från en annan AI-agent. Granskad och rättad. Filhuvudet har numrerade ändringar 1–28 (20–27: filter och sammanfattning, PR #11; 28: EAN-8, PR #14). I korthet:
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
- Elias planerade att köpa batterier/UPS HAT och en riktig strömförsörjning (officiella 27 W) efter lönen den 25:e. **Inte köpt än (27/10), av ekonomiska skäl.** Powerbanken räcker för skannertesterna (`throttled=0x0` hela tiden). **Kontrollera vid valet** att USB-effekten räcker för kameran.
- Mätning är ogiltig om `throttled` ändras mellan körningar (Pi:n sänker då processorhastigheten, och det ser ut som att avståndet är problemet).

---

## 6. Läget just nu och vad som väntar på Pi:n

**Pi:n är på `main` med PR #11 (27/10).** Fokustestet är gjort (18 och 20/10) och filtren är testade på Pi:n (27/10). Detaljer och alla körningar i PDF:erna i `docs/` (avsnitt 11). Det viktigaste:

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

**Pi:n kan tappa wifi** (hände 27/10, `vision-pi1.local` gick inte att nå). Se avsnitt 9.

**Test i uppställning att använda:** **koden nära mitten av bilden** (annars fokuserar autofokus på bakgrunden), köket i dagsljus, fönstret bakom kameran, **bara testobjektet i bild**, kameran plant, paketet rakt upp på ett stabilt stöd med rak framsida mot kameran, **tejpmarkerad bas för paketet och kamerans fötter** så att uppställningen kan upprepas. Mät vinkeln med mobilens vattenpass. Skriv ner varje ändring (en sak i taget). Mät avstånd med djupet, inte måttbandet.

---

## 7. Det jag tänkte göra härnäst, och varför

**Tidsram (2026-10-17):** exjobbet börjar först nästa termin, så det finns ingen deadline att stressa mot. En person kommer då att hjälpa Elias med koden. Prioritera därför att det som byggs nu är **förstått, repeterbart och dokumenterat** framför att hinna med många funktioner. Ordningen nedan reviderades efter en genomgång samma dag: punkt 2 är ny, positionstestet är flyttat fram och vinkel och djupkontroll är sammanslagna i punkt 5. Kodändringar föreslås först och görs när Elias säger ja.

**Status 29/10:** varutester gjorda för tomatpuré, kaffefilter och Coca-Cola (EAN-8) i 4K, se avsnitt 6 och de två PDF:erna från 29/10. Del 2 rättar flera slutsatser från del 1. EAN-8 inlagt (PR #14). **Nästa: röstvägledning.** Först ett skriftligt förslag som Elias godkänner: "lite närmare" vid tunna läsningar, riktning (vänster/höger/upp/ner) utifrån var koden sitter i bilden, "håll stilla" vid konflikt mellan två koder, och pip + varans namn vid säker läsning. Därefter test med ögonbindel. Burk och blank påse kan vänta. Resultaten gäller bästa fall (kameran rätt riktad); den riktiga användarfrågan besvaras med röstvägledning och test med ögonbindel.

**Status 27/10:** punkt 1 (fokustestet) är gjord. Del A av kodförslaget (`docs/Vision5_forslag_kodandring_2026-10-20.pdf`) är genomförd i PR #11: höjd- och djupfilter som loggas och avvisar med `--filter`, `scan_filters.py`, `analyze_scans.py`. Ändrat efter granskning: vid orimligt eller saknat djup sägs varan utan position. Punkt 2–5 nedan är inte påbörjade. **Ny ordning härifrån:**
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
6. **Röstvägledning för siktet** (Elias vill fundera extra på den, och tycker den är en bra funktion). Se nedan. *Varför:* löser sikteproblemet, som är designkrav för blinda användare.
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
vcgencmd get_throttled; vcgencmd pmic_read_adc EXT5V_V          # ström
lsusb -t                                                        # USB3 (5000M) eller USB2 (480M)
python3 tts_engine.py --prewarm                                 # förgenerera tal (inte samtidigt som detect_spatial.py)
```

Sammanställning av alla körningar görs med `analyze_scans.py`, som läser `logs/scan_*.jsonl` (fälten står i avsnitt 3; från PR #11 även `h_px`, `hojd_andel`, `forvantat_djup_m` och `filter`). Träffprocent (försök) och bildrutor/s från kameran finns bara i terminalens sammanfattning.

**När Pi:n inte går att nå** (`Could not resolve hostname vision-pi1.local`): kontrollera att lampan lyser grönt (Pi 5 har en lampa: grön = igång, röd = avstängd), att datorn är på samma wifi, och leta efter Pi:n med `arp -a` i PowerShell efter en pingrunda över nätet (`foreach ($i in 1..254) { $null = ping -n 1 -w 200 "192.168.50.$i" }`). Raspberry Pi har fysiska adresser som börjar med 2c-cf-67, d8-3a-dd, dc-a6-32, e4-5f-01, 28-cd-c1 eller b8-27-eb. 27/10 hade Pi:n tappat wifi. Förebygg med `sudo nmcli connection modify "<wifi-namnet>" connection.autoconnect yes`.

Elias hämtar bilder genom att högerklicka i VS Code och välja **Download**. Skriv `clear` före en körning så att bara den nya utskriften kopieras. Översiktsbilder (de 16 senaste bilderna i en mosaik) har gjorts med ett kort OpenCV-skript. Skriv om det vid behov, och ta bilden **innan** bilderna rensas med `rm logs/snapshots/snap_*.jpg`.

**Test av skannern utan kamera:** föregående agent testade med en låtsas-kamera (en `Device`-klass som levererar syntetiska bilder) och syntetiska EAN-13-koder med känd modulstorlek (kodningstabellerna L/G/R och paritet är standard). Den koden ligger inte i repot. Skriv om den om du ändrar `barcode_scanner.py`, och kontrollera `px_per_modul` mot kända modulstorlekar. Obs: testkodernas streck måste vara tillräckligt höga för roterade koder, annars går de inte att avkoda.

---

## 10. Öppna frågor till Elias
- Ska en tunn läsning ge "lite närmare" i stället för tystnad (avsnitt 7, ny punkt 1)?
- Finns en vara med kort streckkod (13 siffror, korta streck) att testa höjdfiltret på? EAN-8 läses sedan ändring 28.
- Har ICA-butiken svarat på mejlet?
- Vad ska uppställningen heta när den blir standard (tejpmärken, stöd, bakgrund), så att resultaten går att upprepa?
- Vilken butik/vilka butiker finns det tillgång till för att spana in etiketter?
- Röstvägledningen: ton, ord eller båda? Vilken konvention för riktning?
- När blir det råd med strömförsörjning och vilken UPS HAT/PSU? (Inte köpt 27/10.)
- Ska skärpa i kodens ruta loggas (se avsnitt 7, ursprunglig punkt 3)? Elias har inte tagit ställning.

*Det fullständiga samtalsunderlaget (om det finns kvar i sessionens miljö) ligger under `~/.claude/projects/` för sessionen. Räkna inte med att det finns: miljön är tillfällig. Rådata (`logs/scan_*.jsonl`) ligger bara på Pi:n.*

---

## 11. Arbetsloggar (PDF i `docs/`)

Nyaste överst.

| Fil | Innehåll |
|---|---|
| `docs/Vision5_varutest_del2_2026-10-29.pdf` | Varutest del 2 (4K): Coca-Cola med EAN-8 läser till 0,71 m, kaffefiltret rakt och stabilt ger inga fel. **Rättar flera slutsatser i del 1** |
| `docs/Vision5_varutest_kaffefilter_2026-10-29.pdf` | Varutest del 1 (4K): kaffefilter med 22 felläsningar i en lutande, instabil uppställning, förslag på konfliktregel. Läs med rättelserna i del 2 |
| `docs/Vision5_filter_pa_pi_2026-10-27.pdf` | Filtren på Pi:n: höjden mäter osäkerhet, inte rätt/fel; djupet fel bara första sekunden; hälften av bilderna når Pi:n |
| `docs/Vision5_forslag_kodandring_2026-10-20.pdf` | Kodförslaget (del A filter, del B fokusstyrning) med testplan. Del A genomförd i PR #11, med ändringen att varan sägs utan position vid orimligt djup |
| `docs/Vision5_autofokus_hojdfilter_2026-10-20.pdf` | Autofokus och kodens placering (mitten 100 %, längst ner 0 %), lins 77 vid kanten, höjdfiltret på alla loggar |
| `docs/Vision5_fokustest_2026-10-18.pdf` | Fokustestet: 19 körningar, linsfönster per avstånd, fast lins mot autofokus, första felaktiga djupet, första tunna felläsningen. USB-raden rättad 20/10 |

**Inte i repot:** dagsljustestet 15/10 och mätserien 17/10 (gjorda av föregående agent). De innehåller foton från köket. Elias har egna kopior, och siffrorna från 17/10 står i avsnitt 4.
