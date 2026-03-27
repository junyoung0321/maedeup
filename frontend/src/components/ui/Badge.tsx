interface BadgeProps {
  children: React.ReactNode;
  variant?: "primary" | "accent" | "neutral";
}

const variantMap = {
  primary: "bg-primary-100 text-primary-600",
  accent: "bg-accent-100 text-accent-400",
  neutral: "bg-slate-100 text-slate-500",
};

export default function Badge({ children, variant = "primary" }: BadgeProps) {
  return (
    <span className={`${variantMap[variant]} px-2 py-0.5 rounded-full text-xs font-normal`}>
      {children}
    </span>
  );
}
