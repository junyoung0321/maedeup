interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

const variantMap = {
  primary: "bg-primary-600 text-white hover:bg-primary-500",
  secondary: "bg-white text-primary-600 border border-primary-600 hover:bg-primary-50",
  ghost: "bg-slate-50 text-slate-500 border border-slate-200 hover:bg-slate-100",
};

const sizeMap = { sm: "px-3 py-1.5 text-sm", md: "px-5 py-2.5 text-base", lg: "px-6 py-3 text-lg" };

export default function Button({ variant = "primary", size = "md", className = "", children, ...props }: ButtonProps) {
  return (
    <button
      className={`${variantMap[variant]} ${sizeMap[size]} rounded-xl font-medium transition-colors ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
