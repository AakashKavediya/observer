import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InterventionSurface } from "@/screens/InterventionSurface";
import { InterventionEvent } from "@/types/ipc";
import { useObserverStore } from "@/store/useObserverStore";

describe("Intervention Surface Component", () => {
  const mockIntervention: InterventionEvent = {
    schema_version: "1.0.0",
    type: "intervention",
    tier: 2,
    id: "test_intv_001",
    text: "That looks stuck. Want a tiny first step? Totally optional.",
    actions: [
      { id: "tiny_step", label: "Tiny step" },
      { id: "rest_bit", label: "Rest a bit" },
      { id: "not_now", label: "Not now" },
    ],
  };

  it("renders non-blaming warm validating text and action choices", () => {
    render(<InterventionSurface intervention={mockIntervention} />);

    expect(
      screen.getByText("That looks stuck. Want a tiny first step? Totally optional.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tiny step" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rest a bit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not now" })).toBeInTheDocument();
  });

  it("dismisses intervention on close button click", () => {
    useObserverStore.setState({ activeIntervention: mockIntervention });
    render(<InterventionSurface intervention={mockIntervention} />);

    const closeBtn = screen.getByLabelText("Dismiss check-in");
    fireEvent.click(closeBtn);

    expect(useObserverStore.getState().activeIntervention).toBeNull();
  });
});
