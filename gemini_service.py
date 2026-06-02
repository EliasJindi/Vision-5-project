import google.generativeai as genai
from PIL import Image
import os

class GeminiService:
    """
    ANSVAR: Hanterar all direkt kommunikation med Google Gemini API,
    formaterar prompten och skickar bilder för intelligent analys.
    """
    def __init__(self):
        # Hämta API-nyckeln från operativsystemets miljövariabler
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            # FIX: Ändrat till en modern modell eftersom 1.5-flash har flyttats från v1beta-endpoints
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            print("✅ Gemini AI-Service har initierats framgångsrikt.")
        else:
            self.model = None
            print("⚠️ VARNING: Miljövariabeln GEMINI_API_KEY hittades inte i gemini_service.py.")

    def analyze_frame(self, image_path):
        """
        Tar emot en sökväg till en sparad bild, skickar den till Gemini
        och returnerar det färdiga textsvaret på svenska.
        """
        if not self.model:
            return "Fel: AI-tjänsten kunde inte startas eftersom API-nyckeln saknas."

        try:
            # PRINCIP: Resurshantering via Context Manager (with) stänger filen säkert efter läsning
            with Image.open(image_path) as pil_img:
                
                # PRINCIP: Robust prompt-engineering optimerad för Text-to-Speech (TTS)
                prompt = (
                    "Du är röstassistenten Alma i ett par smarta AI-glasögon for blinda. "
                    "Användaren har precis tryckt på en knapp för att be dig tolka miljön eller läsa text framför dem. "
                    "Titta på bilden och ge ett mycket kort, koncist och naturligt svar på svenska (max 2 meningar). "
                    "Prioritera att läsa upp viktig text som skyltar, produktnamn eller priser. "
                    "Om ingen text finns, beskriv kort det viktigaste föremålet direkt framför användaren. "
                    "Tala direkt till användaren (t.ex. 'Framför dig finns...' eller 'Du tittar på...'). "
                    "VIKTIGT: Returnera ENBART ren, rå text. Använd ALDRIG Markdown-formatering, "
                    "så som asterisker (**) för fetstil, hashtags eller listpunkter. Texten ska läsas upp direkt av en talsyntes."
                )

                response = self.model.generate_content([prompt, pil_img])
                return response.text.strip()
            
        except Exception as e:
            return f"Det gick inte att kontakta molnet. Felmeddelande: {e}"