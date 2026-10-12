# ===================== ÄNDRINGAR AV CLAUDE (2026-10-10) =====================
# - __init__(): timeout i HttpOptions (10 000 ms). Den gamla ThreadPoolExecutor-timeouten
#   fungerade inte: with-blocket väntade ändå tills anropet var klart.
# - Navigationsprompten: säger ALDRIG "Fri väg framåt", svarar INGET -> systemet är tyst.
# - last_ok/last_error: så att telemetrin loggar fel ärligt (503 räknades som lyckat).
# - 503/429 ger "Tjänsten är upptagen" i knappläget.
# =============================================================================
from google import genai
from google.genai import types
from PIL import Image
import os

# Max väntetid på Gemini. OBS: HttpOptions.timeout är i MILLISEKUNDER.
GEMINI_TIMEOUT_MS = 10_000

class GeminiService:
    """
    ANSVAR: Hanterar all direkt kommunikation med Google Gemini API,
    formaterar prompten beroende på om det är automatisk navigation
    eller manuell knapptryckning, med stenhård timeout.
    """
    def __init__(self):
        # Hämta API-nyckeln från operativsystemets miljövariabler
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            # Modern SDK-initialisering
            # Timeouten måste sitta i HTTP-klienten. En timeout på en tråd-future
            # avbryter inte själva anropet (se commit-meddelandet).
            self.client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS),
            )
            print("✅ Gemini AI-Service (Modern SDK v2.5) har initierats framgångsrikt.")
        else:
            self.client = None
            print("⚠️ VARNING: Miljövariabeln GEMINI_API_KEY hittades inte i gemini_service.py.")

    # Status för senaste anropet, så att telemetrin kan logga misslyckanden ärligt
    last_ok = False
    last_error = None

    def _make_api_call(self, pil_img, prompt):
        """Hjälpmetod för att kunna lägga en timeout på nätverksanropet."""
        return self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[pil_img, prompt]
        )

    def analyze_frame(self, image_path, mode="navigation"):
        """
        Tar emot en sökväg till en sparad bild och ett läge.
        Returnerar en textsträng att läsa upp, eller None om anropet misslyckas tyst.
        """
        # Returnera kortfattade fel om det är manuellt (describe), annars var tyst (navigation)
        error_response = "Systemfel. API-nyckel saknas." if mode == "describe" else None
        self.last_ok = False
        self.last_error = None

        if not self.client:
            self.last_error = "no_api_key"
            print("❌ [GeminiService] API-nyckeln saknas. Avbryter.")
            return error_response

        # 1. Välj rätt prompt utifrån läge
        if mode == "navigation":
            prompt = (
                "Du är en navigationsassistent för en synskadad person som rör sig. "
                "Ge ett EXTREMT kort svar på svenska (MAX 10-12 ord). "
                "Prioritera ENBART: trappor, nivåskillnader, dörröppningar eller akuta hinder i gångvägen. "
                "TOTALFÖRBUD: Beskriv ALDRIG väggfärger, fönster, krukväxter, tavlor eller bakgrundsdekor. "
                "Om du inte ser något sådant hinder, svara exakt: INGET "
                "(säg ALDRIG att vägen är fri, du ser inte allt). "
                "VIKTIGT: Returnera ENBART ren text utan Markdown eller asterisker."
            )
        else:  # mode == "describe" (Klick på knappen)
            prompt = (
                "Du är röstassistenten Alma i ett par smarta AI-glasögon för blinda. "
                "Användaren har tryckt på knappen för en beskrivning av omgivningen. "
                "Ge ett koncist och naturligt svar på svenska (max 2-3 meningar). "
                "Prioritera att läsa upp viktig text som skyltar, produktnamn eller priser. "
                "Om ingen text finns, beskriv kort vad du ser framför användaren (möbler, rum, miljö). "
                "VIKTIGT: Returnera ENBART ren text utan Markdown eller asterisker."
            )

        try:
            with Image.open(image_path) as pil_img:
                # Avbryts av HTTP-klienten efter GEMINI_TIMEOUT_MS
                response = self._make_api_call(pil_img, prompt)

                # Säkerhetskontroll: Om filtren blockerade svaret eller nätverket returnerade tomt
                if not response or not response.text:
                    print("⚠️ [GeminiService] Varning: Tomt svar eller blockerat av säkerhetsfilter.")
                    self.last_error = "empty"
                    return "Svaret blockerades." if mode == "describe" else None

                self.last_ok = True
                answer = response.text.strip()
                # Navigationsläget ska vara tyst när inget hinder syns
                if mode == "navigation" and answer.strip(" .").upper() == "INGET":
                    return None
                return answer

        except ValueError as ve:
            print(f"🛡️ [GeminiService] Blockerat svar (Safety/Filter): {ve}")
            self.last_error = "blocked"
            return "Analysen blockerades av ett filter." if mode == "describe" else None

        except Exception as e:
            # Timeout (httpx.TimeoutException), inget nät, 503/429 från Google m.m. hamnar här
            msg = str(e)
            if "timeout" in type(e).__name__.lower() or "timed out" in msg.lower():
                print("⏳ [GeminiService] Nätverkstimeout! Gemini tog för lång tid.")
                self.last_error = "timeout"
                return "Nätverksproblem, dålig täckning." if mode == "describe" else None
            if msg.startswith(("503", "429")) or "UNAVAILABLE" in msg or "RESOURCE_EXHAUSTED" in msg:
                # Nätet fungerar, men Googles tjänst är överbelastad eller vi har nått gränsen
                print(f"🚦 [GeminiService] Tjänsten är upptagen: {msg[:80]}")
                self.last_error = msg[:3]
                return "Tjänsten är upptagen. Försök igen strax." if mode == "describe" else None
            print(f"❌ [GeminiService] Kritiskt nätverks- eller API-fel: {e}")
            self.last_error = type(e).__name__
            return "Kunde inte nå nätverket." if mode == "describe" else None
