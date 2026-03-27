export interface Meeting {
  id: string;
  name: string;
  schedule: string;
  badge: string;
  badgeColor: string;
  members: string;
  dDay: string;
  dDayColor: string;
}

export const mockMeetings: Meeting[] = [
  {
    id: "1",
    name: "기획 스터디",
    schedule: "매주 화요일 20:00 \u00b7 온라인",
    badge: "진행중",
    badgeColor: "#4f46e5",
    members: "3 / 6명 참여",
    dDay: "D-3",
    dDayColor: "#ef4444",
  },
  {
    id: "2",
    name: "주말 등산 모임",
    schedule: "매달 둘째 토요일 \u00b7 남한산",
    badge: "참여예정",
    badgeColor: "#059669",
    members: "5 / 10명 참여",
    dDay: "D-10",
    dDayColor: "#3b82f6",
  },
  {
    id: "3",
    name: "랩실 회식",
    schedule: "2월 17일 화 18:00 미진축산",
    badge: "지난 일정",
    badgeColor: "#2859c5",
    members: "8 / 10명 참여",
    dDay: "D+10",
    dDayColor: "#3b82f6",
  },
  {
    id: "4",
    name: "영어 회화 모임",
    schedule: "매주 수요일 19:00 \u00b7 강남",
    badge: "모집중",
    badgeColor: "#ea580c",
    members: "7 / 12명 참여",
    dDay: "D-7",
    dDayColor: "#ea580c",
  },
  {
    id: "5",
    name: "주말 러닝 크루",
    schedule: "매주 일요일 07:00 \u00b7 한강공원",
    badge: "진행중",
    badgeColor: "#4f46e5",
    members: "15 / 20명 참여",
    dDay: "D-2",
    dDayColor: "#ef4444",
  },
];
