export interface Recommendation {
  id: string;
  title: string;
  description: string;
  time: string;
  memberCount: number;
  type: "schedule" | "place" | "activity";
}

export const mockRecommendations: Recommendation[] = [
  {
    id: "1",
    title: "카카오톡 기획 스터디",
    description: "오후 2시 60분 \u00b7 온라인",
    time: "01:20:00",
    memberCount: 4,
    type: "schedule",
  },
  {
    id: "2",
    title: "서현 후 금요일 추천 장소",
    description: "강남역 3번 출구 인근",
    time: "02:45:00",
    memberCount: 6,
    type: "place",
  },
  {
    id: "3",
    title: "지금 바로로 연락 가능",
    description: "참여 가능한 멤버 확인",
    time: "",
    memberCount: 3,
    type: "activity",
  },
];
