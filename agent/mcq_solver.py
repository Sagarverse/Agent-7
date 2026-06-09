import time
import threading
from pynput import keyboard

from agent.brain import GeminiBrain
from controllers.screen import ScreenController
from controllers.mouse import MouseController
from controllers.system import SystemController
from config import Config
from rich.console import Console

console = Console()

class MCQSolver:
    def __init__(self, brain: GeminiBrain, screen: ScreenController, mouse: MouseController):
        self.brain = brain
        self.screen = screen
        self.mouse = mouse
        self.system = SystemController()
        
        self.correct_coordinates = []
        self.is_solving = False
        
        # Initialize Overlay Controller if enabled
        self.overlay = None
        if Config.MCQ_OVERLAY_ENABLED:
            try:
                from controllers.overlay import OverlayController
                self.overlay = OverlayController()
                self.overlay.start()
                console.print("[green]MCQ Solver: Overlay notification system initialized successfully.[/green]")
            except (ImportError, Exception) as e:
                console.print(f"[yellow]MCQ Solver: Overlay Controller could not be loaded ({e}). Notifications will fallback to macOS notification center.[/yellow]")
                self.overlay = None

    # ── Mode 1: Solve + Auto-Click ────────────────────────────
    def on_solve_and_click_request(self):
        """Triggered when Control + Command is pressed. Solves and auto-clicks."""
        if self.is_solving:
            console.print("[yellow]MCQ Solver: Already processing...[/yellow]")
            return
            
        self.is_solving = True
        
        is_ollama = self.brain._is_caps_lock_on() or Config.AI_PROVIDER == "ollama"
        provider = "Ollama (Local)" if is_ollama else "Gemini (Cloud)"
        self.system.notify("MCQ Solver", f"Processing via {provider}...")
        
        console.print(f"\n[bold cyan]MCQ Solver: Processing screen and auto-clicking via {provider}...[/bold cyan]")
        
        thread = threading.Thread(target=self._solve_and_click)
        thread.start()

    # ── Mode 2: Just Show Answer (No Click) ───────────────────
    def on_show_answer_request(self):
        """Triggered when Control + Option is pressed. Shows answer only, no clicking."""
        if self.is_solving:
            console.print("[yellow]MCQ Solver: Already processing...[/yellow]")
            return
            
        self.is_solving = True
        
        is_ollama = self.brain._is_caps_lock_on() or Config.AI_PROVIDER == "ollama"
        provider = "Ollama (Local)" if is_ollama else "Gemini (Cloud)"
        self.system.notify("MCQ Solver", f"Analyzing via {provider}...")
        
        console.print(f"\n[bold magenta]MCQ Solver: Analyzing screen via {provider}...[/bold magenta]")
        
        thread = threading.Thread(target=self._show_answer_only)
        thread.start()

    def _take_fresh_screenshot_bytes(self) -> bytes:
        """Always capture a NEW screenshot and return its bytes."""
        fresh_screenshot = self.screen.capture_screenshot(save=False)
        return self.screen.screenshot_to_bytes(screenshot=fresh_screenshot)

    def _solve_mcq(self) -> dict | None:
        """Common logic: take a fresh screenshot and solve the MCQ."""
        screenshot_bytes = self._take_fresh_screenshot_bytes()
        result = self.brain.solve_mcq_on_screen(screenshot_bytes)
        return result

    def _solve_and_click(self):
        """Solve the MCQ and auto-click the correct answers."""
        try:
            result = self._solve_mcq()
            
            if not result or not result.get("found"):
                console.print("[red]MCQ Solver: No MCQ found or failed to parse.[/red]")
                self.system.notify("MCQ Solver", "No multiple choice question found on screen.")
                if self.overlay:
                    self.overlay.show("No MCQ found on screen.")
                    threading.Timer(Config.MCQ_OVERLAY_DURATION, self.overlay.hide).start()
                return
                
            # Store coordinates and display summary
            self.correct_coordinates = []
            for opt in result.get("correct_options", []):
                x = opt.get("x")
                y = opt.get("y")
                if x is not None and y is not None:
                    self.correct_coordinates.append((x, y))
                    
            summary = result.get("summary_text", "Done")
            confidence = result.get("confidence", 1.0)
            reasoning = result.get("reasoning", "")
            
            console.print(f"\n[bold green]━━━ MCQ Answer ━━━[/bold green]")
            console.print(f"[green]✅ {summary}[/green]")
            console.print(f"[cyan]Confidence: {confidence:.2f} (Threshold: {Config.MCQ_CONFIDENCE_THRESHOLD:.2f})[/cyan]")
            if reasoning:
                console.print(f"[dim]{reasoning[:300]}{'...' if len(reasoning) > 300 else ''}[/dim]")
            console.print(f"[bold green]━━━━━━━━━━━━━━━━━━[/bold green]")
            
            # Show on overlay
            if self.overlay:
                if hasattr(self, 'overlay_timer') and self.overlay_timer:
                    try:
                        self.overlay_timer.cancel()
                    except Exception:
                        pass
                self.overlay.show(f"Answer: {summary}\nConfidence: {confidence:.2f}")
                self.overlay_timer = threading.Timer(Config.MCQ_OVERLAY_DURATION, self.overlay.hide)
                self.overlay_timer.start()

            self.system.notify("MCQ Solver", f"Answer: {summary} (Conf: {confidence:.2f})")
            
            # Check confidence threshold
            if confidence < Config.MCQ_CONFIDENCE_THRESHOLD:
                console.print(f"[yellow]MCQ Solver: Confidence ({confidence:.2f}) is below threshold ({Config.MCQ_CONFIDENCE_THRESHOLD:.2f}). Skipping auto-clicking.[/yellow]")
                self.system.notify("MCQ Solver", "Low confidence. Skipping click.")
                return

            if not self.correct_coordinates:
                console.print("[yellow]MCQ Solver: Answer found but no clickable coordinates detected.[/yellow]")
                return
            
            # Auto-click the correct options with Retina scaling
            console.print("[cyan]MCQ Solver: Auto-clicking...[/cyan]")
            scale_x, scale_y = self.screen.get_retina_scale()
            for (x, y) in self.correct_coordinates:
                scaled_x = int(x * scale_x)
                scaled_y = int(y * scale_y)
                console.print(f"[dim]MCQ Solver: Clicking scaled coordinates ({scaled_x}, {scaled_y}) for raw ({x}, {y})[/dim]")
                self.mouse.move_to(scaled_x, scaled_y, duration=0.1)
                time.sleep(0.05)
                self.mouse.click(scaled_x, scaled_y)
                time.sleep(0.15)
                
            console.print("[green]MCQ Solver: Done! Answers selected.[/green]\n")
            
        except Exception as e:
            console.print(f"[red]MCQ Solver Error: {e}[/red]")
            self.system.notify("MCQ Solver", f"An error occurred: {e}")
            if self.overlay:
                self.overlay.show(f"Error: {e}")
        finally:
            self.is_solving = False

    def _show_answer_only(self):
        """Solve the MCQ and just display the answer — no clicking."""
        try:
            result = self._solve_mcq()
            
            if not result or not result.get("found"):
                console.print("[red]MCQ Solver: No MCQ found on screen.[/red]")
                self.system.notify("MCQ Solver", "No MCQ found on screen.")
                if self.overlay:
                    self.overlay.show("No MCQ found on screen.")
                    threading.Timer(Config.MCQ_OVERLAY_DURATION, self.overlay.hide).start()
                return
            
            summary = result.get("summary_text", "Done")
            confidence = result.get("confidence", 1.0)
            reasoning = result.get("reasoning", "")
            correct_options = result.get("correct_options", [])
            
            console.print(f"\n[bold magenta]━━━ MCQ Answer (View Only) ━━━[/bold magenta]")
            console.print(f"[bold green]✅ {summary}[/bold green]")
            console.print(f"[cyan]Confidence: {confidence:.2f}[/cyan]")
            if correct_options:
                for i, opt in enumerate(correct_options, 1):
                    text = opt.get("text", "?")
                    console.print(f"  [cyan]Option {i}:[/cyan] {text}")
            if reasoning:
                console.print(f"\n[dim]Reasoning: {reasoning[:500]}{'...' if len(reasoning) > 500 else ''}[/dim]")
            console.print(f"[bold magenta]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold magenta]\n")
            
            # Show on overlay
            if self.overlay:
                if hasattr(self, 'overlay_timer') and self.overlay_timer:
                    try:
                        self.overlay_timer.cancel()
                    except Exception:
                        pass
                self.overlay.show(f"Answer: {summary}\nConfidence: {confidence:.2f}")
                self.overlay_timer = threading.Timer(Config.MCQ_OVERLAY_DURATION, self.overlay.hide)
                self.overlay_timer.start()

            self.system.notify("MCQ Answer", f"{summary} (Conf: {confidence:.2f})")
            
        except Exception as e:
            console.print(f"[red]MCQ Solver Error: {e}[/red]")
            self.system.notify("MCQ Solver", f"An error occurred: {e}")
            if self.overlay:
                self.overlay.show(f"Error: {e}")
        finally:
            self.is_solving = False

    def start_listener(self):
        """Start listening for global hotkeys."""
        hotkey_map = {
            '<ctrl>+<cmd>': self.on_solve_and_click_request,
            '<ctrl>+<alt>': self.on_show_answer_request,
        }
        
        console.print("\n[bold yellow]━━━ MCQ Solver Hotkeys ━━━[/bold yellow]")
        console.print("[bold cyan]  Control + Command[/bold cyan]  →  Solve & auto-click the answer")
        console.print("[bold magenta]  Control + Option[/bold magenta]   →  Just show the answer (no click)")
        console.print("[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]\n")
        
        def start_hook():
            with keyboard.GlobalHotKeys(hotkey_map) as h:
                h.join()
                
        thread = threading.Thread(target=start_hook, daemon=True)
        thread.start()
