export default function MeetingLoading() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-3 border-[#4f46e5] border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-slate-500">모임 정보를 불러오는 중...</p>
      </div>
    </div>
  );
}
