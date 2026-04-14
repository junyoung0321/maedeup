import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center max-w-md mx-auto px-6">
        <p className="text-6xl font-bold text-[#4f46e5] mb-4">404</p>
        <h2 className="text-xl font-semibold text-slate-900 mb-2">
          페이지를 찾을 수 없어요
        </h2>
        <p className="text-sm text-slate-500 mb-6">
          요청하신 페이지가 존재하지 않거나 이동되었을 수 있어요.
        </p>
        <Link
          href="/"
          className="inline-block px-6 py-2.5 rounded-full bg-[#4f46e5] text-white text-sm font-semibold hover:bg-[#4338ca] transition-colors"
        >
          홈으로 돌아가기
        </Link>
      </div>
    </div>
  );
}
