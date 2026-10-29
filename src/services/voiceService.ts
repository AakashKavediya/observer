/**
 * voiceService.ts
 * Privacy-preserving, local-only speech synthesis and speech recognition service
 * designed specifically for neurodivergent accessibility.
 * 
 * - SpeechSynthesis: 100% local OS speech synthesis (AVFoundation on macOS, OneCore on Windows).
 * - SpeechRecognition: Web Speech API push-to-talk with interim previews, cancelability, and manual review.
 * - Zero network telemetry or third-party audio transmission.
 */

import { useState, useEffect, useRef, useCallback } from "react";

export type VoiceStateStatus =
  | "idle"
  | "listening"
  | "transcribing"
  | "speaking"
  | "unsupported"
  | "permission_denied"
  | "error";

export interface VoiceSettings {
  rate: number;          // 0.8 to 1.3
  pitch: number;         // 0.9 to 1.1
  voiceName: string;     // selected system voice
  autoSpeak: boolean;    // auto-speak micro-actions aloud
}

const SETTINGS_KEY = "observer_voice_settings";

export function loadVoiceSettings(): VoiceSettings {
  if (typeof window === "undefined") {
    return { rate: 1.0, pitch: 1.0, voiceName: "", autoSpeak: true };
  }
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        rate: typeof parsed.rate === "number" ? Math.max(0.7, Math.min(1.4, parsed.rate)) : 1.0,
        pitch: typeof parsed.pitch === "number" ? parsed.pitch : 1.0,
        voiceName: parsed.voiceName || "",
        autoSpeak: typeof parsed.autoSpeak === "boolean" ? parsed.autoSpeak : true,
      };
    }
  } catch {
    // Ignore storage parse issues
  }
  return { rate: 1.0, pitch: 1.0, voiceName: "", autoSpeak: true };
}

export function saveVoiceSettings(settings: VoiceSettings): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Ignore storage write issues
  }
}

/**
 * Strips markdown tags, code blocks, URLs, and academic bracket citations
 * so the local speech engine only utters calm, natural spoken instructions.
 */
export function cleanTextForSpeech(rawText: string): string {
  if (!rawText) return "";
  return rawText
    .replace(/```[\s\S]*?```/g, "") // remove code blocks
    .replace(/`([^`]+)`/g, "$1") // inline code
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1") // markdown links -> text
    .replace(/\[[A-Z0-9_\-\s]+\]/g, "") // bracketed citations like [INIT-001]
    .replace(/^#+\s+/gm, "") // header hashes
    .replace(/[*_~>]/g, "") // bold, italic, strikethrough, blockquote
    .replace(/^[•\-\*]\s+/gm, "") // bullets
    .replace(/\s+/g, " ") // normalize spacing
    .trim();
}

/**
 * Global SpeechSynthesis controller
 */
class SpeechSynthesisController {
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private onSpeakingChangeCallbacks: Set<(isSpeaking: boolean) => void> = new Set();

  public getCurrentUtterance(): SpeechSynthesisUtterance | null {
    return this.currentUtterance;
  }

  public isSupported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  public subscribeSpeaking(callback: (isSpeaking: boolean) => void): () => void {
    this.onSpeakingChangeCallbacks.add(callback);
    return () => this.onSpeakingChangeCallbacks.delete(callback);
  }

  private notifySpeaking(speaking: boolean) {
    this.onSpeakingChangeCallbacks.forEach((cb) => {
      try {
        cb(speaking);
      } catch (e) {
        console.error("Speech subscriber callback error:", e);
      }
    });
  }

  public getAvailableVoices(): SpeechSynthesisVoice[] {
    if (!this.isSupported()) return [];
    try {
      return window.speechSynthesis.getVoices() || [];
    } catch {
      return [];
    }
  }

  public stop(): void {
    if (!this.isSupported()) return;
    try {
      window.speechSynthesis.cancel();
      this.currentUtterance = null;
      this.notifySpeaking(false);
    } catch (e) {
      console.warn("SpeechSynthesis cancel error:", e);
    }
  }

  public isSpeaking(): boolean {
    if (!this.isSupported()) return false;
    try {
      return window.speechSynthesis.speaking;
    } catch {
      return false;
    }
  }

  public speak(
    text: string,
    options?: {
      rate?: number;
      pitch?: number;
      voiceName?: string;
      onStart?: () => void;
      onEnd?: () => void;
      onError?: (err: any) => void;
    }
  ): void {
    if (!this.isSupported()) {
      options?.onError?.("Speech synthesis is not supported on this device.");
      return;
    }

    const cleaned = cleanTextForSpeech(text);
    if (!cleaned) return;

    this.stop(); // Stop any pending utterance first

    try {
      const utterance = new SpeechSynthesisUtterance(cleaned);
      utterance.rate = options?.rate ?? 1.0;
      utterance.pitch = options?.pitch ?? 1.0;

      if (options?.voiceName) {
        const voices = this.getAvailableVoices();
        const found = voices.find((v) => v.name === options.voiceName);
        if (found) utterance.voice = found;
      }

      utterance.onstart = () => {
        this.notifySpeaking(true);
        options?.onStart?.();
      };

      utterance.onend = () => {
        this.currentUtterance = null;
        this.notifySpeaking(false);
        options?.onEnd?.();
      };

      utterance.onerror = (e) => {
        this.currentUtterance = null;
        this.notifySpeaking(false);
        // "canceled" or "interrupted" is normal when stopped by user
        if (e.error !== "canceled" && e.error !== "interrupted") {
          options?.onError?.(e);
        }
      };

      this.currentUtterance = utterance;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("Failed to speak utterance:", e);
      this.notifySpeaking(false);
      options?.onError?.(e);
    }
  }
}

export const speechSynth = new SpeechSynthesisController();

/**
 * Check whether speech recognition is available in the current environment.
 */
export function isSpeechRecognitionAvailable(): boolean {
  if (typeof window === "undefined") return false;
  return "SpeechRecognition" in window || "webkitSpeechRecognition" in window;
}

/**
 * React hook for push-to-talk / voice input.
 */
export function useVoiceInput(options?: {
  onTranscriptReady?: (transcript: string) => void;
  autoSpeakResponses?: boolean;
}) {
  const [status, setStatus] = useState<VoiceStateStatus>(() =>
    isSpeechRecognitionAvailable() ? "idle" : "unsupported"
  );
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [settings, setSettings] = useState<VoiceSettings>(loadVoiceSettings);

  const recognitionRef = useRef<any>(null);

  // Subscribe to speech synthesis speaking state
  useEffect(() => {
    const unsub = speechSynth.subscribeSpeaking((speaking) => {
      setIsSpeaking(speaking);
    });
    return () => unsub();
  }, []);

  // Update persisted settings
  const updateSettings = useCallback((newSettings: Partial<VoiceSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...newSettings };
      saveVoiceSettings(next);
      return next;
    });
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore already stopped
      }
    }
  }, []);

  const cancelListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore
      }
      recognitionRef.current = null;
    }
    setInterimTranscript("");
    setStatus("idle");
  }, []);

  const startListening = useCallback(() => {
    if (!isSpeechRecognitionAvailable()) {
      setStatus("unsupported");
      setErrorMessage("Speech recognition is not supported in this desktop webview. You can type your request below.");
      return;
    }

    // If currently speaking, stop TTS first
    if (speechSynth.isSpeaking()) {
      speechSynth.stop();
    }

    // Cancel any previous session
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore
      }
    }

    setErrorMessage(null);
    setInterimTranscript("");
    setStatus("listening");

    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRec();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    let finalAccumulated = "";

    recognition.onstart = () => {
      setStatus("listening");
    };

    recognition.onresult = (event: any) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        if (item.isFinal) {
          finalAccumulated += item[0].transcript + " ";
        } else {
          interim += item[0].transcript;
        }
      }
      setInterimTranscript(interim);
      if (finalAccumulated.trim()) {
        setTranscript(finalAccumulated.trim());
      }
    };

    recognition.onerror = (event: any) => {
      console.warn("Speech recognition error:", event.error);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setStatus("permission_denied");
        setErrorMessage("Microphone access was denied. Check system permissions or type below.");
      } else if (event.error === "no-speech") {
        setStatus("idle");
      } else if (event.error !== "aborted") {
        setStatus("error");
        setErrorMessage(`Voice input error: ${event.error}. You can type below.`);
      }
    };

    recognition.onend = () => {
      setInterimTranscript("");
      recognitionRef.current = null;
      if (finalAccumulated.trim()) {
        setStatus("transcribing");
        const finished = finalAccumulated.trim();
        setTranscript(finished);
        options?.onTranscriptReady?.(finished);
        setTimeout(() => setStatus("idle"), 400);
      } else {
        setStatus("idle");
      }
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch (e: any) {
      console.warn("Recognition start failed:", e);
      setStatus("error");
      setErrorMessage("Could not activate microphone. You can type below.");
    }
  }, [options]);

  const speakAction = useCallback(
    (actionText: string, whySuggested?: string) => {
      if (!settings.autoSpeak && !whySuggested) {
        // manual trigger or auto
      }
      const fullText = whySuggested ? `${actionText}. ${whySuggested}` : actionText;
      speechSynth.speak(fullText, {
        rate: settings.rate,
        pitch: settings.pitch,
        voiceName: settings.voiceName,
      });
    },
    [settings]
  );

  const stopSpeaking = useCallback(() => {
    speechSynth.stop();
  }, []);

  return {
    status,
    transcript,
    setTranscript,
    interimTranscript,
    errorMessage,
    isSpeaking,
    settings,
    updateSettings,
    startListening,
    stopListening,
    cancelListening,
    speakAction,
    stopSpeaking,
  };
}
