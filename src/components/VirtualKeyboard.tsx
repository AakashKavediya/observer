/**
 * VirtualKeyboard.tsx
 * Adapted from MotionQ-blink (keyboard_ui.py) for Observer.
 * 
 * Provides an accessible, on-screen virtual keyboard with:
 * - English, Hindi (Devanagari), and Marathi layouts.
 * - Word prediction bar with dwellable completion candidates.
 * - Dwell-registered keys and prediction targets.
 * - Native text typing via Tauri / CoreGraphics FFI.
 */

import React, { useEffect, useRef, useState } from "react";
import { useObserverStore } from "../store/useObserverStore";
import { X, Languages, CornerDownLeft, Delete } from "lucide-react";

const EN_LAYOUT = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["z", "x", "c", "v", "b", "n", "m", "⌫"],
  [" ", "↵"],
];

const HI_LAYOUT = [
  ["अ", "आ", "इ", "ई", "उ", "ऊ", "ए", "ऐ", "ओ", "औ"],
  ["क", "ख", "ग", "घ", "ङ", "च", "छ", "ज", "झ"],
  ["ट", "ठ", "ड", "ढ", "ण", "त", "थ", "द", "ध", "⌫"],
  [" ", "↵"],
];

const MR_LAYOUT = [
  ["अ", "आ", "इ", "ई", "उ", "ऊ", "ए", "ऐ", "ओ", "औ"],
  ["क", "ख", "ग", "घ", "ङ", "च", "छ", "ज", "झ"],
  ["ट", "ठ", "ड", "ढ", "ण", "त", "थ", "द", "ध", "⌫"],
  [" ", "↵"],
];

export const VirtualKeyboard: React.FC = () => {
  const {
    showVirtualKeyboard,
    toggleVirtualKeyboard,
    keyboardLanguage,
    cycleKeyboardLanguage,
    typeVirtualKey,
    fetchWordPredictions,
    motionqPredictions,
    registerDwellTarget,
  } = useObserverStore();

  const [inputBuffer, setInputBuffer] = useState("");
  const keyboardRef = useRef<HTMLDivElement>(null);

  const getLayout = () => {
    if (keyboardLanguage === "HI") return HI_LAYOUT;
    if (keyboardLanguage === "MR") return MR_LAYOUT;
    return EN_LAYOUT;
  };

  // Debounced prediction fetch on buffer change
  useEffect(() => {
    if (inputBuffer.length >= 1) {
      fetchWordPredictions(inputBuffer, keyboardLanguage);
    }
  }, [inputBuffer, keyboardLanguage]);

  // Register Dwell Targets for Keyboard Keys and Predictions
  useEffect(() => {
    if (!showVirtualKeyboard) return;

    const timer = setTimeout(() => {
      if (!keyboardRef.current) return;
      const keyButtons = keyboardRef.current.querySelectorAll<HTMLButtonElement>("[data-key-char]");
      
      keyButtons.forEach((btn) => {
        const rect = btn.getBoundingClientRect();
        const char = btn.getAttribute("data-key-char");
        if (!char) return;

        registerDwellTarget({
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          target_id: `key_${char}`,
          action: `type:${char}`,
          name: `Key ${char}`,
          duration_ms: 700,
        });
      });

      // Register predictions
      const predButtons = keyboardRef.current.querySelectorAll<HTMLButtonElement>("[data-pred-word]");
      predButtons.forEach((btn) => {
        const rect = btn.getBoundingClientRect();
        const word = btn.getAttribute("data-pred-word");
        if (!word) return;

        registerDwellTarget({
          x: Math.round(rect.left),
          y: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          target_id: `pred_${word}`,
          action: `pred:${word}`,
          name: `Word ${word}`,
          duration_ms: 700,
        });
      });
    }, 350);

    return () => {
      clearTimeout(timer);
    };
  }, [showVirtualKeyboard, keyboardLanguage, motionqPredictions]);

  if (!showVirtualKeyboard) {
    return null;
  }

  const handleKeyPress = async (char: string) => {
    if (char === "⌫") {
      await typeVirtualKey("backspace");
      setInputBuffer((prev) => prev.slice(0, -1));
    } else if (char === "↵") {
      await typeVirtualKey("enter");
      setInputBuffer("");
    } else if (char === " ") {
      await typeVirtualKey("space");
      setInputBuffer("");
    } else {
      await typeVirtualKey(char);
      setInputBuffer((prev) => prev + char);
    }
  };

  const handlePredictionSelect = async (word: string) => {
    // Type remaining characters
    const remaining = word.startsWith(inputBuffer) ? word.slice(inputBuffer.length) : word;
    for (const c of remaining) {
      await typeVirtualKey(c);
    }
    await typeVirtualKey(" ");
    setInputBuffer("");
  };

  const layout = getLayout();

  return (
    <div
      ref={keyboardRef}
      className="fixed bottom-3 left-1/2 -translate-x-1/2 z-50 flex flex-col bg-sand-light/95 dark:bg-panel border border-black/10 dark:border-white/10 rounded-2xl shadow-2xl backdrop-blur-md p-3 select-none animate-in fade-in slide-in-from-bottom-4 transition-all"
      style={{ maxWidth: "95vw", width: "720px" }}
    >
      {/* Top Header: Prediction Bar & Language / Close */}
      <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-black/5 dark:border-white/5">
        {/* Word Prediction Slots */}
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-[10px] font-bold uppercase tracking-wider text-ink-muted mr-1">Suggestions:</span>
          {motionqPredictions.length > 0 ? (
            motionqPredictions.slice(0, 3).map((word, idx) => (
              <button
                key={idx}
                data-pred-word={word}
                onClick={() => handlePredictionSelect(word)}
                className="px-3 py-1 bg-ivory dark:bg-black/20 hover:bg-sage/20 border border-black/10 rounded-lg text-xs font-semibold text-ink transition-all shadow-2xs hover:border-sage"
              >
                {word}
              </button>
            ))
          ) : (
            <span className="text-xs text-ink-muted italic">Type letters to see predictions...</span>
          )}
        </div>

        {/* Language & Close Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={cycleKeyboardLanguage}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-bold bg-ivory dark:bg-black/20 hover:bg-black/5 border border-black/10 text-ink transition-all"
            title="Switch Language"
          >
            <Languages className="w-3.5 h-3.5 text-sage" />
            <span>{keyboardLanguage}</span>
          </button>
          <button
            onClick={() => toggleVirtualKeyboard(false)}
            className="p-1 rounded-lg text-ink-muted hover:text-ink hover:bg-black/5 dark:hover:bg-white/5 transition-all ml-1"
            title="Dismiss Keyboard"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Keyboard Grid */}
      <div className="flex flex-col gap-1.5 items-center">
        {layout.map((row, rowIdx) => (
          <div key={rowIdx} className="flex gap-1.5 justify-center w-full">
            {row.map((char, colIdx) => {
              const isSpace = char === " ";
              const isEnter = char === "↵";
              const isBackspace = char === "⌫";

              return (
                <button
                  key={colIdx}
                  data-key-char={char}
                  onClick={() => handleKeyPress(char)}
                  className={`flex items-center justify-center font-bold rounded-xl border border-black/10 shadow-2xs transition-all active:scale-95 ${
                    isSpace
                      ? "flex-1 max-w-[260px] h-11 bg-ivory dark:bg-black/20 hover:bg-black/5 text-ink text-xs uppercase"
                      : isEnter
                      ? "w-20 h-11 bg-sage text-white hover:bg-sage-dark text-xs"
                      : isBackspace
                      ? "w-16 h-11 bg-terra/90 text-white hover:bg-terra text-xs"
                      : "w-12 h-11 bg-ivory dark:bg-black/20 hover:bg-sage/15 hover:border-sage text-ink text-base"
                  }`}
                >
                  {isSpace ? (
                    "SPACE"
                  ) : isEnter ? (
                    <span className="flex items-center gap-1">
                      <span>ENTER</span>
                      <CornerDownLeft className="w-3 h-3" />
                    </span>
                  ) : isBackspace ? (
                    <span className="flex items-center gap-1">
                      <Delete className="w-3.5 h-3.5" />
                    </span>
                  ) : (
                    char
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};
