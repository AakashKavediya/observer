import React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: "default" | "highlight" | "bordered";
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  variant = "default",
  ...props
}) => {
  const variantStyles = {
    default: "bg-panel border border-black/5 shadow-calm",
    highlight: "bg-sage-pale/40 border border-sage/20 shadow-calm",
    bordered: "bg-panel border-2 border-sage/30 shadow-sm",
  };

  return (
    <div
      className={`rounded-card p-6 transition-all duration-200 ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
