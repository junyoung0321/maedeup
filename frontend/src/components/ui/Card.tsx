interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export default function Card({ children, className = "" }: CardProps) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 shadow-md ${className}`}>
      {children}
    </div>
  );
}
