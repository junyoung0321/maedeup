export interface Place {
  id: string;
  name: string;
  category: string;
  tags: string[];
  tagColors: { text: string; bg: string }[];
  rating: number;
  reviewCount: number;
  priceRange: string;
  address: string;
  hours: string;
  phone: string;
  menu: { name: string; price: number }[];
}

export const mockPlaces: Place[] = [
  {
    id: "1",
    name: "을지로 골목식당",
    category: "한식",
    tags: ["한식", "골목맛집", "단체석 가능"],
    tagColors: [
      { text: "#4f46e5", bg: "#eef2ff" },
      { text: "#d97706", bg: "#fef3c7" },
      { text: "#16a34a", bg: "#dcfce7" },
    ],
    rating: 4.5,
    reviewCount: 324,
    priceRange: "1~2만원대",
    address: "서울 강남구 역삼동 123-4",
    hours: "11:30 ~ 22:00",
    phone: "02-1234-5678",
    menu: [
      { name: "된장찌개 정식", price: 12000 },
      { name: "제육볶음 정식", price: 13000 },
      { name: "김치찜", price: 15000 },
    ],
  },
];
