# Arbetsloggar (nyast först)

Arbetsloggarna för Vision-5 efter varje testdag. Klicka på en fil för att läsa den. Siffror är märkta *uppmätt*, *beräknat* eller *hypotes* i varje logg.

| Datum | Logg | Innehåll |
|---|---|---|
| 11/11 2026 | [Vision5_avstandet_2026-11-11.pdf](Vision5_avstandet_2026-11-11.pdf) | 11/11: avståndsmätning med ättikan på stöd (30 cm: 97 och 95 % av bildrutorna godkända; 40 cm: 0 och 0 %; felläsningar bara vid gränsen, alla stoppade av höjdfiltret), rösttester i dagsljus med varorna på ca 30 cm (alla tre varorna lästes, ättikan 16 och 10 s), handmodellen 70–76 % i dagsljus, ändring 41 ("Håll varan nära, armbågen mot kroppen."), fel facit och nätverket, vad som är osäkert, nästa steg |
| 10/11 2026 | [Vision5_kvallsljus_2026-11-10.pdf](Vision5_kvallsljus_2026-11-10.pdf) | 10/11: fem rösttester i lampljus (0 läsningar av tre skäl: mörker, kameran för högt, motljus; sedan lästes tomatpurén mot en upplyst vägg), handmodellen 0–26 % i lampljus mot 72 % i dagsljus, 45 s tystnad efter "Redo" och ändring 40 ("Håll nästa vara framför dig." efter 5 s, fungerade på Pi:n), ättikan 150 s vid läsgränsen, Gemini och lätta hyllor först, nästa steg |
| 9/11 2026 | [Vision5_handmodellen_2026-11-09.pdf](Vision5_handmodellen_2026-11-09.pdf) | 7–9/11: detektorn och regel 3b, rösttester blundande (12 s), "Redo" efter 8 s, handmodellen (handflata ensam 16–55 % fel på bordet; med landmärkesmodellen 83 % och 83 % med vara, 0 % utan), förminskningsfelet, handmodellen i skannern, 33 s tystnad och ändring 39, vad som är osäkert, nästa steg |
| 7/11 2026 | [Vision5_handen_och_fokus_2026-11-07.pdf](Vision5_handen_och_fokus_2026-11-07.pdf) | 6–7/11: USB 3 och kontakten, kamerans vinkel (mosaikerna), "Sakta närmare."/"Håll stilla.", en läsning gav 4 fel namn, linstabellen, `--hand` 13–15 % mot 4 %, vad som är osäkert, nästa steg |
| 5/11 2026 | [Vision5_rostvagledning_pa_pi_2026-11-05.pdf](Vision5_rostvagledning_pa_pi_2026-11-05.pdf) | Röstvägledningen på Pi:n 4–5/11: vad som hände i varje prov, felsökningen av kamerakrascherna (Y-adaptern), ändringarna PR #19–#28, vad som är osäkert, nästa steg |
| 3/11 2026 | [Vision5_rostvagledning_2026-11-03.pdf](Vision5_rostvagledning_2026-11-03.pdf) | Arbetslogg 3/11: vad som byggdes och varför, arkitekturen, hur det är testat (99 tester, mutationskontroll), vad som inte är testat, nästa steg |
| 29/10 2026 | [Vision5_varutest_del2_2026-10-29.pdf](Vision5_varutest_del2_2026-10-29.pdf) | Varutest del 2 (4K): Coca-Cola med EAN-8 läser till 0,71 m, kaffefiltret rakt och stabilt ger inga fel. **Rättar flera slutsatser i del 1** |
| 29/10 2026 | [Vision5_varutest_kaffefilter_2026-10-29.pdf](Vision5_varutest_kaffefilter_2026-10-29.pdf) | Varutest del 1 (4K): kaffefilter med 22 felläsningar i en lutande, instabil uppställning, förslag på konfliktregel. Läs med rättelserna i del 2 |
| 27/10 2026 | [Vision5_filter_pa_pi_2026-10-27.pdf](Vision5_filter_pa_pi_2026-10-27.pdf) | Filtren på Pi:n: höjden mäter osäkerhet, inte rätt/fel; djupet fel bara första sekunden; hälften av bilderna når Pi:n |
| 20/10 2026 | [Vision5_forslag_kodandring_2026-10-20.pdf](Vision5_forslag_kodandring_2026-10-20.pdf) | Kodförslaget (del A filter, del B fokusstyrning) med testplan. Del A genomförd i PR #11, med ändringen att varan sägs utan position vid orimligt djup |
| 20/10 2026 | [Vision5_autofokus_hojdfilter_2026-10-20.pdf](Vision5_autofokus_hojdfilter_2026-10-20.pdf) | Autofokus och kodens placering (mitten 100 %, längst ner 0 %), lins 77 vid kanten, höjdfiltret på alla loggar |
| 18/10 2026 | [Vision5_fokustest_2026-10-18.pdf](Vision5_fokustest_2026-10-18.pdf) | Fokustestet: 19 körningar, linsfönster per avstånd, fast lins mot autofokus, första felaktiga djupet, första tunna felläsningen. USB-raden rättad 20/10 |

Röstvägledningens regler (ingen arbetslogg): [`docs/ROSTVAGLEDNING.md`](../ROSTVAGLEDNING.md). Hela bakgrunden: [`HANDOFF.md`](../../HANDOFF.md), avsnitt 11.
