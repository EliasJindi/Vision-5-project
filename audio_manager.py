import queue
import threading
import subprocess
import time

class AudioManager:
    def __init__(self):
        # Skapa en trådsäker prioriteringskö
        self.queue = queue.PriorityQueue()
        
        # Håll koll på om en lägre prioriterad ljudfil spelas just nu
        self.current_process = None
        self.current_priority = 99
        
        # Sökvägar till din lokala Piper-installation
        self.piper_path = "./piper/piper"
        self.model_path = "sv_SE-alma-medium.onnx"
        
        # Starta bakgrundstråden som hanterar kön
        self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.worker_thread.start()

    def speak(self, text: str, priority: int = 3):
        """
        Lägg till ett meddelande i kön.
        Priority: 1 = Akut (hinder/personer), 2 = Navigering, 3 = OCR/Gemini (standard)
        """
        print(f"🔊 [AudioQueue] Lägger till nivå {priority}: '{text}'")
        
        # Om ett akut meddelande (Nivå 1) kommer in, och vi just nu spelar något med lägre prioritet (t.ex. Nivå 3)
        if priority == 1 and self.current_priority > 1 and self.current_process:
            print("🚨 [AudioQueue] AKUT VARNING! Klipper pågående lågprioriterat ljud.")
            self.stop_current()

        # Lägg till i kön (PriorityQueue sorterar på första elementet i tuppeln)
        self.queue.put((priority, text))

    def stop_current(self):
        """Tvingar Piper att tystna direkt om det körs."""
        if self.current_process:
            try:
                self.current_process.terminate() # Dödar piper-processen direkt
                self.current_process = None
            except Exception as e:
                print(f"Kunde inte stänga av ljudprocess: {e}")

    def _audio_worker(self):
        """Bakgrundstråd som plockar meddelanden ur kön ett efter ett."""
        while True:
            try:
                # Hämta nästa meddelande från kön
                priority, text = self.queue.get()
                
                self.current_priority = priority
                
                # KORRIGERAT: Använder dina exakta sökvägar och pw-play för PipeWire
                command = f"echo '{text}' | {self.piper_path} --model {self.model_path} --output_file - | pw-play -" 
                
                # Starta uppläsningen
                self.current_process = subprocess.Popen(command, shell=True)
                
                # Vänta tills Piper har pratat färdigt
                self.current_process.wait()
                
                # Återställ status när ljudet är klart
                self.current_process = None
                self.current_priority = 99
                
                # Markera uppgiften som klar i kön
                self.queue.task_done()
                
            except Exception as e:
                print(f"Fel i audio worker: {e}")
                time.sleep(0.1)

# Skapa en global instans som alla filer kan dela på
audio_system = AudioManager()