import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock Web Speech API SpeechSynthesis for headless testing environment
if (typeof window !== "undefined") {
  if (!window.speechSynthesis) {
    (window as any).speechSynthesis = {
      speak: vi.fn(),
      cancel: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      getVoices: vi.fn().mockReturnValue([
        { name: "Default System Voice", lang: "en-US", default: true },
      ]),
      speaking: false,
      paused: false,
      pending: false,
      onvoiceschanged: null,
    };
  }

  if (!(window as any).SpeechSynthesisUtterance) {
    (window as any).SpeechSynthesisUtterance = class {
      text: string = "";
      rate: number = 1;
      pitch: number = 1;
      volume: number = 1;
      voice: any = null;
      onstart: any = null;
      onend: any = null;
      onerror: any = null;
      constructor(text?: string) {
        if (text) this.text = text;
      }
    };
  }
}
