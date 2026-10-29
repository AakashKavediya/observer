import React from "react";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "accent" | "highlight";
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = "default", className = "" }) => {
  const styles = {
    default: "bg-sage-pale text-ink border border-sage/20",
    accent: "bg-clay-pale text-clay border border-clay/30 font-medium",
    highlight: "bg-sage text-white font-medium",
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs ${styles[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
