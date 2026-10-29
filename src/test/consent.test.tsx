import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WelcomeConsentScreen } from "@/screens/WelcomeConsentScreen";
import { useObserverStore } from "@/store/useObserverStore";

describe("Consent Gating and Welcome Screen", () => {
  it("disables Get Started button until user checks I understand", () => {
    render(<WelcomeConsentScreen />);
    const submitButton = screen.getByRole("button", { name: /get started/i });
    expect(submitButton).toBeDisabled();

    const understandCheckbox = screen.getByRole("checkbox", {
      name: /i understand that observer runs locally/i,
    });
    expect(understandCheckbox).not.toBeChecked();

    fireEvent.click(understandCheckbox);
    expect(understandCheckbox).toBeChecked();
    expect(submitButton).not.toBeDisabled();
  });

  it("updates store state upon consent submission", () => {
    render(<WelcomeConsentScreen />);
    const understandCheckbox = screen.getByRole("checkbox", {
      name: /i understand that observer runs locally/i,
    });
    const submitButton = screen.getByRole("button", { name: /get started/i });

    fireEvent.click(understandCheckbox);
    fireEvent.click(submitButton);

    const state = useObserverStore.getState();
    expect(state.consentGiven).toBe(true);
    expect(state.activeScreen).toBe("home");
  });
});
