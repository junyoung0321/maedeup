export interface Friend {
  id: string;
  name: string;
  color: string;
  online: boolean;
}

export const mockFriends: Friend[] = [
  { id: "1", name: "김창윤", color: "#818cf8", online: true },
  { id: "2", name: "정준영", color: "#f472b6", online: true },
  { id: "3", name: "한산희", color: "#34d399", online: false },
  { id: "4", name: "최영규", color: "#fbbf24", online: true },
  { id: "5", name: "정승일", color: "#60a5fa", online: false },
  { id: "6", name: "김제영", color: "#a78bfa", online: true },
  { id: "7", name: "최주원", color: "#f87171", online: false },
  { id: "8", name: "뽀삐", color: "#4ade80", online: true },
];
