"use client";

import { useState } from "react";
import { Sparkles, RefreshCw, Minus, Plus, X, MapPin, Zap, Heart, Search, UserPlus, UsersRound } from "lucide-react";
import Header from "@/components/layout/Header";
import { apiFetch } from "@/lib/api";

interface PlaceResult {
  id: string;
  name: string;
  address: string;
  phone: string;
  url: string;
  x: string;
  y: string;
  category: string;
}

const MOODS = ["모던", "아늑함", "트렌디", "야외활동", "조용함", "자연"];
const DURATIONS = ["1~3시간", "3시간", "3~5시간", "5시간 이상"];

const REGIONS: Record<string, Record<string, string[]>> = {
  서울특별시: {
    강남구: ["역삼동", "논현동", "청담동", "삼성동"],
    마포구: ["홍대입구", "합정동", "망원동", "연남동"],
    종로구: ["인사동", "삼청동", "북촌", "광화문"],
    용산구: ["이태원동", "한남동", "녹사평"],
  },
  경기도: {
    수원시: ["영통동", "팔달구", "장안구", "권선구"],
    성남시: ["분당구", "수정구", "중원구"],
    고양시: ["일산동구", "일산서구", "덕양구"],
    안양시: ["만안구", "동안구"],
  },
  강원도: {
    춘천시: ["소양동", "후평동", "신북읍"],
    강릉시: ["경포동", "주문진읍", "성산면"],
    속초시: ["청호동", "교동", "노학동"],
  },
  충청도: {
    대전시: ["유성구", "서구", "중구", "동구"],
    청주시: ["상당구", "흥덕구", "청원구"],
    천안시: ["동남구", "서북구"],
  },
  전라도: {
    광주시: ["동구", "서구", "남구", "북구", "광산구"],
    전주시: ["완산구", "덕진구"],
    여수시: ["돌산읍", "율촌면", "소라면"],
  },
  경상도: {
    부산시: ["해운대구", "수영구", "남구", "사하구"],
    대구시: ["수성구", "달서구", "중구", "북구"],
    경주시: ["황남동", "교동", "성건동"],
  },
  제주도: {
    제주시: ["연동", "노형동", "이도동", "아라동"],
    서귀포시: ["서귀동", "중앙동", "대정읍"],
  },
};


export default function AiRecommendPage() {
  // Form state
  const [date, setDate] = useState("2026년 6월 10일(수) 오후 7시");
  const [members, setMembers] = useState(4);
  const [region, setRegion] = useState("경기도 > 수원시 > 영통동");
  const [selectedMoods, setSelectedMoods] = useState<string[]>(["아늑함"]);
  const [description, setDescription] = useState("");
  const [selectedDurations, setSelectedDurations] = useState<string[]>(["1~3시간"]);
  const [friendInput, setFriendInput] = useState("");
  const [friendChips, setFriendChips] = useState<string[]>([]);

  // Results state
  const [places, setPlaces] = useState<PlaceResult[]>([]);
  const [hasResults, setHasResults] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Region modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [selectedProvince, setSelectedProvince] = useState("");
  const [selectedCity, setSelectedCity] = useState("");
  const [selectedDistrict, setSelectedDistrict] = useState("");

  const toggleMood = (m: string) =>
    setSelectedMoods((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]);

  const toggleDuration = (d: string) =>
    setSelectedDurations((prev) => prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]);

  const handleRecommend = async () => {
    const district = region.split(" > ").pop() ?? region;
    const query = [district, ...selectedMoods, description.trim().slice(0, 40)]
      .filter(Boolean)
      .join(" ");

    setIsLoading(true);
    setError(null);
    try {
      const results = await apiFetch<PlaceResult[]>("/api/v1/places/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      setPlaces(results);
      setHasResults(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "추천을 불러올 수 없어요");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegionConfirm = () => {
    const parts = [selectedProvince, selectedCity, selectedDistrict].filter(Boolean);
    setRegion(parts.join(" > ") || region);
    setModalOpen(false);
    setStep(1);
    setSelectedProvince("");
    setSelectedCity("");
    setSelectedDistrict("");
  };

  const provinces = Object.keys(REGIONS);
  const cities = selectedProvince ? Object.keys(REGIONS[selectedProvince]) : [];
  const districts = selectedProvince && selectedCity ? REGIONS[selectedProvince][selectedCity] : [];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <div className="flex flex-1 gap-6 p-6 max-w-[1400px] mx-auto w-full">
        {/* Left Panel — Form */}
        <div className="w-[440px] shrink-0 bg-white rounded-2xl border border-gray-200 p-6 flex flex-col gap-5 self-start">
          <div className="flex items-center gap-2">
            <Sparkles size={20} className="text-primary-600" />
            <span className="text-lg font-bold text-gray-900">AI 빠른 추천 보고서</span>
          </div>

          {/* 일정 선택 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">일정 선택</label>
            <input
              type="text"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 인원수 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">인원수</label>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setMembers(Math.max(1, members - 1))}
                className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center hover:bg-gray-100"
              >
                <Minus size={14} />
              </button>
              <span className="text-sm font-semibold text-gray-800 w-10 text-center">{members}명</span>
              <button
                onClick={() => setMembers(members + 1)}
                className="w-8 h-8 rounded-full border border-gray-300 flex items-center justify-center hover:bg-gray-100"
              >
                <Plus size={14} />
              </button>
            </div>
          </div>

          {/* 참여 친구 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-1.5">
              <UsersRound size={13} className="text-primary-600" />
              참여 친구
              <span className="font-normal normal-case text-gray-400 ml-1">{friendChips.length}명 추가됨</span>
            </label>
            <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 bg-gray-50">
              <Search size={14} className="text-gray-400 shrink-0" />
              <input
                value={friendInput}
                onChange={(e) => setFriendInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && friendInput.trim()) {
                    setFriendChips((prev) => [...prev, friendInput.trim()]);
                    setFriendInput("");
                  }
                }}
                placeholder="이름 입력 후 Enter..."
                className="flex-1 bg-transparent text-sm text-gray-800 outline-none"
              />
              <UserPlus size={16} className="text-primary-600 shrink-0" />
            </div>
            {friendChips.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {friendChips.map((name, idx) => (
                  <span
                    key={idx}
                    className="flex items-center gap-1.5 bg-gray-100 border border-gray-200 rounded-full px-3 py-1 text-xs font-semibold text-gray-700"
                  >
                    {name}
                    <button onClick={() => setFriendChips((prev) => prev.filter((_, i) => i !== idx))}>
                      <X size={12} className="text-gray-400 hover:text-gray-600" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* 장소 선택 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">장소 선택</label>
            <div className="flex items-center gap-2">
              <span className="flex-1 text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 truncate">
                {region}
              </span>
              <button
                onClick={() => { setModalOpen(true); setStep(1); }}
                className="text-xs font-semibold text-primary-600 border border-primary-200 rounded-lg px-3 py-2 hover:bg-primary-50 whitespace-nowrap"
              >
                변경
              </button>
            </div>
          </div>

          {/* 무드 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">무드 추천</label>
            <div className="flex flex-wrap gap-2">
              {MOODS.map((m) => (
                <button
                  key={m}
                  onClick={() => toggleMood(m)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    selectedMoods.includes(m)
                      ? "bg-primary-600 text-white border-primary-600"
                      : "bg-white text-gray-600 border-gray-300 hover:border-primary-400"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {/* 주요 설명 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">주요 설명</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="원하는 분위기나 특별 요청사항을 입력하세요..."
              rows={3}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 resize-none focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* 이동 방법 */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">이동 방법</label>
            <div className="flex flex-wrap gap-2">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  onClick={() => toggleDuration(d)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                    selectedDurations.includes(d)
                      ? "bg-primary-600 text-white border-primary-600"
                      : "bg-white text-gray-600 border-gray-300 hover:border-primary-400"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* CTA Button */}
          <button
            onClick={handleRecommend}
            disabled={isLoading}
            className="w-full bg-primary-600 hover:bg-primary-500 text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-70"
          >
            {isLoading ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                AI 분석 중...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                AI 추천 받기 &gt;&gt;
              </>
            )}
          </button>
        </div>

        {/* Right Panel — Results */}
        <div className="flex-1 bg-white rounded-2xl border border-gray-200 p-6 flex flex-col gap-5 self-start">
          {!hasResults ? (
            /* Empty State */
            <div className="flex flex-col items-center justify-center py-20 gap-6">
              <div className="w-16 h-16 rounded-full bg-primary-50 flex items-center justify-center">
                <Sparkles size={28} className="text-primary-600" />
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-gray-800">AI가 최적의 장소를 찾아드릴게요</p>
                <p className="text-sm text-gray-500 mt-1">왼쪽 조건을 설정하고 추천 받기 버튼을 눌러보세요</p>
              </div>
              <div className="grid grid-cols-3 gap-4 w-full max-w-lg mt-2">
                {[
                  { icon: <Zap size={18} className="text-yellow-500" />, title: "빠른 분석", desc: "수천 개의 장소를 즉시 분석" },
                  { icon: <MapPin size={18} className="text-blue-500" />, title: "정확한 위치", desc: "실시간 거리·교통 반영" },
                  { icon: <Heart size={18} className="text-rose-500" />, title: "맞춤 추천", desc: "모임 유형에 최적화된 결과" },
                ].map((f, i) => (
                  <div key={i} className="bg-gray-50 rounded-xl p-4 flex flex-col gap-2">
                    {f.icon}
                    <span className="text-sm font-semibold text-gray-800">{f.title}</span>
                    <span className="text-xs text-gray-500">{f.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Results */
            <>
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold text-gray-900">AI 추천 결과</span>
                <button
                  onClick={handleRecommend}
                  className="flex items-center gap-1.5 text-xs font-medium text-primary-600 border border-primary-200 rounded-lg px-3 py-1.5 hover:bg-primary-50"
                >
                  <RefreshCw size={13} />
                  새로 추천받기
                </button>
              </div>

              {error ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <p className="text-sm font-semibold text-red-500">{error}</p>
                  <p className="text-xs text-gray-400">조건을 바꿔 다시 시도해보세요</p>
                </div>
              ) : places.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <p className="text-sm font-semibold text-gray-600">검색 결과가 없어요</p>
                  <p className="text-xs text-gray-400">지역이나 무드 조건을 바꿔 다시 시도해보세요</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4">
                  {places.map((place, idx) => {
                    const categoryShort = place.category.split(">").pop()?.trim() ?? place.category;
                    return (
                      <div
                        key={place.id}
                        className="flex gap-4 border border-gray-200 rounded-xl p-4 hover:border-primary-300 hover:shadow-sm transition-all"
                      >
                        {/* Rank badge */}
                        <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center shrink-0 self-center">
                          <span className="text-sm font-bold text-primary-600">#{idx + 1}</span>
                        </div>

                        <div className="flex flex-col gap-1.5 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-medium text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full">
                              {categoryShort}
                            </span>
                          </div>
                          <span className="text-base font-bold text-gray-900 truncate">{place.name}</span>
                          <span className="text-sm text-gray-500 truncate">{place.address || "주소 정보 없음"}</span>
                          {place.phone && (
                            <span className="text-xs text-gray-400">{place.phone}</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Region Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-[440px] flex flex-col gap-5 shadow-xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between">
              <span className="text-base font-bold text-gray-900">
                {step === 1 ? "도/특별시 선택" : step === 2 ? `${selectedProvince} — 시/군 선택` : `${selectedCity} — 구/동 선택`}
              </span>
              <button onClick={() => { setModalOpen(false); setStep(1); }}>
                <X size={20} className="text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            {/* Step indicator */}
            <div className="flex gap-1.5">
              {[1, 2, 3].map((s) => (
                <div
                  key={s}
                  className={`h-1 flex-1 rounded-full transition-colors ${s <= step ? "bg-primary-600" : "bg-gray-200"}`}
                />
              ))}
            </div>

            {/* Step content */}
            <div className="flex flex-wrap gap-2">
              {step === 1 &&
                provinces.map((p) => (
                  <button
                    key={p}
                    onClick={() => setSelectedProvince(p)}
                    className={`px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
                      selectedProvince === p
                        ? "bg-primary-600 text-white border-primary-600"
                        : "bg-white text-gray-700 border-gray-300 hover:border-primary-400"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              {step === 2 &&
                cities.map((c) => (
                  <button
                    key={c}
                    onClick={() => setSelectedCity(c)}
                    className={`px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
                      selectedCity === c
                        ? "bg-primary-600 text-white border-primary-600"
                        : "bg-white text-gray-700 border-gray-300 hover:border-primary-400"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              {step === 3 &&
                districts.map((d) => (
                  <button
                    key={d}
                    onClick={() => setSelectedDistrict(d)}
                    className={`px-3 py-2 rounded-xl text-sm font-medium border transition-colors ${
                      selectedDistrict === d
                        ? "bg-primary-600 text-white border-primary-600"
                        : "bg-white text-gray-700 border-gray-300 hover:border-primary-400"
                    }`}
                  >
                    {d}
                  </button>
                ))}
            </div>

            {/* CTA */}
            <button
              onClick={() => {
                if (step < 3) setStep(step + 1);
                else handleRegionConfirm();
              }}
              disabled={
                (step === 1 && !selectedProvince) ||
                (step === 2 && !selectedCity) ||
                (step === 3 && !selectedDistrict)
              }
              className="w-full bg-primary-600 hover:bg-primary-500 disabled:opacity-40 text-white font-semibold py-3 rounded-xl transition-colors"
            >
              {step < 3 ? "다음 단계로" : "이 장소로 선택하기"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
