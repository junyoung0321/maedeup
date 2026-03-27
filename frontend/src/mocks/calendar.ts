export interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  color: string;
}

export const mockCalendarEvents: CalendarEvent[] = [
  { id: "1", title: "기획 스터디", date: "2026-03-05", color: "#4f46e5" },
  { id: "2", title: "랩실 회식", date: "2026-03-10", color: "#64748b" },
  { id: "3", title: "기획 스터디", date: "2026-03-18", color: "#4f46e5" },
  { id: "4", title: "영어 회화", date: "2026-03-19", color: "#ea580c" },
  { id: "5", title: "기획 스터디", date: "2026-03-20", color: "#4f46e5" },
  { id: "6", title: "러닝 크루", date: "2026-03-22", color: "#16a34a" },
  { id: "7", title: "등산 모임", date: "2026-03-25", color: "#ef4444" },
  { id: "8", title: "기획 스터디", date: "2026-03-25", color: "#4f46e5" },
  { id: "9", title: "영어 회화", date: "2026-03-26", color: "#ea580c" },
  { id: "10", title: "독서 모임", date: "2026-03-27", color: "#4f46e5" },
  { id: "11", title: "영어 회화", date: "2026-03-27", color: "#ea580c" },
  { id: "12", title: "러닝 크루", date: "2026-03-29", color: "#16a34a" },
  { id: "13", title: "등산 모임", date: "2026-03-30", color: "#ef4444" },
  { id: "14", title: "봉사활동", date: "2026-03-31", color: "#16a34a" },
];
