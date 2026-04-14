import Header from "@/components/layout/Header";
import UserPreferencesForm from "@/components/settings/UserPreferencesForm";

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-[960px] px-6 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold text-slate-900">환경 설정</h1>
          <p className="mt-2 text-sm text-slate-500">내 모임 취향과 기본 위치를 관리합니다.</p>
        </div>
        <UserPreferencesForm />
      </main>
    </div>
  );
}
