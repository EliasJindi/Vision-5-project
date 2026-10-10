from google import genai
from PIL import Image
import os
import concurrent.futures

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
            self.client = genai.Client(api_key=api_key)
            print("✅ Gemini AI-Service (Modern SDK v2.5) har initierats framgångsrikt.")
        else:
            self.client = None
            print("⚠️ VARNING: Miljövariabeln GEMINI_API_KEY hittades inte i gemini_service.py.")

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
        
        if not self.client:
            print("❌ [GeminiService] API-nyckeln saknas. Avbryter.")
            return error_response

        # 1. Välj rätt prompt utifrån läge
        if mode == "navigation":
            prompt = (
                "Du är en navigationsassistent för en synskadad person som rör sig. "
                "Ge ett EXTREMT kort svar på svenska (MAX 10-12 ord). "
                "Prioritera ENBART: trappor, nivåskillnader, dörröppningar eller akuta hinder i gångvägen. "
                "TOTALFÖRBUD: Beskriv ALDRIG väggfärger, fönster, krukväxter, tavlor eller bakgrundsdekor. "
                "Om gångvägen är helt fri, svara bara: 'Fri väg framåt.' "
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
                # Använd en tråd-pool för att tvinga fram en timeout på 10 sekunder
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._make_api_call, pil_img, prompt)
                    
                    # Väntar max 10.0 sekunder, annars kastas TimeoutError
                    response = future.result(timeout=10.0)

                # Säkerhetskontroll: Om filtren blockerade svaret eller nätverket returnerade tomt
                if not response or not response.text:
                    print("⚠️ [GeminiService] Varning: Tomt svar eller blockerat av säkerhetsfilter.")
                    return "Svaret blockerades." if mode == "describe" else None
                
                return response.text.strip()
                
        except concurrent.futures.TimeoutError:
            print("⏳ [GeminiService] Nätverkstimeout! Gemini tog för lång tid (över 10s).")
            return "Nätverksproblem, dålig täckning." if mode == "describe" else None
            
        except ValueError as ve:
            print(f"🛡️ [GeminiService] Blockerat svar (Safety/Filter): {ve}")
            return "Analysen blockerades av ett filter." if mode == "describe" else None
            
        except Exception as e:
            print(f"❌ [GeminiService] Kritiskt nätverks- eller API-fel: {e}")
            return "Kunde inte nå nätverket." if mode == "describe" else None