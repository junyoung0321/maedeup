import { CalendarDays, MapPin, CheckCircle2, ChevronRight } from "lucide-react";

export type Step = "schedule" | "place" | "done";

interface StepIndicatorProps {
  currentStep: Step;
}

const steps: { key: Step; label: string; icon: typeof CalendarDays }[] = [
  { key: "schedule", label: "일정", icon: CalendarDays },
  { key: "place", label: "장소", icon: MapPin },
  { key: "done", label: "생성 완료", icon: CheckCircle2 },
];

export default function StepIndicator({ currentStep }: StepIndicatorProps) {
  const currentIndex = steps.findIndex((s) => s.key === currentStep);
  const allDone = currentStep === "done";

  return (
    <div className="flex items-center gap-2">
      {steps.map((step, i) => {
        const isPast = i < currentIndex;
        const isCurrent = step.key === currentStep;
        const isActive = isCurrent || (allDone && true);
        const Icon = step.icon;
        return (
          <div key={step.key} className="flex items-center gap-2">
            {i > 0 && (
              <ChevronRight
                className="shrink-0"
                style={{ width: 18, height: 18, color: "#818cf8" }}
              />
            )}
            <div
              className="shrink-0"
              style={{
                width: "clamp(28px, 1.8vw + 12px, 42px)",
                aspectRatio: "42 / 37",
                borderRadius: 90,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: isActive
                  ? "2px solid #6366f1"
                  : "2px solid #c7d2fe",
                background: isActive
                  ? "linear-gradient(135deg, #4338ca, #4f46e5)"
                  : "#e0e7ff",
              }}
            >
              <Icon
                style={{
                  width: "clamp(14px, 0.8vw + 8px, 20px)",
                  height: "clamp(14px, 0.8vw + 8px, 20px)",
                  color: isActive ? "#ffffff" : "#4338ca",
                }}
              />
            </div>
            <span
              className="hidden lg:inline whitespace-nowrap"
              style={{
                fontSize: "clamp(14px, 0.6vw + 8px, 20px)",
                letterSpacing: 0.6,
                fontFamily: "Pretendard, sans-serif",
                fontWeight: isActive ? 500 : 300,
                color: isActive ? "#ffffff" : "#a5b4fc",
              }}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
