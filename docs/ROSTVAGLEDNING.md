# Röstvägledning

*Skriven 2026-11-03. Kod: `voice_guidance/`. Status: byggd och enhetstestad, **inte körd på Pi:n än**.*

Mätningarna 17–29/10 gav en tydlig bild: koden läses säkert när den är tillräckligt stor, ungefär rak och mitt i bilden, och felläsningar kommer när den är för liten eller tunn. Röstvägledningen gör att användaren själv tar sig in i den säkra zonen. Den säger **vad som ska ändras** ("lite närmare", "lite åt vänster") och bekräftar varan först när läsningen är säker.

Allt här gäller **bästa fall** (kameran rätt riktad). Om det fungerar för någon som inte ser kan bara ett test med ögonbindel visa.

## Så hänger delarna ihop

```
 kamera ──> barcode_scanner.py ──> handle_barcode() ──> loggrad (rec)
            (Python, äger kameran)                        │
                                                          ▼
                                              GuidanceSession.on_frame(t, recs)
                                   ┌──────────────────────┼───────────────────────┐
                                   ▼                      ▼                       ▼
                            GuidanceEngine          GuidanceVoice            TcpJsonLink
                       (beslut, ren logik)     (ord + Speaker)        (JSON-rader, localhost)
                                                          │                       ▲  │
                                                          ▼                       │  ▼
                                            audio_manager (nivå 3)        t.ex. C#-tjänst
```

| Del | Ansvar | Vet inget om |
|---|---|---|
| `model.py` | `CodeRead`, `FrameObservation`, `GuidanceAction`. Enda stället som läser loggradens format | ljud, kamera |
| `engine.py` | `GuidanceEngine`: vad ska sägas nu? Tiden kommer med varje bildruta | ljud, kamera, klocka |
| `catalog.py` | `ProductCatalog`: varunamn per EAN | motorn |
| `voice.py` | `GuidanceVoice` (handling → svenska) och `Speaker` (ljudsystemet eller utskrift) | beslutsreglerna |
| `link.py` | `TcpJsonLink`: händelser ut, `say` in | vad händelserna betyder |
| `session.py` | `GuidanceSession`: det enda skannern anropar | |
| `replay.py` | Spelar upp motorn mot gamla loggar | kameran |

Beroenden pekar åt ett håll och går via små gränssnitt (`Protocol`): `Speaker`, `ProductCatalog`, `EventPublisher`. Därför går allt att testa utan kamera, och delar kan bytas ut (butikens sortiment som katalog, en annan röst, en annan transport).

## Reglerna

Motorn får en bildruta i taget och svarar med **högst ett besked**, eller tystnad. I prioritetsordning:

| # | Läge | Besked |
|---|---|---|
| 1 | Två **olika** koder lästes **säkert** (inte tunna) från ungefär samma ställe inom 3 s | **"Håll stilla."** Inget bekräftas under konflikten och 3 s efter. Varar den över 5 s sägs i stället **"Lite närmare."** (närmare tog bort felläsningarna 29/10, och "håll stilla" upprepat i 35 s fastnar användaren i). Är en vara redan bekräftad tiger motorn (en avvikande läsning är då troligen en felläsning) |
| 2 | Samma vara lästes **säkert** (inte tunn) minst 2 gånger inom 2 s, ingen konflikt | **Varans namn** ("Tomatpure."), följt av kartans `info` om den finns och sist korgen: **"Tomatpure. 500 gram. Tillagd."**, eller "… Finns redan i korgen." om samma vara skannats förut (ingen dubbel i korgen av misstag; antal kommer med inköpslistan). Finns varan inte i kartan: **"Okänd vara."** Sägs en gång tills varan varit borta i 5 s |
| 3 | Koden syns men är osäker (tunn eller ogiltig kontrollsiffra), ingen vara bekräftad | Ligger koden i bildens kant: **riktning** (autofokus följer bildens mitt). Annars **"Lite närmare."** |
| 4 | **Ingen kod alls** på 4 s | Tips i tur och ordning: **"Hittar ingen streckkod. Håll varan mitt framför dig."** → **"Vänd varan sakta. Koden kan sitta på en annan sida."** → **"Håll varan ungefär 30 centimeter bort."**, och sedan om igen. Var 6:e s de tre första gångerna, sedan var 10:e s, **utan slut** tills en kod syns. (5/11: med högst 3 gånger blev det tyst i 70 s, och "Ingen kod." lät som "pinkod" med den snabba rösten.) **Efter en lyckad läsning** sägs i stället **"Redo för nästa vara."** en gång, 15 s efter att varan senast syntes, sedan tyst tills en ny kod syns. "Vänd varan" vore fel då, användaren har kanske ingen vara i handen (Elias, 5/11) |
| 5 | Annars (en säker läsning som väntar på sin andra) | Tystnad |

**Pip** (4/11): när regel 3 vill säga något men takten håller tillbaka talet hörs i stället ett kort pip (70 ms), högst ett per sekund och inte närmare än 1,2 s efter tal. Användaren hör då att en kod syns och kan sluta vrida, utan att rösten pratar hela tiden. Pipet skjuter inte upp nästa vägledning. Inget pip under en konflikt, när varan redan är bekräftad, eller när ingen kod syns. **Prövat 5/11: pipet hördes aldrig.** Tunna läsningar är för få (4 på 4 min), och när koden syns men är suddig hittar zxing ingenting alls. Pipet behöver en detektor som ser *att* en kod finns utan att läsa den (OpenCV:s `BarcodeDetector`), som ska mätas innan den används. Ett pip som fått vänta mer än 0,6 s i ljudkön (t.ex. bakom ett akutlarm) slängs, eftersom det då inte längre stämmer med bilden.

Takt: minst 1,5 s mellan beskeden, och samma besked upprepas inte oftare än var 3:e s. Bekräftelsen går före (den är poängen med flödet). Allt ligger i `GuidanceConfig`:

| Värde | Standard | Varför |
|---|---|---|
| `confirm_reads` / `confirm_window_s` | 2 / 2,0 s | Röstning. Räcker **inte** ensamt mot systematiska felkoder (se konfliktregeln) |
| `lost_after_s` | 5,0 s | Efter så lång tid utan läsning räknas varan som borta. Nära pixelgränsen kommer läsningar glest, och med 2 s började rösten guida om en vara som redan sagts |
| `conflict_window_s` / `conflict_radius` / `conflict_hold_s` | 3,0 s / 0,10 / 3,0 s | **Gissat, ska finjusteras.** Se nedan |
| `conflict_escalate_s` | 5,0 s | Efter så lång konflikt byts "håll stilla" mot "lite närmare" |
| `deadzone_x` / `deadzone_y` | 0,15 / 0,25 (0,20 / 0,25 före 5/11) | Hur långt från mitten koden får ligga innan riktning sägs |
| `min_interval_s` / `repeat_after_s` | 1,5 / 3,0 s (1,8 före 5/11) | Elias 5/11: "lite snabbare" |
| `conflict_from_thin` | nej | Får en tunn läsning starta en konflikt? Köksprovet 4/11: en tunn felläsning gav "håll stilla" och 4 s extra väntan. Replay 5/11 (81 loggar): 0 fel vara med båda värdena, 44 mot 43 bekräftelser med `nej`. Två säkra läsningar av olika koder ger fortfarande konflikt |
| `ready_after_s` | 15,0 s | "Redo för nästa vara" så länge efter att en bekräftad vara försvann. 0 stänger av. Startvärde, inte prövat |
| `cue_interval_s` / `cue_quiet_s` | 1,0 s / 1,2 s | Pip: högst så här ofta, och inte så här snart efter tal. `cue_interval_s=0` stänger av pipet. Startvärden, inte prövade |
| `no_code_after_s` / `no_code_repeat_s` / `no_code_fast` / `no_code_slow_repeat_s` | 4,0 s / 6,0 s / 3 / 10,0 s | Första tipset, tätt mellan de 3 första, sedan glest utan slut. `no_code_slow_repeat_s=0` gör det tyst efter de täta, båda 0 stänger av. Startvärden | "Ingen kod": när, hur ofta och hur många gånger per sökning. 0 stänger av. Startvärden, inte prövade |

**Varför just de här reglerna (alla från mätningar):**
- *Tunn = osäker, inte fel.* Nära pixelgränsen är även rätta läsningar 1 px höga (27/10). Därför blir tunn läsning "lite närmare" och inte tystnad.
- *Konfliktregeln.* Systematiska felkoder kommer om vartannat med den rätta koden från samma ställe (kaffefiltret 29/10). Röstning ensamt hade inte räckt.
- *Riktning bara i kanten.* Autofokus landar på bildens mitt. Sitter koden i kanten blir den suddig (20/10: 0 % mot 100 %).
- *Okänd vara i stället för ett namn.* Ett namn sägs bara för varor som finns i produktlistan. En felläsning med giltig kontrollsiffra som inte finns där blir "Okänd vara" och inte ett påhittat namn. Är felkoden en annan *riktig* vara i listan kan motorn inte upptäcka det själv: det skyddas av höjdfiltret, röstningen och konfliktregeln tillsammans.

## Orden

Alla fraser ligger i `phrases.py` (`GUIDANCE_PHRASES`, `AIM_PHRASES`). Motorn säger bara **var koden ligger i bilden**, och konventionen avgör orden:

| Koden ligger | `--sikte huvud` (vrid huvudet) | `--sikte hand` (flytta varan) |
|---|---|---|
| till vänster | "Lite åt vänster." | "Lite åt höger." |
| till höger | "Lite åt höger." | "Lite åt vänster." |
| ovanför mitten | "Lite uppåt." | "Lite nedåt." |
| under mitten | "Lite nedåt." | "Lite uppåt." |

**Öppen fråga till Elias:** vilken konvention ska gälla? Kameran sitter på huvudet, så `huvud` är standard. Välj **en** och håll fast vid den.

Fasta fraser **och varunamnen i kartan** (med `info`) genereras i förväg med `python3 tts_engine.py --prewarm` (utan att kameran är igång: Pi:n har dött av strömbrist när båda körts samtidigt). Kör den igen när kartan ändras. Annars genereras ett nytt namn första gången det sägs (~0,5 s). Vid start skriver skannern hur många fraser som finns i cachen.

**Mer om varan:** fältet `info` i `kartor/produkter.geojson` är valfritt, text eller lista med högst 2 delar på högst 40 tecken, till exempel `"info": ["140 gram", "hylla 3"]`. Varje ord kostar tid innan användaren kan gå vidare, så bara det viktigaste ska vara med. För lång info stoppar starten med en förklaring i stället för att läsas upp.

## Länken till andra program

Syftet: en separat tjänst (t.ex. i C#) ska kunna bygga applikationslogik ovanpå, utan att röra kameran eller de uppmätta delarna. **Python äger kameran, avkodningen och filtren.**

`python3 barcode_scanner.py --lank 5555` öppnar `127.0.0.1:5555`. Protokollet är **JSON-rader** (en händelse eller ett kommando per rad, `\n` som avskiljare, UTF-8), version 1.

**Ut (skanner → klient):**

```json
{"type":"hello","protocol":1}
{"type":"read","t":1792339713.273,"mode":"4k","ean":"7311043006847","px_per_modul":3.02,"hojd_andel":0.64,"distance_m":0.276,"filter":[],"hornen":[[1449,1432],[1755,1432],[1755,1652],[1449,1652]],"bild":[3840,2160], ...}
{"type":"guidance","t":1792339713.8,"action":"confirmed","ean":"7311043006847","name":"Kaffefilter","text":"Kaffefilter."}
{"type":"error","reason":"..."}
```

- `read`: loggraden för varje avläsning, oförändrad (fälten står i `HANDOFF.md` avsnitt 3 och i `barcode_scanner.py`). `filter` kan innehålla `tunn` och `orimligt djup`.
- `guidance`: det Pythons egen motor beslutat. `action` är en av `confirmed`, `unknown_product`, `closer`, `code_left`, `code_right`, `code_above`, `code_below`, `hold_still`, `no_code`, `no_code_turn`, `no_code_distance`, `ready`, `code_seen` (pipet, `text` är "♪"). Vid `confirmed` finns även `details` och `basket` (`added` eller `already`; annars `null`). Skickas bara när `--vagledning` är på.
- `error`: svar på ett felaktigt kommando.

**In (klient → skanner), bara ett kommando:**

```json
{"cmd":"say","text":"Lite närmare."}
```

Texten (1–120 tecken, inga styrtecken) läses upp via `audio_manager` på **nivå 3**, alltså under akutlarm och Gemini. Ett externt program kan aldrig utlösa eller klippa ett akutlarm.

**Beteende och gränser**
- Lyssnar **bara på localhost**. Andra adresser vägras i koden. Ingen autentisering (onödig på localhost).
- En klient som inte hänger med (skrivning tar över 0,2 s) kopplas bort, så kameraloopen blockeras aldrig.
- Flera klienter går bra, alla får samma händelser.
- Ändras protokollet höjs `protocol` i `hello`.

**Att ta över vägledningen i C#:** kör `--lank 5555` **utan** `--vagledning`. Då skickar Python bara `read`-händelser, och C# bestämmer vad som sägs och skickar `say`. Pythons `GuidanceEngine` är då **specifikationen**: reglerna ovan, `tests/test_engine.py` (varje regel är ett testfall) och `replay.py` (kör en regeluppsättning mot ~1 500 verkliga läsningar). Portar reglerna och ta samma testfall.

**Ska stanna i Python oavsett:** kamera och avkodning (uppmätta med zxing-cpp, en annan avkodare ger andra gränser), filtren i `scan_filters.py`, och allt som rör **säkerhet** (hinder, bilar, trappor), som ska vara lokalt och snabbt och inte bero på att ett annat program lever.

## Köra och testa

```bash
# Enhetstester (kräver varken kamera eller Pi: ~100 tester, ~2 s)
python3 -m unittest discover -s tests -t .

# Vad hade vägledningen sagt under gamla körningar? Visar framför allt om den hade sagt FEL vara:
python3 -m voice_guidance.replay logs/scan_*.jsonl --karta kartor/produkter.geojson
# (avslutar med felkod 1 om någon bekräftelse hade varit fel)
# Prova andra trösklar utan att ändra koden:
python3 -m voice_guidance.replay logs/scan_*.jsonl --karta kartor/produkter.geojson --satt lost_after_s=8 --satt min_interval_s=2.5

# På Pi:n, i den här ordningen:
python3 tts_engine.py --prewarm                                   # utan kameran igång
python3 barcode_scanner.py --diag --4k --facit <EAN> --vagledning text   # först bara utskrift
python3 barcode_scanner.py --diag --4k --facit <EAN> --vagledning tal    # sedan med röst
```

## Kända begränsningar och risker

- **Inte körd på Pi:n.** Allt är testat med låtsaskamera, äkta streckkoder skapade av zxing-cpp och påhittade loggar. Trösklarna är startvärden från mätningarna och ska justeras mot riktiga körningar.
- **Konfliktradien (0,10) är ett kvalificerat antagande.** För liten missar konflikter när varan rör sig. För stor kan två grannvaror på en hylla räknas som en konflikt. Ingen mätning av hyllor än: justera efter butiksbesöket och med `replay`.
- **Ingen pip.** Förslaget nämnde pip plus namn. Namnet räcker som bekräftelse, och en pip kräver ljudstöd i `audio_manager` som inte finns. Kan läggas till senare.
- **Rösten kan bara guida mot en kod den ser.** När ingen kod syns ger den bara allmänna tips (håll i mitten, vänd, 30 cm), inte åt vilket håll. Riktning utan läsbar kod kräver fokusområde (B2 i `docs/Vision5_forslag_kodandring_2026-10-20.pdf`) eller en detektor som hittar koden utan att avkoda den. "Hittar ingen streckkod" kan inte prövas med `replay`, eftersom loggarna bara har bildrutor där en kod lästes.
- **Mitten av en tunn läsning** är mitten av remsan som avkodades, inte av hela koden. Riktningen kan därför vara något förskjuten.
- **Ljudkön spelar upp gamla besked** upp till 4 s efter att de köats (nivå 3). Vid långsam syntes kan ett besked komma när läget ändrats. Motorns takt (1,5 s) gör det osannolikt.
- **Fokuslås (B1) och fokusområde på koden (B2)** i `docs/Vision5_forslag_kodandring_2026-10-20.pdf` är inte byggda. Höjd- och djupfiltren finns i `scan_filters.py`.
- **Okänd vara** sägs för allt som inte finns i `kartor/produkter.geojson`. Med bara två varor i kartan blir det ofta. Butikens riktiga sortiment kopplas in via `ProductCatalog`.
