"use client";

export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-center min-h-screen bg-gray-100">
      <div className="w-[390px] min-h-screen bg-white relative overflow-hidden shadow-xl">
        {children}
      </div>
    </div>
  );
}
