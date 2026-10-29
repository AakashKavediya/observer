import React from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "subtle" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  size = "md",
  className = "",
  disabled = false,
  children,
  ...props
}) => {
  const baseStyles =
    "inline-flex items-center justify-center font-medium rounded-button transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-sage focus-visible:outline-offset-2 disabled:opacity-50 disabled:cursor-not-allowed select-none";

  const sizeStyles = {
    sm: "px-3 py-1.5 text-sm gap-1.5",
    md: "px-4 py-2.5 text-base gap-2",
    lg: "px-6 py-3.5 text-lg gap-2.5",
  };

  const variantStyles = {
    primary: "bg-sage text-white hover:bg-sage-hover active:bg-sage/90 shadow-sm",
    secondary: "bg-sage-pale text-ink hover:bg-sage-paleHover border border-sage/20",
    subtle: "bg-transparent text-ink hover:bg-sage-pale/50",
    danger: "bg-clay text-white hover:bg-clay/90 shadow-sm",
    ghost: "bg-transparent text-ink hover:bg-black/5",
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
